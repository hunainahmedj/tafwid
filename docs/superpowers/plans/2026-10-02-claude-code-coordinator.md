# Claude Code Coordinator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tafwid installs in both Codex and Claude Code from this repository, and either host coordinates delegation with the same features.

**Architecture:** One plugin directory with two manifest pairs. A new `host.py` is the only module that reads coordinator identity; every other script asks it for the task ID, host name, and full-access signal. State moves to a host-neutral home with an explicit migration command, and one hooks file serves both hosts.

**Tech Stack:** Python 3.10+ standard library only, `unittest`, JSON manifests, `make test`.

**Spec:** `docs/superpowers/specs/2026-10-02-claude-code-coordinator-design.md`

## Global Constraints

- Python 3.10 or newer; no third-party packages.
- Tests use temporary homes and fake worker executables. No test makes a model request or touches the developer's installed plugin or real state.
- Existing Codex installations keep working with no user action. Legacy state is used in place until `settings.py migrate` is run.
- Tafwid never moves, merges, or creates state on a read.
- Run `make test` for runtime changes and `python3 scripts/check_package.py` for packaging changes.
- All paths below are relative to the repository root. `S` means `plugins/tafwid/skills/delegate`.
- Commit messages follow the existing style and end with `(TAF-6)`.
- Version `0.4.0` in `VERSION`, `.codex-plugin/plugin.json`, and `.claude-plugin/plugin.json`.
- Claude Code identity signal: `CLAUDE_CODE_SESSION_ID`. Codex: `CODEX_THREAD_ID`, then legacy `CODEX_SESSION_ID`.
- Hook command form, exactly: `bash -c 'exec python3 "${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/delegate/scripts/completion_hook.py" <action>'`.
- No machine-specific absolute paths in any committed file; `check_package.py` rejects them.

## Review Focus

1. Both hosts' identity variables are present (for example Codex started from a Claude Code terminal). Expect a clear error naming `TAFWID_HOST`, never a silent pick. Pinned in Task 2.
2. A Claude worker inherits the coordinator's `CLAUDE_CODE_SESSION_ID`. Expect both launchers to strip identity variables. Pinned in Task 2.
3. `~/.tafwid` already exists without a `state` directory. Expect legacy state to stay in use and `migrate` to succeed. Pinned in Tasks 3 and 7.
4. Migration fails after the move (malformed account registry). Expect the source directory restored byte-for-byte. Pinned in Task 7.
5. Claude Code hooks are disabled. Expect `arm` to report `unavailable` and `inherit` to resolve to `scoped`. Pinned in Tasks 5 and 6.

## File Structure

| File | Responsibility |
| --- | --- |
| `S/scripts/host.py` (new) | Detect the coordinator, return its task ID, display name, full-access signal; hooks-seen marker; worker environment scrub |
| `S/scripts/migration.py` (new) | Move legacy state to the neutral home with rollback |
| `S/scripts/paths.py` | Resolve the neutral or legacy state root |
| `S/scripts/session.py`, `settings.py`, `wait.py`, `delegate.py`, `completion_hook.py`, `run_state.py`, `accounts.py`, `connections.py`, `codex_cli.py` | Call `host` instead of reading `CODEX_*`; neutral wording |
| `plugins/tafwid/hooks/hooks.json` | One hooks file for both hosts |
| `.claude-plugin/marketplace.json`, `plugins/tafwid/.claude-plugin/plugin.json` (new) | Claude Code packaging |
| `scripts/check_package.py` | Validate both manifest pairs, versions, hook form |
| `S/tests/test_host.py`, `test_migration.py` (new); other tests updated | Offline coverage |

---

### Task 1: Record the work and isolate test environments

Tests currently isolate state with `CODEX_HOME` only. After this plan, state defaults to `~/.tafwid`, and host detection reads `CLAUDE_CODE_SESSION_ID`, which is present when a developer runs tests from Claude Code. Every test environment therefore sets `TAFWID_HOME` and `TAFWID_HOST` first. Setting `TAFWID_HOME` to `<CODEX_HOME>/tafwid` keeps every existing path assertion (`<home>/tafwid/state/...`) valid.

**Files:**
- Modify: `docs/01-project/backlog.md`
- Modify: every file under `S/tests/` listed below

**Interfaces:**
- Produces: all test environments contain `TAFWID_HOME=<CODEX_HOME>/tafwid` and `TAFWID_HOST=codex`.

- [ ] **Step 1: Add TAF-6 to the backlog**

In `docs/01-project/backlog.md` change `Next ID: TAF-6` to `Next ID: TAF-7`, and replace the line `No active implementation items.` with:

```markdown
- TAF-6 Make Claude Code a full coordinator alongside Codex: host adapter, neutral state home, shared hooks, Claude Code packaging. See the [spec](../superpowers/specs/2026-10-02-claude-code-coordinator-design.md).
```

- [ ] **Step 2: Add the two variables to each test environment**

| File | Existing environment | Add |
| --- | --- | --- |
| `test_account_cli.py` | `self.env = {**os.environ, "CODEX_HOME": str(self.root / "ordinary"),` | `"TAFWID_HOME": str(self.root / "ordinary" / "tafwid"), "TAFWID_HOST": "codex",` |
| `test_accounts.py` | `{"CODEX_HOME": str(self.home)}` | `"TAFWID_HOME": str(self.home / "tafwid"), "TAFWID_HOST": "codex"` |
| `test_completion_hook.py` | `{"CODEX_HOME": str(self.root), "CODEX_THREAD_ID": TASK}` | `"TAFWID_HOME": str(self.root / "tafwid"), "TAFWID_HOST": "codex"` |
| `test_connections.py` | `{"CODEX_HOME": str(self.home)}` | `"TAFWID_HOME": str(self.home / "tafwid"), "TAFWID_HOST": "codex"` |
| `test_delegate.py` | `self.env["CODEX_HOME"] = str(self.root / "codex")` | `self.env["TAFWID_HOME"] = str(self.root / "codex" / "tafwid")` and `self.env["TAFWID_HOST"] = "codex"` |
| `test_delegate_gpt.py` | `self.env = {**os.environ, "CODEX_HOME": str(self.root / "normal"),` | `"TAFWID_HOME": str(self.root / "normal" / "tafwid"), "TAFWID_HOST": "codex",` |
| `test_harnesses.py` | `"CODEX_HOME": str(self.root), "CODEX_THREAD_ID": TASK, "PATH": "",` | `"TAFWID_HOME": str(self.root / "tafwid"), "TAFWID_HOST": "codex",` |
| `test_paths.py` setUp | `{"CODEX_HOME": str(self.home)}` | `"TAFWID_HOME": str(self.home / "tafwid"), "TAFWID_HOST": "codex"` |
| `test_paths.py` conflict test | `{"CODEX_HOME": str(home)}` | `"TAFWID_HOME": str(home / "tafwid")` |
| `test_session.py` | `self.env["CODEX_HOME"] = str(self.home)` | `self.env["TAFWID_HOME"] = str(self.home / "tafwid")` and `self.env["TAFWID_HOST"] = "codex"` |
| `test_settings.py` | `{'CODEX_HOME': self.temp.name}` | `'TAFWID_HOME': str(Path(self.temp.name) / 'tafwid'), 'TAFWID_HOST': 'codex'` |
| `test_wait.py` | `{"CODEX_HOME": str(self.root), "CODEX_THREAD_ID": TASK}` | `"TAFWID_HOME": str(self.root / "tafwid"), "TAFWID_HOST": "codex"` |

Subprocess environments in these files are built from `os.environ` or `self.env`, so they inherit both values.

- [ ] **Step 3: Run the suite**

Run: `make test`
Expected: all 152 tests pass; behavior is unchanged because nothing reads the new variables yet.

- [ ] **Step 4: Commit**

```bash
git add docs/01-project/backlog.md docs/superpowers plugins/tafwid/skills/delegate/tests
git commit -m "test: isolate Tafwid home and host in fixtures (TAF-6)"
```

---

### Task 2: Host adapter

**Files:**
- Create: `S/scripts/host.py`
- Create: `S/tests/test_host.py`
- Modify: `S/scripts/session.py` (`current_task_id`, messages)
- Modify: `S/scripts/accounts.py` (`isolated_env`)
- Modify: `S/scripts/delegate.py` (Claude worker `Popen`)
- Modify: `S/tests/test_delegate.py`, `S/tests/test_delegate_gpt.py` (fixtures record identity variables)

