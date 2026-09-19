import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import dashboard
import settings


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {'CODEX_HOME': self.temp.name})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_default_persistence_validation_and_private_file(self):
        self.assertEqual(settings.read()['permission_policy'], 'scoped')
        self.assertFalse(settings.settings_file().exists())
        for policy in settings.POLICIES:
            data = {'version': 1, 'permission_policy': policy}
            settings.save(data)
            self.assertEqual(settings.read()['permission_policy'], policy)
        self.assertEqual(settings.settings_file().stat().st_mode & 0o777, 0o600)
        for invalid in ({}, {'version': True, 'permission_policy': 'full'},
                        {'version': 1, 'permission_policy': []},
                        {'version': 1, 'permission_policy': 'full', 'extra': 1}):
            with self.assertRaises(ValueError):
                settings.save(invalid)
        self.assertEqual(settings.read()['permission_policy'], 'inherit')

    def test_upgrade_preserves_permission_and_legacy_save_preserves_models(self):
        settings.settings_file().parent.mkdir(parents=True)
        settings.settings_file().write_text(json.dumps({"version": 1, "permission_policy": "inherit"}))
        data = settings.read()
        self.assertEqual(data["version"], 2)
        self.assertEqual(data["permission_policy"], "inherit")
        data["models"]["profiles"]["deep"] = "opus"
        data["models"]["tasks"]["architecture"] = "fable"
        settings.save(data)
        settings.save({"version": 1, "permission_policy": "scoped"})
        saved = settings.read()
        self.assertEqual(saved["models"]["profiles"]["deep"], "opus")
        self.assertEqual(saved["models"]["tasks"]["architecture"], "fable")
        self.assertEqual(saved["permission_policy"], "scoped")

    def test_invalid_model_map_never_changes_saved_settings(self):
        data = settings.read()
        self.assertIn("models", data)
        settings.save(data)
        previous = settings.settings_file().read_bytes()
        for key, value in (("architecture", "unknown"), ("made_up", "opus"), ("final_review", [])):
            invalid = json.loads(json.dumps(data))
            invalid["models"]["tasks"][key] = value
            with self.assertRaises(ValueError):
                settings.save(invalid)
            self.assertEqual(settings.settings_file().read_bytes(), previous)

    def test_settings_api_requires_authorized_local_json_and_preserves_on_error(self):
        server = dashboard.make_server('fixture-token')
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f'http://127.0.0.1:{server.server_port}/api/settings'
        def request(data=None, headers=None):
            supplied = {'Authorization': 'Bearer fixture-token', 'Content-Type': 'application/json'}
            supplied.update(headers or {})
            return urlopen(Request(base, data=data, headers=supplied), timeout=2)
        full = json.dumps({'version': 1, 'permission_policy': 'full'}).encode()
        with request() as response:
            self.assertEqual(json.load(response)['permission_policy'], 'scoped')
        for body, headers, code in [
            (full, {'Authorization': ''}, 401),
            (full, {'Origin': 'https://example.com'}, 403),
            (full, {'Host': 'example.com'}, 403),
            (full, {'Content-Type': 'text/plain'}, 415),
            (b'x' * 5000, {}, 413), (b'not json', {}, 400),
            (b'{"version":1,"permission_policy":"oops"}', {}, 400),
            (b'{"version":1,"permission_policy":"full","path":"/tmp/extra"}', {}, 400),
        ]:
            with self.subTest(code=code, headers=headers):
                with self.assertRaises(HTTPError) as error:
                    request(body, headers)
                self.assertEqual(error.exception.code, code)
                error.exception.close()
                self.assertFalse(settings.settings_file().exists())
        with request(full) as response:
            self.assertEqual(json.load(response)['permission_policy'], 'full')
        with request() as response:
            self.assertEqual(json.load(response)['permission_policy'], 'full')
        self.assertEqual(settings.read()['permission_policy'], 'full')
        self.assertEqual(list(settings.settings_file().parent.glob('*.json')), [settings.settings_file()])

    def test_separate_page_and_api_round_trip_model_routes(self):
        server = dashboard.make_server("fixture-token")
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_port}"
        headers = {"Authorization": "Bearer fixture-token", "Content-Type": "application/json"}
        with urlopen(base + "/settings") as response:
            self.assertEqual(response.headers.get_content_type(), "text/html")
            self.assertIn("Content-Security-Policy", response.headers)
        with urlopen(Request(base + "/api/settings/catalog", headers=headers)) as response:
            catalog = json.load(response)
            self.assertTrue(any(t["id"] == "final_review" for t in catalog["tasks"]))
        with self.assertRaises(HTTPError) as error:
            urlopen(base + "/api/settings/catalog")
        self.assertEqual(error.exception.code, 401)
        error.exception.close()
        data = settings.read()
        data["models"]["tasks"]["final_review"] = "opus"
        data["models"]["profiles"]["deep"] = "fable"
        with urlopen(Request(base + "/api/settings", data=json.dumps(data).encode(), headers=headers)) as response:
            self.assertEqual(json.load(response)["models"]["tasks"]["final_review"], "opus")
        with urlopen(Request(base + "/api/settings", headers=headers)) as response:
            self.assertEqual(json.load(response)["models"], data["models"])

    def test_permission_cli_preserves_custom_routing(self):
        import subprocess
        data = settings.read()
        data["models"]["tasks"]["final_review"] = "opus"
        settings.save(data)
        result = subprocess.run([sys.executable, str(Path(settings.__file__)), "set", "--policy", "inherit"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        saved = json.loads(result.stdout)
        self.assertEqual(saved["permission_policy"], "inherit")
        self.assertEqual(saved["models"]["tasks"]["final_review"], "opus")


if __name__ == '__main__':
    unittest.main()
