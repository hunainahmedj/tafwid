#!/usr/bin/env python3
"""Offline release integrity checks; not a substitute for a security review."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def check():
    plugin = ROOT / "plugins/tafwid"
    manifest = json.loads((plugin / ".codex-plugin/plugin.json").read_text())
    marketplace = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
    version = (ROOT / "VERSION").read_text().strip()
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), "Invalid VERSION"
    assert manifest["name"] == plugin.name == "tafwid"
    assert manifest["version"] == version, "Manifest/version mismatch"
    assert manifest["license"] == "MIT"
    assert marketplace["name"] == "tafwid"
    entries = marketplace["plugins"]
    assert len(entries) == 1 and entries[0]["name"] == "tafwid"
    assert entries[0]["source"] == {"source": "local", "path": "./plugins/tafwid"}
    skill = plugin / "skills/tafwid"
    assert "\nname: tafwid\n" in (skill / "SKILL.md").read_text()
    for name in ("README.md", "LICENSE", "CONTRIBUTING.md", "SECURITY.md",
                 "CHANGELOG.md", "docs/migration.md", "docs/architecture.md"):
        assert (ROOT / name).is_file(), f"Missing {name}"
    for name in ("scripts/delegate.py", "scripts/paths.py", "scripts/session.py",
                 "assets/dashboard/index.html", "assets/dashboard/settings.html"):
        assert (skill / name).is_file(), f"Missing {name}"
    excluded = {".git", "__pycache__", "dist", ".venv", "node_modules"}
    private_path = re.compile(r"/(?:Users|home)/[a-zA-Z0-9_.-]+/")
    secret = re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|sk-ant-[A-Za-z0-9_-]{30,})")
    count = 0
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if any(part in excluded for part in relative.parts):
            continue
        assert not path.is_symlink(), f"Unexpected symlink: {relative}"
        if not path.is_file():
            continue
        assert path.suffix not in {".jsonl", ".sqlite", ".db", ".log"}, f"Runtime data: {relative}"
        assert path.name != ".env", f"Environment secrets: {relative}"
        content = path.read_text()
        assert not private_path.search(content), f"Machine-specific path: {relative}"
        assert not secret.search(content), f"Possible credential: {relative}"
        count += 1
    print(f"Package integrity passed ({count} source files, version {version}).")


if __name__ == "__main__":
    check()