**Interfaces:**
- Produces:
  - `host.detect(env=None) -> "codex" | "claude" | None`; raises `ValueError` when both hosts' signals are present without `TAFWID_HOST`, or `TAFWID_HOST` is invalid.
  - `host.task_id(env=None) -> str | None`; raises `ValueError` on a malformed ID.
  - `host.display_name(env=None) -> str` (`"Codex"`, `"Claude Code"`, or `"the coordinator"`).
  - `host.for_hook(env=None) -> "codex" | "claude"`.
  - `host.worker_env(base=None) -> dict[str, str]`.
  - `host.IDENTITY_VARIABLES: tuple[str, ...]`.
  - `host.seen_path(task_id) -> Path`, `host.record_seen(task_id, permission_mode) -> None`, `host.seen(task_id) -> dict | None`.
  - `host.full_access(env=None) -> bool`.

- [ ] **Step 1: Write the failing tests**

Create `S/tests/test_host.py`:

```python
"""Coordinator detection must be explicit and never guess between hosts."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import host

A = "00000000-0000-4000-8000-000000000001"
B = "00000000-0000-4000-8000-000000000002"


class HostTests(unittest.TestCase):
    def test_each_host_is_detected_from_its_own_signal(self):
        self.assertEqual(host.detect({"CODEX_THREAD_ID": A}), "codex")
        self.assertEqual(host.detect({"CODEX_SESSION_ID": A}), "codex")
        self.assertEqual(host.detect({"CLAUDE_CODE_SESSION_ID": A}), "claude")
        self.assertIsNone(host.detect({}))
        self.assertEqual(host.task_id({"CODEX_THREAD_ID": A, "CODEX_SESSION_ID": B}), A)
        self.assertEqual(host.task_id({"CLAUDE_CODE_SESSION_ID": B}), B)
        self.assertIsNone(host.task_id({}))

    def test_both_signals_fail_without_guessing(self):
        env = {"CODEX_THREAD_ID": A, "CLAUDE_CODE_SESSION_ID": B}
        with self.assertRaisesRegex(ValueError, "TAFWID_HOST"):
            host.detect(env)
        with self.assertRaisesRegex(ValueError, "TAFWID_HOST"):
            host.task_id(env)
        self.assertEqual(host.display_name(env), "the coordinator")

    def test_override_selects_one_host_and_ignores_the_other_signal(self):
        env = {"CODEX_THREAD_ID": A, "CLAUDE_CODE_SESSION_ID": B}
        self.assertEqual(host.task_id({**env, "TAFWID_HOST": "codex"}), A)
        self.assertEqual(host.task_id({**env, "TAFWID_HOST": "claude"}), B)
        self.assertIsNone(host.task_id({"TAFWID_HOST": "codex", "CLAUDE_CODE_SESSION_ID": B}))
        with self.assertRaisesRegex(ValueError, "TAFWID_HOST"):
            host.detect({"TAFWID_HOST": "other"})

    def test_malformed_identity_is_rejected_with_the_host_name(self):
        with self.assertRaisesRegex(ValueError, "Invalid Codex task identity"):
            host.task_id({"CODEX_THREAD_ID": "../../outside"})
        with self.assertRaisesRegex(ValueError, "Invalid Claude Code task identity"):
            host.task_id({"CLAUDE_CODE_SESSION_ID": "not-a-uuid"})

    def test_display_names(self):
        self.assertEqual(host.display_name({"CODEX_THREAD_ID": A}), "Codex")
        self.assertEqual(host.display_name({"CLAUDE_CODE_SESSION_ID": A}), "Claude Code")
        self.assertEqual(host.display_name({}), "the coordinator")

    def test_hook_host_uses_the_plugin_root_variable(self):
        self.assertEqual(host.for_hook({"CLAUDE_PLUGIN_ROOT": "/plugin"}), "claude")
        self.assertEqual(host.for_hook({"PLUGIN_ROOT": "/plugin"}), "codex")
        self.assertEqual(host.for_hook({}), "codex")

    def test_worker_environment_drops_every_identity_variable(self):
        base = {"PATH": "/bin", "CODEX_THREAD_ID": A, "CODEX_SESSION_ID": A,
                "CLAUDE_CODE_SESSION_ID": B, "TAFWID_HOST": "claude", "CLAUDE_CONFIG_DIR": "/c"}
        self.assertEqual(host.worker_env(base), {"PATH": "/bin", "CLAUDE_CONFIG_DIR": "/c"})


class HookSeenTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        env = patch.dict(os.environ, {"CODEX_HOME": str(self.root), "TAFWID_HOME": str(self.root / "tafwid")})
        env.start()
        self.addCleanup(env.stop)

    def test_marker_round_trip_is_private_and_task_bound(self):
        self.assertIsNone(host.seen(A))
        self.assertIsNone(host.seen(None))
        host.record_seen(A, "bypassPermissions")
        self.assertEqual(host.seen(A)["permission_mode"], "bypassPermissions")
        self.assertEqual(host.seen_path(A).stat().st_mode & 0o777, 0o600)
        self.assertIsNone(host.seen(B))
        host.seen_path(A).write_text('{"version": 1, "thread_id": "other"}')
        self.assertIsNone(host.seen(A))
        host.seen_path(A).write_text("not json")
        self.assertIsNone(host.seen(A))

    def test_full_access_signal_per_host(self):
        self.assertTrue(host.full_access({"CODEX_THREAD_ID": A, "CODEX_PERMISSION_PROFILE": ":danger-full-access"}))
        self.assertFalse(host.full_access({"CODEX_THREAD_ID": A, "CODEX_PERMISSION_PROFILE": ":workspace-write"}))
        self.assertFalse(host.full_access({"CODEX_PERMISSION_PROFILE": ":danger-full-access"}))
        claude = {"CLAUDE_CODE_SESSION_ID": A}
        self.assertFalse(host.full_access(claude))
        host.record_seen(A, "default")
        self.assertFalse(host.full_access(claude))
        host.record_seen(A, "bypassPermissions")
        self.assertTrue(host.full_access(claude))
        self.assertFalse(host.full_access({"CLAUDE_CODE_SESSION_ID": B}))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s plugins/tafwid/skills/delegate/tests -p test_host.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'host'`.

- [ ] **Step 3: Write `S/scripts/host.py`**

```python
"""Identify the coordinating host and its task for Tafwid's scripts.

Tafwid is coordinated by Codex or Claude Code. This is the only module that
reads their identity signals. TAFWID_HOST=codex|claude forces one host for
tests and recovery; with it set, only that host's signal is read.
"""
import json
import os
import time
import uuid

import paths

HOSTS = ("codex", "claude")
NAMES = {"codex": "Codex", "claude": "Claude Code"}
SIGNALS = {"codex": ("CODEX_THREAD_ID", "CODEX_SESSION_ID"),
           "claude": ("CLAUDE_CODE_SESSION_ID",)}
IDENTITY_VARIABLES = SIGNALS["codex"] + SIGNALS["claude"] + ("TAFWID_HOST",)


def _signal(name, env):
    """Return the first nonempty identity value for one host."""
    for key in SIGNALS[name]:
        if env.get(key):
            return env[key]
    return None


def detect(env=None):
    """Return "codex", "claude", or None; never choose between two hosts."""
    env = os.environ if env is None else env
    forced = env.get("TAFWID_HOST")
    if forced:
        if forced not in HOSTS:
            raise ValueError("TAFWID_HOST must be codex or claude")
        return forced
    found = [name for name in HOSTS if _signal(name, env)]
    if len(found) > 1:
        raise ValueError("Both Codex and Claude Code task identities are present; "
                         "set TAFWID_HOST to codex or claude")
    return found[0] if found else None


def task_id(env=None):
    """Return the coordinator's task UUID, or None when there is no identity.

    A malformed value raises ValueError so it cannot select an unintended file.
    """
    env = os.environ if env is None else env
    name = detect(env)
    value = _signal(name, env) if name else None
    if not value:
        return None
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise ValueError(f"Invalid {NAMES[name]} task identity; cannot select delegation state") from None


def display_name(env=None):
    """Name the coordinator for messages without raising."""
    try:
        return NAMES.get(detect(env), "the coordinator")
    except ValueError:
        return "the coordinator"


def for_hook(env=None):
    """Identify the host inside a hook process, which lacks task variables."""
    env = os.environ if env is None else env
    return "claude" if env.get("CLAUDE_PLUGIN_ROOT") else "codex"


def worker_env(base=None):
    """Copy an environment without coordinator identity, so a worker is never one."""
    base = os.environ if base is None else base
    return {key: value for key, value in base.items() if key not in IDENTITY_VARIABLES}


def seen_path(task_id):
    """Choose the private marker recording that this task's hooks ran."""
    return paths.state_root() / "hook-seen" / (task_id + ".json")


def record_seen(task_id, permission_mode):
    """Record that Claude Code ran Tafwid's prompt hook, with its permission mode."""
    paths.atomic_json(seen_path(task_id), {
        "version": 1, "thread_id": task_id, "seen_at": time.time(),
        "permission_mode": permission_mode if isinstance(permission_mode, str) else None})


def seen(task_id):
    """Return this task's hooks-seen marker, or None when missing or invalid."""
    if not task_id:
        return None
    try:
        data = json.loads(seen_path(task_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("version") != 1 or data.get("thread_id") != task_id:
        return None
    return data


def full_access(env=None):
    """Report whether the coordinator currently confirms full access."""
    env = os.environ if env is None else env
    name = detect(env)
    if name == "codex":
        return env.get("CODEX_PERMISSION_PROFILE") == ":danger-full-access"
    if name == "claude":
        marker = seen(task_id(env))
        return bool(marker) and marker.get("permission_mode") == "bypassPermissions"
    return False
```

