#!/usr/bin/env python3
"""Start or inspect the local Claude workers dashboard."""
import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from urllib.parse import parse_qs, urlsplit, urlencode
from urllib.request import Request, urlopen
import worker_registry as registry
import session
import activity
import settings
import routing

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "dashboard"
CSP = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


def make_server(token, port=0):
    activity_reader = activity.ActivityReader()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never write a URL token or a task brief into an access log.

        def respond(self, code, body, content_type="application/json"):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", CSP)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def authorized(self, api=False):
            expected = "127.0.0.1:" + str(self.server.server_port)
            if self.headers.get("Host") != expected or self.headers.get("Origin") not in (None, "http://" + expected):
                self.respond(403, {"error": "Local dashboard access only"})
                return False
            if api and not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
                self.respond(401, {"error": "Open the dashboard using its local launch link"})
                return False
            return True

        def do_POST(self):
            if not self.authorized(api=True):
                return
            if urlsplit(self.path).path != "/api/settings":
                self.respond(404, {"error": "Not found"})
                return
            if self.headers.get_content_type() != "application/json":
                self.respond(415, {"error": "Settings require application/json"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 4096:
                    self.respond(413, {"error": "Settings request too large"})
                    return
                if length <= 0 or self.headers.get("Transfer-Encoding"):
                    raise ValueError("Invalid request length")
                self.connection.settimeout(5)
                data = json.loads(self.rfile.read(length))
                self.respond(200, settings.save(data))
            except (ValueError, TypeError):
                self.respond(400, {"error": "Invalid worker settings"})
            except OSError:
                self.respond(503, {"error": "Could not save worker settings"})

        def do_GET(self):
            url = urlsplit(self.path)
            if not self.authorized(api=url.path.startswith("/api/")):
                return
            if url.path.startswith("/api/"):
                try:
                    if url.path == "/api/health":
                        self.respond(200, {"app": "claude-workers", "pid": os.getpid()})
                    elif url.path == "/api/settings/catalog":
                        self.respond(200, routing.catalog())
                    elif url.path == "/api/settings":
                        self.respond(200, settings.read())
                    elif url.path == "/api/runs":
                        thread = parse_qs(url.query).get("thread", [None])[0]
                        self.respond(200, {"runs": registry.list_runs(thread), "server_time": time.time()})
                    elif url.path in ("/api/activity", "/api/messages"):
                        query = parse_qs(url.query)
                        thread = query.get("thread", [""])[0]
                        if thread not in {row.get("codex_thread_id") for row in registry.list_runs()}:
                            self.respond(404, {"error": "No registered workers for this conversation"})
                            return
                        if url.path == "/api/messages":
                            self.respond(200, activity_reader.messages(thread))
                            return
                        before = query.get("before", [None])[0]
                        self.respond(200, activity_reader.read(thread, query=query.get("q", [""])[0],
                            kind=query.get("kind", [""])[0], before=int(before) if before else None))
                    elif url.path.startswith("/api/runs/"):
                        self.respond(200, registry.details(url.path.removeprefix("/api/runs/")))
                    else:
                        self.respond(404, {"error": "Not found"})
                except FileNotFoundError:
                    self.respond(404, {"error": "Run no longer exists"})
                except (ValueError, TypeError):
                    self.respond(400, {"error": "Invalid run record or identifier"})
                except OSError:
                    self.respond(503, {"error": "Worker records are temporarily unavailable"})
                return
            files = {"/": ("index.html", "text/html; charset=utf-8"),
                     "/settings": ("settings.html", "text/html; charset=utf-8"),
                     "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                     "/view.mjs": ("view.mjs", "text/javascript; charset=utf-8"),
                     "/stats.mjs": ("stats.mjs", "text/javascript; charset=utf-8"),
                     "/settings-ui.mjs": ("settings-ui.mjs", "text/javascript; charset=utf-8"),
                     "/activity-ui.mjs": ("activity-ui.mjs", "text/javascript; charset=utf-8"),
                     "/style.css": ("style.css", "text/css; charset=utf-8")}
            if url.path not in files:
                self.respond(404, {"error": "Not found"})
                return
            filename, mime = files[url.path]
            self.respond(200, (ASSETS / filename).read_bytes(), mime)
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def service_file():
    return registry.state_root() / "dashboard.json"


def service_status():
    try:
        data = json.loads(service_file().read_text())
        port = data["port"]
        if type(port) is not int or not 0 < port < 65536:
            return None
        request = Request(f"http://127.0.0.1:{port}/api/health",
                          headers={"Authorization": "Bearer " + data["token"]})
        with urlopen(request, timeout=1) as response:
            health = json.load(response)
        return data if health.get("app") == "claude-workers" and health.get("pid") == data["pid"] else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def serve(port, token=None):
    # Single server per Codex home, including concurrent `start` calls.
    import fcntl
    root = registry.state_root()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (root / "dashboard.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        token = token or secrets.token_urlsafe(32)
        server = make_server(token, port)
        registry.atomic_json(service_file(), {"port": server.server_port, "token": token, "pid": os.getpid()})
        try:
            server.serve_forever()
        finally:
            server.server_close()


def start(thread_id=None):
    data = service_status()
    if not data:
        root = registry.state_root()
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (root / "dashboard.log").open("ab") as log:
            subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "serve"],
                             stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True,
                             cwd=Path(__file__).resolve().parent)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            data = service_status()
            if data:
                break
            time.sleep(0.1)
        if not data:
            raise ValueError("Dashboard did not start; inspect " + str(root / "dashboard.log"))
    fragment = {"token": data["token"]}
    if thread_id:
        fragment["thread"] = thread_id
    return {"url": f"http://127.0.0.1:{data['port']}/#" + urlencode(fragment), "pid": data["pid"]}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "serve", "status", "import"))
    parser.add_argument("run_dir", type=Path, nargs="?")
    parser.add_argument("--title")
    parser.add_argument("--thread", help="Codex task to select in the UI")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    try:
        if args.action == "serve":
            serve(args.port)
        elif args.action == "start":
            print(json.dumps(start(args.thread or session.current_task_id())))
        elif args.action == "status":
            data = service_status()
            print(json.dumps({"running": bool(data), "pid": data["pid"] if data else None}))
        elif args.run_dir:
            print(json.dumps({"run_id": registry.import_run(args.run_dir, args.title)}))
        else:
            parser.error("import requires a run directory")
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
