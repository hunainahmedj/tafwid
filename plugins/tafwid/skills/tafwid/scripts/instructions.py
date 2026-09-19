"""Select one instruction source per assignment; keep audit metadata off prompts."""
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import worker_registry

MAX_FILES = 512
MAX_BYTES = 32 * 1024 * 1024
IGNORED = {".git", "__pycache__", ".DS_Store"}


def skill_name(text):
    # Conservative subset of skill frontmatter; unusual names use supplied text.
    if not text.startswith("---\n"):
        return None
    front = text.split("\n---", 1)[0]
    match = re.search(r"^name:\s*['\"]?([a-z0-9][a-z0-9_-]*)['\"]?\s*$", front, re.M)
    return match.group(1) if match else None


def native_invocable(text):
    front = text.split("\n---", 1)[0]
    # These fields alter execution rather than merely supply worker instructions.
    if re.search(r"^(context|agent|hooks|model|effort|allowed-tools):", front, re.M):
        return False
    flag = re.search(r"^disable-model-invocation:\s*(.*)$", front, re.M)
    return not flag or flag.group(1).strip().lower() == "false"


def external_reference(data):
    return (b"../" in data or re.search(rb'(?:\]\(|["\x27`])(?:/|~/)', data)
            or re.search(rb'\$\{?[A-Z_]*(?:ROOT|DIR|HOME)\b', data))


def describe(path):
    path = Path(path).expanduser().resolve(strict=True)
    content = path.read_text(encoding="utf-8")
    if not content.strip():
        raise ValueError(f"Empty instruction file: {path}")
    digest = hashlib.sha256(content.encode()).hexdigest()
    package = path.parent if (path.parent / "SKILL.md").is_file() else None
    complete = True
    fingerprint = hashlib.sha256()
    if package:
        total = count = 0
        try:
            for item in sorted(package.rglob("*")):
                relative = item.relative_to(package)
                if any(part in IGNORED for part in relative.parts):
                    continue
                if item.is_symlink():
                    complete = False
                    break
                if not item.is_file():
                    continue
                count += 1
                total += item.stat().st_size
                if count > MAX_FILES or total > MAX_BYTES:
                    complete = False
                    break
                data = item.read_bytes()
                # Outside resources cannot be equated from this package alone.
                # False negatives are safe: supply the selected source instead.
                if external_reference(data):
                    complete = False
                fingerprint.update(str(relative).encode() + b"\0" + hashlib.sha256(data).digest())
            fingerprint.update(str(path.relative_to(package)).encode())
        except OSError:
            complete = False
    else:
        fingerprint.update(content.encode())
        fingerprint.update(str(path.parent).encode())
        # Non-skill files may reference neighboring resources. Preserve origin and
        # resend on resumes when equivalence of dependencies cannot be established.
        if (external_reference(content.encode()) or
                re.search(r'\]\([^#][^)]*\)|(?:\.{1,2}/|~/)|\b[\w-]+\.[a-zA-Z][a-zA-Z0-9]{0,8}\b', content)):
            complete = False
    if not complete:
        fingerprint.update(str(path).encode() + digest.encode())
    return {"source_path": str(path), "name": skill_name(content) if path.name == "SKILL.md" else None,
            "kind": "skill" if path.name == "SKILL.md" else "file", "content_sha256": digest,
            "fingerprint": fingerprint.hexdigest(), "fingerprint_complete": complete,
            "content": content}


def overrides_present(cwd, config):
    paths = [config / "settings.json", config / "settings.local.json",
             Path("/Library/Application Support/ClaudeCode/managed-settings.json"),
             Path("/etc/claude-code/managed-settings.json")]
    for parent in (cwd, *cwd.parents):
        paths.extend((parent / ".claude/settings.json", parent / ".claude/settings.local.json"))
    for path in dict.fromkeys(paths):
        try:
            data = json.loads(path.read_text())
            # Avoid reimplementing precedence/value semantics for invocation
            # overrides: any override disables this optional optimization.
            if not isinstance(data, dict) or data.get("skillOverrides"):
                return True
        except FileNotFoundError:
            continue
        except (OSError, ValueError):
            return True
    return False