- [ ] **Step 4: Route `session.current_task_id` through the adapter**

In `S/scripts/session.py` add `import host` beside the other imports and replace the body of `current_task_id`:

```python
def current_task_id():
    """Return the coordinator's task UUID, or None when no identity is available.

    Malformed values raise ValueError so they cannot select an unintended state file.
    """
    return host.task_id()
```

Remove the now-unused `import uuid` from `session.py`. In `set_enabled`, change the message to `"No task identity from the coordinator; cannot save a session switch. Use an explicit one-shot task instead."`.

- [ ] **Step 5: Strip identity from worker environments**

In `S/scripts/accounts.py` add `import host` and change the comprehension in `isolated_env`:

```python
    env = {key: value for key, value in source.items()
           if not (key.startswith("OPENAI_") or key.startswith("CODEX_")
                   or key in host.IDENTITY_VARIABLES)}
```

In `S/scripts/delegate.py` add `import host` and pass the scrubbed environment to the Claude worker:

```python
            proc = subprocess.Popen(command, cwd=cwd, stdin=stdin, stdout=stdout, stderr=stderr,
                                    env=host.worker_env(), start_new_session=True)
```

- [ ] **Step 6: Pin the worker environment in the launcher tests**

In `S/tests/test_delegate.py`, in the `FAKE` fixture change the `received.json` line to:

```python
Path("received.json").write_text(json.dumps({"args": sys.argv[1:], "prompt": prompt,
    "identity": {k: os.environ.get(k) for k in ("CODEX_THREAD_ID", "CODEX_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "TAFWID_HOST")}}))
```

and add to `DelegationTests`:

```python
    def test_worker_environment_has_no_coordinator_identity(self):
        self.env["CLAUDE_CODE_SESSION_ID"] = "00000000-0000-4000-8000-000000000009"
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        identity = json.loads((self.cwd / "received.json").read_text())["identity"]
        self.assertEqual(set(identity.values()), {None})
```

In `S/tests/test_delegate_gpt.py`, in `FAKE` add `"identity": {k: os.environ.get(k) for k in ("CODEX_THREAD_ID", "CLAUDE_CODE_SESSION_ID", "TAFWID_HOST")},` to the JSON written to `CALLS`, and add a test that runs one successful assignment with the file's existing helper and asserts `set(json.loads(self.calls.read_text())["identity"].values()) == {None}`.

- [ ] **Step 7: Run the suite**

Run: `make test`
Expected: PASS, including `test_host` and the two new launcher tests.

- [ ] **Step 8: Commit**

```bash
git add plugins/tafwid/skills/delegate
git commit -m "feat: detect the coordinator through a host adapter (TAF-6)"
```

---

### Task 3: Host-neutral state home

**Files:**
- Modify: `S/scripts/paths.py`
- Modify: `S/scripts/accounts.py` (`_safe_home`, `create`)
- Modify: `S/scripts/session.py` (`status`), `S/scripts/settings.py` (`main`)
- Test: `S/tests/test_paths.py`

**Interfaces:**
- Produces:
  - `paths.neutral_root() -> Path` (`$TAFWID_HOME/state`, default `~/.tafwid/state`).
  - `paths.legacy_roots() -> tuple[Path, Path, Path]`.
  - `paths.state_root() -> Path` (unchanged signature).
  - `paths.legacy_in_use() -> Path | None`.
  - `paths.migration_notice() -> dict | None` with keys `available`, `from`, `to`, `command`.

- [ ] **Step 1: Write the failing tests**

Add to `StatePathsTests` in `S/tests/test_paths.py` (add `import paths` beside the other imports):

```python
    def test_default_home_is_neutral_and_independent_of_codex_home(self):
        user = self.home / "user"
        with patch.dict(os.environ, {"HOME": str(user), "CODEX_HOME": str(self.home / "codex")}):
            os.environ.pop("TAFWID_HOME")
            self.assertEqual(paths.state_root(), user / ".tafwid" / "state")
            self.assertIsNone(paths.legacy_in_use())
            self.assertIsNone(paths.migration_notice())
        self.assertFalse(user.exists())

    def test_single_legacy_directory_is_used_in_place_with_a_notice(self):
        user, codex = self.home / "user", self.home / "codex"
        legacy = codex / "tafwid" / "state"
        legacy.mkdir(parents=True)
        (user / ".tafwid").mkdir(parents=True)  # exists without a state directory
        with patch.dict(os.environ, {"HOME": str(user), "CODEX_HOME": str(codex)}):
            os.environ.pop("TAFWID_HOME")
            self.assertEqual(paths.state_root(), legacy)
            self.assertEqual(paths.legacy_in_use(), legacy)
            notice = paths.migration_notice()
            self.assertEqual(notice["from"], str(legacy))
            self.assertEqual(notice["to"], str(user / ".tafwid" / "state"))
            self.assertIn("settings.py migrate", notice["command"])
        self.assertFalse((user / ".tafwid" / "state").exists())

    def test_neutral_and_legacy_together_fail_without_picking(self):
        user, codex = self.home / "user", self.home / "codex"
        (codex / "state" / "tafwid").mkdir(parents=True)
        (user / ".tafwid" / "state").mkdir(parents=True)
        with patch.dict(os.environ, {"HOME": str(user), "CODEX_HOME": str(codex)}):
            os.environ.pop("TAFWID_HOME")
            with self.assertRaisesRegex(ValueError, "state directories"):
                paths.state_root()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s plugins/tafwid/skills/delegate/tests -p test_paths.py -v`
Expected: the three new tests FAIL with `AttributeError: module 'paths' has no attribute 'legacy_in_use'` or a wrong path.

- [ ] **Step 3: Rewrite the resolver in `S/scripts/paths.py`**

Replace the module docstring and `state_root` with:

```python
"""Shared state location and private JSON writes for Tafwid's scripts.

State lives in a host-neutral home, $TAFWID_HOME/state (default ~/.tafwid/state),
shared by Codex and Claude Code coordinators. An existing installation under the
Codex home is used in place until `settings.py migrate` moves it.
"""

import json
import os
import tempfile
from pathlib import Path


def neutral_root():
    """Return the host-neutral state directory without creating it."""
    return Path(os.environ.get("TAFWID_HOME") or Path.home() / ".tafwid").expanduser() / "state"


def legacy_roots():
    """Return the state directories older releases used under the Codex home."""
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
    return (home / "tafwid" / "state", home / "state" / "tafwid", home / "state" / "claude-delegate")


def state_root():
    """Resolve the state directory without creating or moving files.

    Use the neutral directory, or the single legacy directory when it is the
    only one that exists. Several candidates raise ValueError rather than
    choosing between conflicting histories.
    """
    neutral = neutral_root()
    legacy = [path for path in legacy_roots() if path != neutral and path.exists()]
    if len(legacy) > 1 or (legacy and neutral.exists()):
        raise ValueError(
            "Multiple Tafwid state directories exist. Back up and reconcile them "
            "before launching; Tafwid will not merge histories or permissions "
            "automatically."
        )
    return legacy[0] if legacy else neutral


def legacy_in_use():
    """Return the legacy directory currently serving as state, or None."""
    root = state_root()
    return None if root == neutral_root() else root


def migration_notice():
    """Describe the available migration for status output, or None."""
    legacy = legacy_in_use()
    if legacy is None:
        return None
    return {"available": True, "from": str(legacy), "to": str(neutral_root()),
            "command": "settings.py migrate"}
```

`atomic_json` is unchanged.

- [ ] **Step 4: Point the account redirect checks at the active root**

In `S/scripts/accounts.py` add this helper above `_safe_home`:

```python
def _reject_redirected_root():
    """Stop when the state directory or its Tafwid parents are symlinks."""
    root = paths.state_root()
    parts = [root, root.parent]
    if root.parent.parent != Path.home():
        parts.append(root.parent.parent)
    if any(part.is_symlink() for part in parts):
        raise ValueError("Tafwid state path is redirected; account setup stopped")
```

In `_safe_home`, replace the three lines that compute `base` and raise `"Codex state path is redirected; account setup stopped"` with `_reject_redirected_root()`. In `create`, replace the equivalent three lines with `_reject_redirected_root()`.

- [ ] **Step 5: Report the migration notice from the two read commands**

In `S/scripts/session.py`, `status()` becomes:

```python
    result = connections.describe(current_task_id())
    notice = paths.migration_notice()
    if notice:
        result["migration"] = notice
    return result
```

In `S/scripts/settings.py` `main()`, after `result` is computed for `show`, add:

```python
        if args.action == "show" and paths.migration_notice():
            result = {**result, "migration": paths.migration_notice()}
```

- [ ] **Step 6: Run the suite**

Run: `make test`
Expected: PASS. Existing path tests keep passing because `TAFWID_HOME` equals `<CODEX_HOME>/tafwid` in fixtures.

- [ ] **Step 7: Commit**

```bash
git add plugins/tafwid/skills/delegate
git commit -m "feat: resolve a host-neutral state home (TAF-6)"
```

---

### Task 4: Host-neutral run ownership

**Files:**
- Modify: `S/scripts/run_state.py`, `S/scripts/delegate.py`, `S/scripts/wait.py`, `S/scripts/completion_hook.py`
- Test: `S/tests/test_delegate.py`, `S/tests/test_wait.py`, `S/tests/test_paths.py`

**Interfaces:**
- Consumes: `host.detect()`.
- Produces: `run_state.owner(record: dict) -> str | None`. New run records and summaries contain `coordinator_task_id` and `coordinator_host`; they no longer contain `codex_thread_id`.

- [ ] **Step 1: Update the tests first**

In `S/tests/test_delegate.py`:
- Line asserting `json.loads(stdout)["codex_thread_id"]` becomes `["coordinator_task_id"]`, followed by `self.assertEqual(json.loads(stdout)["coordinator_host"], "codex")`.
- Line asserting `record["codex_thread_id"]` becomes `record["coordinator_task_id"]`.
- `del summary["codex_thread_id"]` becomes `del summary["coordinator_task_id"]`.
- Keep the legacy summary in `test_retired_worker_cannot_resume_as_claude` unchanged.
- Add a test that resumes from a summary carrying only the legacy field:

```python
    def test_resume_accepts_a_legacy_ownership_field(self):
        first = self.run_cli()
        self.assertEqual(first.returncode, 0, first.stderr)
        path = self.out / "summary.json"
        summary = json.loads(path.read_text())
        summary["codex_thread_id"] = summary.pop("coordinator_task_id")
        summary.pop("coordinator_host")
        path.write_text(json.dumps(summary))
        previous, self.out = self.out, self.root / "resumed-legacy"
        resumed = self.run_cli("--resume-from", str(previous))
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
```

In `S/tests/test_wait.py` the assertion on `json.loads(before)["codex_thread_id"]` becomes `["coordinator_task_id"]`. `S/tests/test_paths.py` keeps its legacy `codex_thread_id` record; it proves old history stays listed.

- [ ] **Step 2: Run to verify failure**

Run: `make test`
Expected: the edited assertions FAIL with `KeyError: 'coordinator_task_id'`.

- [ ] **Step 3: Implement**

In `S/scripts/run_state.py` add `import host` and:

```python
def owner(record):
    """Return the coordinating task that owns a run, reading older records too."""
    return record.get("coordinator_task_id") or record.get("codex_thread_id")
```

In `list_runs`, the filter becomes `if thread_id and owner(row) != thread_id:`. In `Tracker.__init__`, replace `"codex_thread_id": task_id,` with `"coordinator_task_id": task_id, "coordinator_host": host.detect(),`.

In `S/scripts/delegate.py`:
- Both summaries replace `"codex_thread_id": task_id` with `"coordinator_task_id": task_id, "coordinator_host": host.detect()`.
- The resume check becomes:

```python
        if not run_state.owner(previous) or run_state.owner(previous) != task_id:
            raise ValueError("Resume has missing or different task ownership; start a fresh worker")
```

In `S/scripts/wait.py`, `record.get("codex_thread_id") != task_id` becomes `registry.owner(record) != task_id`. In `S/scripts/completion_hook.py` `arm`, `record.get("codex_thread_id") != task_id` becomes `run_state.owner(record) != task_id`.

- [ ] **Step 4: Run the suite**

Run: `make test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/tafwid/skills/delegate
git commit -m "feat: record run ownership by coordinator task (TAF-6)"
```

---

### Task 5: Permissions follow the coordinator

**Files:**
- Modify: `S/scripts/settings.py` (`resolve`)
- Test: `S/tests/test_settings.py`

**Interfaces:**
- Consumes: `host.full_access()`, `host.display_name()`, `host.record_seen()`.
- Produces: `settings.resolve()` returns `coordinator_full_access` in place of `codex_full_access`.

- [ ] **Step 1: Write the failing test**

Add to `SettingsTests` in `S/tests/test_settings.py` (add `import host` beside `import settings`):

```python
    def test_inherit_follows_each_coordinator(self):
        config = {**settings.defaults(), 'permission_policy': 'inherit'}
        with patch.dict(os.environ, {'CODEX_THREAD_ID': A, 'CODEX_PERMISSION_PROFILE': ':danger-full-access'}):
            result = settings.resolve(config=config)
            self.assertEqual((result['effective'], result['coordinator_full_access']), ('full', True))
            self.assertIn('Codex', result['reason'])
            self.assertNotIn('codex_full_access', result)
        claude = {'TAFWID_HOST': 'claude', 'CLAUDE_CODE_SESSION_ID': B}
        with patch.dict(os.environ, claude):
            self.assertEqual(settings.resolve(config=config)['effective'], 'scoped')  # hooks never ran
            host.record_seen(B, 'acceptEdits')
            self.assertEqual(settings.resolve(config=config)['effective'], 'scoped')
            host.record_seen(B, 'bypassPermissions')
            result = settings.resolve(config=config)
            self.assertEqual((result['effective'], result['claude_mode']), ('full', 'bypassPermissions'))
            self.assertIn('Claude Code', result['reason'])
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m unittest discover -s plugins/tafwid/skills/delegate/tests -p test_settings.py -v`
Expected: FAIL with `KeyError: 'coordinator_full_access'`.

- [ ] **Step 3: Implement**

In `S/scripts/settings.py` add `import host` and replace the tail of `resolve`:

```python
    parent_full = host.full_access()
    name = host.display_name()
    effective = "full" if policy == "full" or (policy == "inherit" and parent_full) else "scoped"
    reason = {"full": "Full access selected by the user", "scoped": "Scoped command allowances selected"}.get(policy)
    if policy == "inherit":
        reason = (f"{name} currently reports full access" if parent_full else
                  f"Full access is not confirmed by {name}; using scoped allowances")
    return {"policy": policy, "effective": effective,
            "claude_mode": "bypassPermissions" if effective == "full" else "dontAsk",
            "source": "override" if override is not None else "settings",
            "coordinator_full_access": parent_full, "reason": reason}
```

Update the docstring to `"""Map the selected policy to worker permissions using the coordinator's live signal."""`.

- [ ] **Step 4: Run the suite**

Run: `make test`
Expected: PASS, including the existing `inherit` launcher tests in `test_delegate.py`.

- [ ] **Step 5: Commit**

```bash
git add plugins/tafwid/skills/delegate
git commit -m "feat: resolve inherited permissions per coordinator (TAF-6)"
```

---

### Task 6: Completion hook on both hosts

**Files:**
- Modify: `S/scripts/completion_hook.py`, `S/scripts/wait.py`, `plugins/tafwid/hooks/hooks.json`
- Test: `S/tests/test_completion_hook.py`

**Interfaces:**
- Consumes: `host.detect()`, `host.for_hook()`, `host.task_id()`, `host.seen()`, `host.record_seen()`.
- Produces: `wait.wait_for_runs(..., task_id=None)`; `completion_hook.hook_status()` works on both hosts; `completion_hook.disarm(event)` records the hooks-seen marker on Claude Code.

- [ ] **Step 1: Write the failing tests**

Add to `S/tests/test_completion_hook.py` (add `import subprocess` and `import host`):

