"""Keep named GPT CLI accounts in separate private Codex homes.

Only Codex writes credentials. This module never opens ``auth.json`` or makes a
model request. ``check`` asks ``codex login status`` for its login method.
"""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid

import paths

NAME = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")
RESERVED = {"gpt", "personal", "business", "claude"}
KINDS = {"personal", "business"}


def registry_path():
    """Return the private registry path without creating it."""
    return paths.state_root() / "accounts" / "registry.json"


def _rows():
    """Read saved records and reject malformed registry data."""
    if registry_path().is_symlink() or registry_path().parent.is_symlink():
        raise ValueError("GPT account registry is redirected")
    try:
        data = json.loads(registry_path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("accounts"), list):
        raise ValueError("Invalid GPT account registry")
    return data["accounts"]


def _save(rows):
    """Atomically save metadata with owner-only file access."""
    paths.atomic_json(registry_path(), {"version": 1, "accounts": rows})


def _safe_home(home):
    """Reject redirected or group-accessible account-home components."""
    root = paths.state_root() / "accounts"
    home = Path(home)
    if home.parent.parent != root or not home.name:
        raise ValueError("Account home is outside the private registry")
    base = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
    if base.is_symlink() or (base / "tafwid").is_symlink() or (base / "state").is_symlink():
        raise ValueError("Codex state path is redirected; account setup stopped")
    for part in (root, home.parent, home):
        if part.is_symlink() or not part.is_dir():
            raise ValueError("Account home is missing or redirected; repair setup before use")
        if part.stat().st_mode & 0o077:
            raise ValueError("Account home is accessible to other local users")
        if part.stat().st_uid != os.getuid():
            raise ValueError("Account home belongs to another local user")
    return home


def create(name: str, kind: str) -> dict:
    """Create a pending account with a distinct private CLI home."""
    if not isinstance(name, str) or not NAME.fullmatch(name) or name in RESERVED:
        raise ValueError("Use a unique lowercase account name starting with a letter (up to 32 characters)")
    if kind not in KINDS:
        raise ValueError("Account type must be personal or business")
    base = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
    if any(part.is_symlink() for part in (base, base / "tafwid", base / "state")):
        raise ValueError("Codex state path is redirected; account setup stopped")
    rows = _rows()
    if any(row.get("name") == name for row in rows):
        raise ValueError("That GPT account name already exists")
    account_id = str(uuid.uuid4())
    root = paths.state_root() / "accounts"
    for part in (paths.state_root(), root, root / "homes", root / "homes" / account_id):
        if part.is_symlink():
            raise ValueError("Private account path is redirected; setup stopped")
        part.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(part, 0o700)
    home = root / "homes" / account_id
    _safe_home(home)
    (home / "config.toml").write_text('cli_auth_credentials_store = "file"\n', encoding="utf-8")
    os.chmod(home / "config.toml", 0o600)
    row = {"id": account_id, "name": name, "kind": kind, "home": str(home), "status": "pending"}
    _save([*rows, row])
    return dict(row)


def get(name: str) -> dict:
    """Return one named account without reading its credential file."""
    for row in _rows():
        if row.get("name") == name:
            return dict(row)
    raise ValueError(f"No GPT account named {name} is set up")


def list_accounts() -> list[dict]:
    """List account metadata without checking login or reading credentials."""
    return [dict(row) for row in _rows()]


def validate_home(account: dict) -> Path:
    """Validate a saved account's private home before any CLI invocation."""
    return _safe_home(account["home"])


def mark_pending(name: str) -> dict:
    """Require renewed user confirmation before a login retry can be used."""
    row = get(name)
    rows = _rows()
    for item in rows:
        if item["id"] == row["id"]:
            item["status"] = "pending"
    _save(rows)
    return get(name)


def isolated_env(home: Path, base=None) -> dict[str, str]:
    """Select one CLI home and drop inherited identity or billing overrides."""
    source = os.environ if base is None else base
    env = {key: value for key, value in source.items()
           if not (key.startswith("OPENAI_") or key.startswith("CODEX_"))}
    for key in ("OPENAI_CERT_FILE", "OPENAI_CA_BUNDLE", "CODEX_CERT_FILE"):
        if key in source:
            env[key] = source[key]
    env["CODEX_HOME"] = str(home)
    return env


def check(account: dict) -> dict:
    """Check file-backed ChatGPT login via Codex without a model request.

    The status command reports a method, not the account identity, workspace,
    policy, or usage. CLI output is never returned on failure.
    """
    row = dict(account)
    home = _safe_home(row["home"])
    result = {**row, "login_method": "unavailable", "reason": "Codex ChatGPT sign-in is needed"}
    executable = shutil.which("codex")
    if executable is None:
        result["reason"] = "Install the Codex CLI, then retry account login"
        return result
    auth = home / "auth.json"
    if auth.is_symlink() or not auth.is_file():
        result["reason"] = "No file-based Codex login in this account home"
        return result
    if auth.stat().st_uid != os.getuid() or auth.stat().st_mode & 0o077:
        result["reason"] = "Codex credential file needs owner-only access; repair its permissions"
        return result
    try:
        proc = subprocess.run([executable, "login", "status"], env=isolated_env(home),
                              capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        result["reason"] = "Codex login check failed; retry sign-in"
        return result
    if proc.returncode != 0:
        result["reason"] = "Codex is not signed in here; retry sign-in"
    elif "chatgpt" in (proc.stdout + proc.stderr).lower() and "api key" not in (proc.stdout + proc.stderr).lower():
        result.update(login_method="chatgpt", reason="ChatGPT login method found; confirm the account and workspace")
    else:
        result["reason"] = "Login method is not clearly ChatGPT; retry Codex sign-in"
    return result


def confirm(name: str) -> dict:
    """Mark an account ready after the caller obtained user confirmation."""
    row = get(name)
    checked = check(row)
    if checked["login_method"] != "chatgpt":
        raise ValueError(checked["reason"])
    rows = _rows()
    for item in rows:
        if item["id"] == row["id"]:
            item["status"] = "ready"
    _save(rows)
    return get(name)