def discover(claude, cwd, names):
    """Inspect local CLI metadata only. Unknown inventory falls back to source."""
    if not names:
        return [], "not_needed"
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude").expanduser()
    if overrides_present(cwd, config):
        return [], "invocation_overrides_or_unreadable_settings"
    candidates = []
    status = "available"
    try:
        result = subprocess.run([claude, "plugin", "list", "--json"], cwd=cwd,
                                capture_output=True, text=True, timeout=10)
        plugins = json.loads(result.stdout) if result.returncode == 0 else None
        if not isinstance(plugins, list):
            raise ValueError("Unrecognized plugin inventory")
        for plugin in plugins:
            if not isinstance(plugin, dict) or plugin.get("enabled") is not True:
                continue
            identity, root = plugin.get("id"), plugin.get("installPath")
            if not isinstance(identity, str) or not isinstance(root, str):
                continue
            prefix = identity.split("@", 1)[0]
            if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", prefix):
                continue
            for selected in names:
                path = Path(root) / "skills" / selected / "SKILL.md"
                try:
                    name = skill_name(path.read_text(encoding="utf-8"))
                    if name in names:
                        candidates.append({"path": path, "name": f"{prefix}:{name}",
                                           "version": plugin.get("version")})
                except (OSError, UnicodeError):
                    continue
    except (OSError, ValueError, subprocess.TimeoutExpired):
        status = "unavailable"
    # User/project skills require no plugin. Consider only selected skill names;
    # ambiguous invocable names are rejected below, rather than guessing precedence.
    roots = [config / "skills", *[parent / ".claude/skills" for parent in (cwd, *cwd.parents)]]
    for root in dict.fromkeys(roots):
        for name in names:
            path = root / name / "SKILL.md"
            if path.is_file():
                candidates.append({"path": path, "name": name, "version": None})
    return candidates, status


def prior_manifest(out, summary):
    # Failed/auth-rejected/time-limited calls do not prove that instructions were
    # received. Legacy or missing manifests simply cause explicit redelivery.
    if (summary.get("claude_exit_code") != 0 or summary.get("status") not in
            {"completed", "native_required", "blocked", "needs_review"}):
        return None
    # --resume selects the Claude session's latest history, even if the caller
    # supplied an older run directory. Never deduplicate against that old state.
    history = [row for row in worker_registry.list_runs(summary.get("codex_thread_id"))
               if row.get("session_id") == summary.get("session_id")
               and row.get("codex_thread_id") == summary.get("codex_thread_id")]
    if not history or Path(history[0]["output_dir"]).resolve() != Path(out).expanduser().resolve():
        return None
    try:
        data = json.loads((Path(out).expanduser() / "instructions.json").read_text())
        if (data.get("version") == 1 and data.get("session_id") == summary.get("session_id")
                and data.get("codex_thread_id") == summary.get("codex_thread_id")
                and data.get("cwd") == summary.get("cwd") and isinstance(data.get("instructions"), list)
                and all(isinstance(item, dict) and isinstance(item.get("source_path"), str)
                        and isinstance(item.get("fingerprint"), str) for item in data["instructions"])):
            return data
    except (OSError, ValueError, AttributeError, TypeError):
        pass
    return None


def prepare(paths, prompt, previous=None, native=(), *, claude=None, cwd=None):
    sources = []
    seen = set()
    for path in paths:
        item = describe(path)
        # Path aliases and identical self-contained packages are the same input.
        key = item["fingerprint"] if item["fingerprint_complete"] else item["source_path"]
        if key not in seen:
            sources.append(item)
            seen.add(key)
    prior = {item["source_path"]: item for item in (previous or {}).get("instructions", [])}
    entries = {path: {**item, "delivery": "retained"} for path, item in prior.items()}
    unresolved = [item for item in sources if not (
        item["fingerprint_complete"] and prior.get(item["source_path"], {}).get("fingerprint") == item["fingerprint"])]
    inventory_status = "not_needed"
    if claude:
        native, inventory_status = discover(claude, cwd, {item["name"] for item in unresolved
            if item["name"] and item["fingerprint_complete"]})
    candidates = collections.defaultdict(dict)
    for candidate in native:
        candidates[candidate["name"]][str(Path(candidate["path"]).resolve())] = candidate
    native_by_fingerprint = {}
    for aliases in candidates.values():
        if len(aliases) != 1:
            continue
        candidate = next(iter(aliases.values()))
        try:
            desc = describe(candidate["path"])
            if desc["fingerprint_complete"] and native_invocable(desc["content"]):
                native_by_fingerprint.setdefault(desc["fingerprint"], candidate)
        except (OSError, ValueError):
            continue
    chunks = []
    for item in sources:
        content = item["content"]
        record = {key: value for key, value in item.items() if key != "content"}
        old = prior.get(item["source_path"])
        if old and item["fingerprint_complete"] and old["fingerprint"] == item["fingerprint"]:
            entries[item["source_path"]] = {**old, "delivery": "retained"}
            continue
        match = native_by_fingerprint.get(item["fingerprint"]) if item["kind"] == "skill" else None
        replacing = " (replaces the earlier instructions from this source)" if old else ""
        if content in prompt and item["kind"] == "file" and item["fingerprint_complete"]:
            record["delivery"] = "brief"
        elif match:
            record.update(delivery="native", native_skill=match["name"],
                          native_path=str(match["path"]), native_version=match.get("version"))
            chunks.append(f"\n\nUse Skill {match['name']}{replacing}.\n")
        else:
            record["delivery"] = "inline"
            chunks.append(f"\n\nWORKER INSTRUCTIONS ({item['source_path']}){replacing}:\n" + content)
        entries[item["source_path"]] = record
    emitted = "".join(chunks)
    return emitted, {"version": 1, "instructions": list(entries.values()),
                     "inventory_status": inventory_status, "emitted_characters": len(emitted)}