```python
PLUGIN = Path(__file__).resolve().parents[3]


class ClaudeHookTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.env = {"CODEX_HOME": str(self.root), "TAFWID_HOME": str(self.root / "tafwid"),
                    "TAFWID_HOST": "claude", "CLAUDE_CODE_SESSION_ID": TASK}
        environment = patch.dict(os.environ, self.env)
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop("CODEX_THREAD_ID", None)

    def worker(self, name="worker", task=TASK):
        output = self.root / name
        output.mkdir()
        return run_state.Tracker(output, task, "session", name, {}, str(self.root))

    def prompt_event(self, mode="default"):
        return {"session_id": TASK, "hook_event_name": "UserPromptSubmit", "permission_mode": mode}

    def test_arm_is_unavailable_until_the_prompt_hook_has_run(self):
        with self.worker() as worker:
            worker.running(123)
            result = completion_hook.arm([worker.id])
            self.assertEqual(result["event"], "unavailable")
            self.assertIn("Claude Code", result["reason"])
            self.assertFalse(completion_hook.arm_path(TASK).exists())
            with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(PLUGIN)}):
                completion_hook.disarm(self.prompt_event("acceptEdits"))
            self.assertEqual(host.seen(TASK)["permission_mode"], "acceptEdits")
            self.assertEqual(completion_hook.arm([worker.id])["event"], "active")

    def test_codex_prompt_hook_records_no_marker(self):
        completion_hook.disarm(self.prompt_event())  # no CLAUDE_PLUGIN_ROOT: a Codex hook process
        self.assertIsNone(host.seen(TASK))

    def test_stop_resumes_a_claude_session_without_codex_identity(self):
        host.record_seen(TASK, "default")
        with self.worker() as worker:
            worker.finish({"status": "completed"})
            self.assertEqual(completion_hook.arm([worker.id])["event"], "active")
            hook_env = {k: v for k, v in os.environ.items() if k not in host.IDENTITY_VARIABLES}
            with patch.dict(os.environ, {**hook_env, "CLAUDE_PLUGIN_ROOT": str(PLUGIN)}, clear=True):
                result = completion_hook.on_stop({"session_id": TASK, "stop_hook_active": False})
            self.assertEqual(result["decision"], "block")
            self.assertIn(worker.id, result["reason"])

    def test_packaged_hook_command_runs_with_either_plugin_root_variable(self):
        commands = json.loads((PLUGIN / "hooks" / "hooks.json").read_text())["hooks"]
        command = commands["UserPromptSubmit"][0]["hooks"][0]["command"]
        base = {k: v for k, v in os.environ.items() if k not in host.IDENTITY_VARIABLES}
        for variable, expected in (("CLAUDE_PLUGIN_ROOT", "default"), ("PLUGIN_ROOT", None)):
            with self.subTest(variable=variable):
                host.seen_path(TASK).unlink(missing_ok=True)
                run = subprocess.run(command, shell=True, env={**base, variable: str(PLUGIN)},
                                     input=json.dumps(self.prompt_event()), text=True,
                                     capture_output=True, timeout=10)
                self.assertEqual(run.returncode, 0, run.stderr)
                marker = host.seen(TASK)
                self.assertEqual(marker and marker["permission_mode"], expected)
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m unittest discover -s plugins/tafwid/skills/delegate/tests -p test_completion_hook.py -v`
Expected: the four new tests FAIL (Codex app-server lookup, missing marker, old command form).

- [ ] **Step 3: Let `wait_for_runs` take the task explicitly**

In `S/scripts/wait.py` change the signature and the identity lines:

```python
def wait_for_runs(run_dirs=(), timeout=MAX_WAIT_SECONDS, *, run_ids=(), watch_keys=None, task_id=None):
```

```python
    task_id = task_id or session.current_task_id()
    if not task_id:
        raise ValueError("No task identity from the coordinator; use the original launcher process handle")
```

Add to the docstring: `Hook processes pass task_id because they carry no task environment.`

- [ ] **Step 4: Update `S/scripts/completion_hook.py`**

Add `import host`. Rename the existing `hook_status` to `_codex_hook_status` (body unchanged) and add:

```python
def hook_status():
    """Return whether this chat's completion hooks can resume the coordinator."""
    if host.detect() == "claude":
        if host.seen(host.task_id()):
            return {"active": True}
        return {"active": False, "reason": "Tafwid hooks have not run in this Claude Code session; "
                "check that the plugin is enabled and hooks are not disabled"}
    return _codex_hook_status()
```

In `arm`, change the missing-identity message to `"No chat identity from the coordinator"`.

Replace `disarm`:

```python
def disarm(event):
    """Clear this chat's pending handoff; on Claude Code, record that hooks run."""
    task_id = event.get("session_id")
    try:
        task_id = str(uuid.UUID(task_id))
    except (TypeError, ValueError):
        return
    arm_path(task_id).unlink(missing_ok=True)
    if host.for_hook() == "claude":
        host.record_seen(task_id, event.get("permission_mode"))
```

In `on_stop`, delete the line `os.environ["CODEX_THREAD_ID"] = task_id` and pass the task to the waiter:

```python
        result = wait.wait_for_runs(run_ids=pending, task_id=task_id,
                                    timeout=min(wait.MAX_WAIT_SECONDS, max(0, deadline - time.monotonic())))
```

Update the module docstring's first line to `"""Arm a one-time Stop hook to wait for this chat's Tafwid workers.` and the last docstring line to `The hook waits locally and resumes the coordinator only for completion or attention.`

- [ ] **Step 5: Rewrite `plugins/tafwid/hooks/hooks.json`**

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash -c 'exec python3 \"${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/delegate/scripts/completion_hook.py\" hook'",
            "timeout": 1800,
            "statusMessage": "Waiting for a Tafwid worker"
          }
        ]
      }
    ],
    "Interrupt": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash -c 'exec python3 \"${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/delegate/scripts/completion_hook.py\" disarm'",
            "timeout": 2
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash -c 'exec python3 \"${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/delegate/scripts/completion_hook.py\" disarm'",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

The prompt hook's timeout rises from 2 to 5 seconds because it now writes a file.

- [ ] **Step 6: Run the suite**

Run: `make test`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add plugins/tafwid
git commit -m "feat: run the completion hook under Codex and Claude Code (TAF-6)"
```

---

### Task 7: Migration command

**Files:**
- Create: `S/scripts/migration.py`, `S/tests/test_migration.py`
- Modify: `S/scripts/settings.py` (`main`)

**Interfaces:**
- Consumes: `paths.legacy_in_use()`, `paths.neutral_root()`, `paths.state_root()`, `paths.atomic_json()`, `run_state.list_runs()`, `run_state.ACTIVE`.
- Produces: `migration.migrate(dry_run=False) -> dict` with `event` of `nothing_to_migrate`, `dry_run`, or `migrated`; CLI `settings.py migrate [--dry-run]`.

- [ ] **Step 1: Write the failing tests**

Create `S/tests/test_migration.py`:

```python
"""Legacy state moves only on request, completely, and is restored on failure."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import accounts
import migration
import paths
import settings

TASK = "00000000-0000-4000-8000-000000000001"
RUN = "00000000-0000-4000-8000-000000000002"


class MigrationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.codex = self.root / "codex"
        self.neutral = self.root / "user" / ".tafwid" / "state"
        env = patch.dict(os.environ, {"CODEX_HOME": str(self.codex), "TAFWID_HOST": "codex",
                                      "TAFWID_HOME": str(self.neutral.parent)})
        env.start()
        self.addCleanup(env.stop)
        self.legacy = self.codex / "tafwid" / "state"

    def legacy_install(self):
        self.legacy.mkdir(parents=True)  # an existing pre-0.4 installation
        self.account = accounts.create("work", "business")
        settings.save({**settings.defaults(), "permission_policy": "inherit"})
        (self.legacy / "workers").mkdir()
        (self.legacy / "workers" / (RUN + ".json")).write_text(json.dumps(
            {"id": RUN, "codex_thread_id": TASK, "status": "completed", "output_dir": str(self.root / "run")}))
        self.assertEqual(paths.legacy_in_use(), self.legacy)

    def snapshot(self, root):
        return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}

    def test_nothing_to_migrate_on_a_fresh_install(self):
        self.assertEqual(migration.migrate()["event"], "nothing_to_migrate")
        self.assertFalse(self.neutral.parent.exists())

    def test_dry_run_reports_and_changes_nothing(self):
        self.legacy_install()
        before = self.snapshot(self.legacy)
        result = migration.migrate(dry_run=True)
        self.assertEqual(result["event"], "dry_run")
        self.assertEqual((result["accounts"], result["runs"]), (1, 1))
        self.assertEqual(self.snapshot(self.legacy), before)
        self.assertFalse(self.neutral.exists())

    def test_migrate_moves_state_and_keeps_accounts_usable(self):
        self.legacy_install()
        self.neutral.parent.mkdir(parents=True)  # ~/.tafwid may already exist without state
        result = migration.migrate()
        self.assertEqual(result["event"], "migrated")
        self.assertFalse(self.legacy.exists())
        self.assertEqual(paths.state_root(), self.neutral)
        self.assertIsNone(paths.legacy_in_use())
        row = accounts.get("work")
        self.assertEqual(Path(row["home"]), self.neutral / "accounts" / "homes" / self.account["id"])
        self.assertEqual(accounts.validate_home(row), Path(row["home"]))
        self.assertEqual(settings.read()["permission_policy"], "inherit")
        self.assertEqual(self.neutral.parent.stat().st_mode & 0o077, 0)

    def test_active_worker_blocks_migration(self):
        self.legacy_install()
        (self.legacy / "workers" / (RUN + ".json")).write_text(json.dumps(
            {"id": RUN, "status": "running", "updated_at": time.time(), "output_dir": str(self.root / "run")}))
        with self.assertRaisesRegex(ValueError, RUN):
            migration.migrate()
        self.assertTrue(self.legacy.exists())
        self.assertFalse(self.neutral.exists())

    def test_failure_after_the_move_restores_the_source(self):
        self.legacy_install()
        registry = self.legacy / "accounts" / "registry.json"
        registry.write_text("{not json")
        before = self.snapshot(self.legacy)
        with self.assertRaises(ValueError):
            migration.migrate()
        self.assertEqual(self.snapshot(self.legacy), before)
        self.assertFalse(self.neutral.exists())

    def test_redirected_source_is_refused(self):
        real = self.root / "elsewhere"
        real.mkdir()
        self.legacy.parent.mkdir(parents=True)
        self.legacy.symlink_to(real)
        with self.assertRaisesRegex(ValueError, "redirected"):
            migration.migrate()

    def test_cli_reports_json(self):
        self.legacy_install()
        command = [sys.executable, settings.__file__, "migrate"]
        dry = subprocess.run([*command, "--dry-run"], capture_output=True, text=True)
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertEqual(json.loads(dry.stdout)["event"], "dry_run")
        done = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(json.loads(done.stdout)["event"], "migrated")
        again = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(json.loads(again.stdout)["event"], "nothing_to_migrate")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m unittest discover -s plugins/tafwid/skills/delegate/tests -p test_migration.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'migration'`.

- [ ] **Step 3: Write `S/scripts/migration.py`**

```python
"""Move a legacy Tafwid state directory to the host-neutral home on request.

Used by `settings.py migrate`. Nothing here runs implicitly: reads keep using a
legacy directory in place until the user asks for the move.
"""
import errno
import json
import os
from pathlib import Path
import shutil

import paths
import run_state


def _files(root):
    """List relative regular-file paths and sizes for copy verification."""
    return sorted((str(path.relative_to(root)), path.stat().st_size)
                  for path in root.rglob("*") if path.is_file() and not path.is_symlink())


def _move(source, destination):
    """Rename, or copy and verify across filesystems before removing the source."""
    try:
        os.rename(source, destination)
        return
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise
    shutil.copytree(source, destination, symlinks=True)
    if _files(source) != _files(destination):
        shutil.rmtree(destination)
        raise ValueError("Copied state does not match the source; nothing was removed")
    shutil.rmtree(source)


def migrate(dry_run=False):
    """Move the single legacy state directory to the neutral home.

    Refuse while workers run or when a path is redirected. Rewrite the absolute
    account homes saved in the registry. Any failure after the move restores
    the original directory before raising.
    """
    source = paths.legacy_in_use()
    destination = paths.neutral_root()
    if source is None:
        return {"event": "nothing_to_migrate", "state_root": str(paths.state_root())}
    if source.is_symlink() or destination.is_symlink() or destination.parent.is_symlink():
        raise ValueError("Tafwid state path is redirected; migration stopped")
    if destination.exists():
        raise ValueError("The destination state directory already exists; migration stopped")
    active = [row["id"] for row in run_state.list_runs() if row.get("status") in run_state.ACTIVE]
    if active:
        raise ValueError("Workers are still running; wait for them before migrating: " + ", ".join(sorted(active)))
    registry = source / "accounts" / "registry.json"
    original = registry.read_bytes() if registry.is_file() else None
    result = {"source": str(source), "destination": str(destination),
              "accounts": len(list((source / "accounts" / "homes").glob("*"))),
              "tasks": len(list((source / "tasks").glob("*"))),
              "runs": len(list((source / "workers").glob("*.json")))}
    if dry_run:
        return {"event": "dry_run", **result}
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(destination.parent, 0o700)
    _move(source, destination)
    try:
        if original is not None:
            data = json.loads(original)
            prefix = str(source) + os.sep
            for row in data["accounts"]:
                if isinstance(row.get("home"), str) and row["home"].startswith(prefix):
                    row["home"] = str(destination / row["home"][len(prefix):])
            paths.atomic_json(destination / "accounts" / "registry.json", data)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        _move(destination, source)
        (source / "accounts" / "registry.json").write_bytes(original)
        raise ValueError("Migration failed and the original state was restored: " + str(exc)) from exc
    return {"event": "migrated", **result}
```

- [ ] **Step 4: Add the CLI action to `S/scripts/settings.py`**

In `main()`:
- `choices=("show", "set")` becomes `choices=("show", "set", "migrate")`, help `"read or update settings, or move legacy state to the neutral home"`.
- Add `parser.add_argument("--dry-run", action="store_true", help="with migrate: report what would move without changing anything")`.
- After the two existing `parser.error` checks add:

```python
    if args.action == "migrate" and (args.policy is not None or args.harness is not None or args.global_defaults):
        parser.error("migrate accepts only --dry-run")
    if args.dry_run and args.action != "migrate":
        parser.error("--dry-run applies to migrate")
```

- At the start of the `try:` block add:

```python
        if args.action == "migrate":
            import migration
            print(json.dumps(migration.migrate(dry_run=args.dry_run)))
            return 0
```

- Add to the epilog examples: `  python3 scripts/settings.py migrate --dry-run` and `  python3 scripts/settings.py migrate`, and to the module docstring: `migrate [--dry-run] moves a legacy state directory to the host-neutral home.`

- [ ] **Step 5: Run the suite**

Run: `make test`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add plugins/tafwid/skills/delegate
git commit -m "feat: add an explicit state migration command (TAF-6)"
```

---

### Task 8: Host-neutral wording

"Codex" stays where it means the GPT worker CLI, Codex sign-in, or `CODEX_HOME` for account homes. It becomes "the coordinator" where it means the orchestrating host.

**Files:**
- Modify: `plugins/tafwid/skills/delegate/SKILL.md`, `plugins/tafwid/skills/account/SKILL.md`
- Modify: `S/references/workflow.md`, `S/references/claude-code.md`, `S/references/monitor.md`
- Modify: `S/scripts/delegate.py`, `session.py`, `settings.py`, `wait.py`, `connections.py`, `codex_cli.py`

- [ ] **Step 1: Find every coordinator-meaning use**

Run: `grep -rn -i "codex" plugins/tafwid/skills --include=*.md --include=*.py --exclude-dir=tests`
Review each hit against the rule above.

- [ ] **Step 2: Apply the script edits**

| File | Old | New |
| --- | --- | --- |
| `delegate.py` `CONTRACT` | `You are a Claude Code worker for a bounded Codex task.` | `You are a Claude Code worker for a bounded task assigned by a coordinator.` |
| `delegate.py` `CONTRACT` | `Codex owns planning/dispatch; no replanning or nested workers unless requested.` | `The coordinator owns planning/dispatch; no replanning or nested workers unless requested.` |
| `delegate.py` `CONTRACT` | `Codex retains acceptance review.` | `The coordinator retains acceptance review.` |
| `delegate.py` `run` | `Delegation is off for this Codex task. Enable it` | `Delegation is off for this task. Enable it` |
| `connections.py` | `Invalid Codex task identity` | `Invalid task identity` |
| `connections.py` | `Delegation is off for this Codex task` | `Delegation is off for this task` |
| `settings.py` | `Invalid Codex task identity; cannot select settings` | `Invalid task identity; cannot select settings` |
| `settings.py` | `No Codex task identity; use --global for global defaults` | `No task identity from the coordinator; use --global for global defaults` |
| `settings.py` epilog | `use the current Codex task identity from the host environment` | `use the current task identity from the coordinator's environment` |
| `session.py` docstring | `Read or change this Codex task's pool of worker connections.` | `Read or change this task's pool of worker connections.` |
| `session.py` description | `for the current Codex chat.` | `for the current chat.` |
| `session.py` epilog | `Read from CODEX_THREAD_ID, falling back to CODEX_SESSION_ID.` and `Use the identity provided by Codex; there is no chat-ID argument.` | `Codex: CODEX_THREAD_ID, falling back to CODEX_SESSION_ID. Claude Code: CLAUDE_CODE_SESSION_ID.` and `Use the identity provided by the coordinator; there is no chat-ID argument.` |
| `wait.py` epilog | `Uses the current Codex chat identity from the environment.` | `Uses the current chat identity from the coordinator's environment.` |
| `wait.py` comment | `do not wake GPT` | `do not wake the coordinator` |

`codex_cli.CONTRACT` already says "a task assigned by Tafwid"; leave it.

- [ ] **Step 3: Apply the skill and reference edits**

`skills/delegate/SKILL.md`:
- Description becomes `Use when the user manages Tafwid delegation, assigns work to Claude Code or a named GPT account, or continues with delegation enabled. Works when Codex or Claude Code is the coordinator.`
- `A bare \`$tafwid:delegate\` invocation means status.` becomes `Invoking the delegate skill with no arguments means status.`
- `offer \`$tafwid:account\` setup` becomes `offer setup through the \`tafwid:account\` skill`.
- After the Session control section's last paragraph add: `If status or settings output contains a \`migration\` field, tell the user once that \`scripts/settings.py migrate\` can move saved state to the shared location, and continue.`
- Fix the typo `You have the a few scripts availible to you.` to `You have a few scripts available.`

`skills/account/SKILL.md`: `Your current Codex login will stay signed in.` becomes `Your own Codex login, if you have one, will stay signed in.`

`references/claude-code.md`: the `inherit` row becomes `Uses \`full\` when the coordinator currently reports full access; otherwise uses \`scoped\`.` and add below the table:

```markdown
A Codex coordinator reports full access through its permission profile. A Claude Code
coordinator reports it when the session was in bypass-permissions mode at the user's
last prompt; this needs Tafwid's hooks enabled, and a mode change mid-turn takes
effect at the next prompt. Without a confirmed signal, `inherit` uses `scoped`.
```

`references/monitor.md`: after the paragraph beginning `In Codex, use one`, add:

```markdown
In Claude Code, run `wait.py` with the Bash tool and a tool timeout of at least
310 seconds, so the script's own five-minute limit ends the call. If it returns
`waiting`, run it again with only `pending_run_ids`. Do not run it in the
background and poll its output.
```

- [ ] **Step 4: Run the suite**

Run: `make test`
Expected: PASS. If a test asserts an old message, update that assertion to the new text.

- [ ] **Step 5: Commit**

```bash
git add plugins/tafwid/skills
git commit -m "docs: address the coordinator instead of Codex in skills and messages (TAF-6)"
```

---

### Task 9: Claude Code packaging

**Files:**
- Create: `.claude-plugin/marketplace.json`, `plugins/tafwid/.claude-plugin/plugin.json`
- Modify: `plugins/tafwid/.codex-plugin/plugin.json`, `VERSION`, `scripts/check_package.py`

- [ ] **Step 1: Extend the package check first**

In `scripts/check_package.py`, after the Codex marketplace assertions add:

```python
    # Claude Code packaging mirrors the Codex identity and version.
    claude = json.loads((plugin / ".claude-plugin/plugin.json").read_text())
    assert claude["name"] == "tafwid", "Claude manifest name mismatch"
    assert claude["version"] == version, "Claude manifest/version mismatch"
    assert claude["license"] == "MIT"
    claude_market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    assert claude_market["name"] == "tafwid" and claude_market["owner"]["name"]
    entries = claude_market["plugins"]
    assert len(entries) == 1 and entries[0]["name"] == "tafwid"
    assert entries[0]["source"] == "./plugins/tafwid"
```

Add `"scripts/host.py"` and `"scripts/migration.py"` to the required runtime files tuple. Replace the two hook lines at the end of that block with:

```python
    hooks = json.loads((plugin / "hooks/hooks.json").read_text())["hooks"]
    assert hooks["Stop"] and hooks["UserPromptSubmit"], "Missing completion hooks"
    prefix = ("bash -c 'exec python3 \"${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
              "/skills/delegate/scripts/completion_hook.py\" ")
    for event, groups in hooks.items():
        for group in groups:
            for hook in group["hooks"]:
                assert hook["command"].startswith(prefix), f"Hook is not host-neutral: {event}"
```

Update the module docstring's checks sentence to mention both hosts' manifests.

- [ ] **Step 2: Run to verify failure**

Run: `python3 scripts/check_package.py`
Expected: FAIL with `FileNotFoundError` for `.claude-plugin/plugin.json`.

- [ ] **Step 3: Create the manifests and bump the version**

`plugins/tafwid/.claude-plugin/plugin.json`:

```json
{
  "name": "tafwid",
  "version": "0.4.0",
  "description": "Delegate bounded work to coding agents while your coordinator orchestrates and reviews.",
  "author": {
    "name": "hunainahmedj",
    "url": "https://github.com/hunainahmedj"
  },
  "homepage": "https://github.com/hunainahmedj/tafwid",
  "repository": "https://github.com/hunainahmedj/tafwid",
  "license": "MIT",
  "keywords": [
    "delegation",
    "coding-agents",
    "claude-code",
    "codex"
  ]
}
```

`.claude-plugin/marketplace.json`:

```json
{
  "name": "tafwid",
  "owner": {
    "name": "hunainahmedj",
    "url": "https://github.com/hunainahmedj"
  },
  "metadata": {
    "description": "Tafwid: delegate work, keep control."
  },
  "plugins": [
    {
      "name": "tafwid",
      "source": "./plugins/tafwid",
      "description": "Delegate bounded work to Claude Code or named GPT accounts while your coordinator orchestrates and reviews.",
      "category": "productivity"
    }
  ]
}
```

Set `VERSION` to `0.4.0`. In `plugins/tafwid/.codex-plugin/plugin.json` set `"version": "0.4.0"`, the description to `Delegate bounded work to coding agents while your coordinator orchestrates and reviews.`, `longDescription` to `Delegate bounded tasks to Claude Code or named GPT accounts with task-local switches, model selection, explicit permissions and compact reports.`, and add `"claude-code"` to `keywords`.

- [ ] **Step 4: Validate**

Run: `python3 scripts/check_package.py`
Expected: `Package integrity passed (... version 0.4.0).`

Run, where the Claude Code CLI is installed: `claude plugin validate . && claude plugin validate plugins/tafwid`
Expected: both pass. The only acceptable warning is `hooks.Interrupt: unknown hook event; entry ignored at runtime`. If the marketplace description warning appears, move the description to the location the validator names and re-run.

- [ ] **Step 5: Commit**

```bash
git add .claude-plugin plugins/tafwid/.claude-plugin plugins/tafwid/.codex-plugin VERSION scripts/check_package.py
git commit -m "feat: package Tafwid for Claude Code (TAF-6)"
```

---

### Task 10: Documentation

**Files:**
- Modify: `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `docs/migration.md`
- Modify: `docs/03-architecture/system.md`, `docs/04-modules/delegation.md`, `docs/04-modules/accounts.md`, `docs/02-workspace/repos.md`, `docs/01-project/overview.md`
- Create: `docs/05-decisions/0004-host-adapter-and-neutral-state.md`; modify `docs/05-decisions/README.md`
- Modify: `docs/01-project/backlog.md`

Follow `docs/07-meta/documentation-guide.md`: each fact has one home; module docs link to the architecture page instead of repeating it.

- [ ] **Step 1: README**

- Introduction: `Tafwid lets Codex or Claude Code delegate bounded tasks to Claude Code or named GPT accounts. The coordinator directs the work and accepts the result using concise reports and relevant checks.`
- "What it does": `Follow Codex` becomes `Follow coordinator`; `Delegation does not guarantee lower Codex usage` becomes `lower coordinator usage`. Add: `A Claude Code coordinator and its Claude workers share one Claude subscription; delegation there saves coordinator context, not allowance.`
- Requirements: first bullet becomes `Codex or Claude Code with plugin support, as the coordinator.`
- Install: keep the Codex block under a `### Codex` heading and add:

```markdown
### Claude Code

    /plugin marketplace add hunainahmedj/tafwid
    /plugin install tafwid@tafwid

Start a new session. Skills are invoked as `/tafwid:delegate` and `/tafwid:account`.
```

- Skill table: the first column lists both forms, for example `` `$tafwid:delegate` / `/tafwid:delegate` ``.
- Hooks paragraph: add `Claude Code runs plugin hooks without a trust step; if hooks are disabled, the workflow uses \`wait.py\`.`
- Before "Contribute" add a short paragraph: state is kept in `~/.tafwid/state` and shared by both coordinators; an installation that predates 0.4 keeps using its directory under the Codex home until `settings.py migrate` is run; link to `docs/migration.md`.

- [ ] **Step 2: Contributor files**

- `AGENTS.md`: `Tafwid is a Codex plugin.` becomes `Tafwid is a plugin for Codex and Claude Code.` Add a bullet: `Only \`scripts/host.py\` reads coordinator identity variables; other scripts call it.` The last bullet becomes `Use release versions in VERSION and both plugin manifests consistently; preserve license notices.`
- `CONTRIBUTING.md`: after the Codex install block add the Claude Code equivalent, `claude --plugin-dir "$PWD/plugins/tafwid"` for a local session and `claude plugin validate . && claude plugin validate plugins/tafwid` before a release. Add `TAFWID_HOME="$test_home/tafwid"` to the note on separate test homes. In Releases, `the plugin manifest version` becomes `both plugin manifest versions`.
- `CHANGELOG.md`: rename `## Unreleased` to `## 0.4.0` and add at its top:

```markdown
- Support Claude Code as a coordinator alongside Codex, with Claude Code marketplace
  and plugin manifests.
- Keep state in a host-neutral home, `~/.tafwid/state`, shared by both coordinators.
  Existing state under the Codex home is used in place until `settings.py migrate`.
- Share one hooks file between hosts; on Claude Code the prompt hook records that
  hooks are active and the session's permission mode.
- Record run ownership as `coordinator_task_id` and `coordinator_host`; older
  records remain readable.
- Rename the `codex_full_access` permission result field to `coordinator_full_access`.
```

- [ ] **Step 3: Migration guide**

Append to `docs/migration.md`:

```markdown
## From Tafwid 0.3

Version 0.4 adds Claude Code as a coordinator and a host-neutral state home,
`~/.tafwid/state` (`TAFWID_HOME` overrides `~/.tafwid`). Upgrade and start a new task.

An existing installation keeps using its directory under the Codex home; nothing
moves on its own. `session.py status` and `settings.py show` report a `migration`
field while that is the case. To move it, finish or pause running workers, then:

    python3 scripts/settings.py migrate --dry-run
    python3 scripts/settings.py migrate

Named GPT accounts move with the directory and stay signed in. If the neutral
directory and a legacy directory both exist, scripts stop with a conflict error;
back up and reconcile them. Run records now name their owner as
`coordinator_task_id`; older records are still read.

A Codex task and a Claude Code session are different tasks. Accounts, global
defaults and run history are shared; the on/off switch and task settings are not.
```

Also change the earlier sentence `A later release may provide an explicit migration command;` to `Version 0.4 adds an explicit migration command;`.

- [ ] **Step 4: Durable documentation**

- `docs/03-architecture/system.md`: add a `host.py` row (`Detect the coordinator and its task; scrub worker environments; record Claude Code hook activity.`) and a `migration.py` row to the script table; rewrite the state paragraph for the neutral home and legacy reuse; rewrite the hook paragraph so it describes trust on Codex and the hooks-seen marker on Claude Code; replace coordinator-meaning uses of "Codex".
- `docs/04-modules/delegation.md`: `lets a Codex coordinator assign` becomes `lets a Codex or Claude Code coordinator assign`; under Decisions add a link to ADR-0004; under Tracker add `[TAF-6](../01-project/backlog.md)`.
- `docs/04-modules/accounts.md`: note that accounts are shared by both coordinators and link to ADR-0004.
- `docs/02-workspace/repos.md`: the `plugins/tafwid/` role becomes `Distributable plugin for Codex and Claude Code, including both hosts' manifests, skills, hooks, and brand assets`; add a row for `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json` as the two marketplace entries; the hook-configuration sentence in "New machine setup" stays about Archivist hooks.
- `docs/01-project/overview.md`: `Tafwid helps a Codex user delegate` becomes `Tafwid helps a Codex or Claude Code user delegate`.

- [ ] **Step 5: Decision record**

Create `docs/05-decisions/0004-host-adapter-and-neutral-state.md`:

```markdown
# ADR-0004: Host adapter and host-neutral state

- Date: 2026-10-02
- Status: Accepted

## Context

Tafwid was built as a Codex plugin. Its runtime read Codex's task identity and
permission signals directly and kept state under the Codex home. Claude Code
users could not install it, and a Claude Code session could not coordinate.

## Options considered

- One plugin with a host adapter: a single runtime and test suite; most scripts
  change once.
- Separate plugin directories per host sharing a copied runtime: no hooks
  collision, but two skill sets drift and packaging must police the copy.
- Skills pass an explicit host flag to every script: least code, but correctness
  depends on the model passing the flag, and hooks still need the host.

## Decision

Keep one plugin directory with both hosts' manifests. `host.py` is the only
module that reads coordinator identity. State lives in `~/.tafwid/state`, shared
by both coordinators; an existing directory under the Codex home is used in place
until the user runs `settings.py migrate`. One hooks file serves both hosts
through a `bash -c` command that accepts either plugin-root variable.

## Consequences

Accounts, defaults and run history are shared across coordinators; task switches
are not, because the hosts issue different task IDs. Ambiguous identity (both
hosts' variables present) is an error resolved with `TAFWID_HOST`. On Claude Code,
hook availability and inherited full access rely on a marker written by the prompt
hook, so both are off when hooks are disabled, and the permission mode can lag by
one prompt. Tracked in [TAF-6](../01-project/backlog.md); design history is in the
[spec](../superpowers/specs/2026-10-02-claude-code-coordinator-design.md).
```

Add the row `| [0004](0004-host-adapter-and-neutral-state.md) | Host adapter and host-neutral state | Accepted |` to `docs/05-decisions/README.md`.

- [ ] **Step 6: Backlog**

In `docs/01-project/backlog.md`, restore `No active implementation items.` under Now and add at the top of Done:

```markdown
- TAF-6 Make Claude Code a full coordinator alongside Codex. Offline suite and
  package checks pass; live acceptance steps are listed in the
  [plan](../superpowers/plans/2026-10-02-claude-code-coordinator.md).
```

- [ ] **Step 7: Check and commit**

Run: `make test`
Expected: PASS, including documentation link checks in `check_package.py`.

```bash
git add README.md AGENTS.md CONTRIBUTING.md CHANGELOG.md docs
git commit -m "docs: describe Claude Code coordination and the neutral state home (TAF-6)"
```

---

### Task 11: Verification and acceptance

- [ ] **Step 1: Full offline gate**

Run: `make test`
Expected: PASS with zero failures and zero errors.

Run the suite once more with a Claude Code identity in the environment to prove fixtures are isolated:
`CLAUDE_CODE_SESSION_ID=00000000-0000-4000-8000-0000000000aa make test`
Expected: PASS.

- [ ] **Step 2: Claude Code validation**

Run: `claude plugin validate . && claude plugin validate plugins/tafwid`
Expected: pass; only the `Interrupt` warning.

- [ ] **Step 3: Claude Code smoke test with an isolated state home**

In a temporary directory, with `TAFWID_HOME` set to a temporary path, start one headless session with `claude -p --plugin-dir <repo>/plugins/tafwid` that runs `session.py status` through the Bash tool. Confirm:
- the output has a non-null `thread_id` equal to the session ID and `enabled: false`;
- `$TAFWID_HOME/state/hook-seen/<session-id>.json` exists with a `permission_mode`;
- `completion_hook.py status` run in that session reports `{"active": true}`.

- [ ] **Step 4: Manual acceptance on the developer's machine**

These need real accounts and both CLIs, so they are run by the user:

1. Claude Code: `/plugin marketplace add` the local repository, `/plugin install tafwid@tafwid`; both skills are listed.
2. New Claude Code session: `/tafwid:delegate on claude`, then status.
3. One one-shot assignment to a named GPT account and one to a Claude worker; each returns a compact report.
4. Arm the completion hook, end the turn, and confirm Claude Code resumes when the worker finishes, including a worker that runs longer than ten minutes (the 1800-second hook timeout).
5. With hooks disabled, `completion_hook.py arm` reports `unavailable` and `wait.py` works.
6. Codex: upgrade and reinstall, confirm the hooks still load and are trusted with the `bash -c` command, and repeat steps 2 to 4. If the hook command fails on Codex, stop and report; the fallback is host-specific hook files.
7. `settings.py migrate --dry-run`, then `migrate`; accounts list as ready from both hosts without a new sign-in.
