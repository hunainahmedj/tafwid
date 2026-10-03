#!/usr/bin/env python3
"""Check Tafwid's repository files before distributing the plugin.

Run from any directory with Python 3.10 or newer:
    python3 /path/to/tafwid/scripts/check_package.py

No arguments are required. The repository root is resolved from this file.
Checks cover Codex and Claude Code metadata consistency, required files, local documentation links,
PNG assets, and recognizable private data. Files are read but never changed;
no workers are launched and no network requests are made.

Success prints a summary and exits with code 0. A failed check or unreadable
file raises an exception and exits with a nonzero code. These checks are
specific to Tafwid and are not a complete security review.
"""

import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def source_files(excluded):
    """Files Git would commit (tracked plus untracked, honouring .gitignore).

    Falls back to walking the tree when Git is unavailable, so local build
    output and scratch folders do not fail the check inside a checkout.
    """
    try:
        listed = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT, check=True, capture_output=True,
        ).stdout.decode().split("\0")
        paths = [ROOT / name for name in listed if name]
    except (OSError, subprocess.CalledProcessError):
        paths = list(ROOT.rglob("*"))
    return [
        p for p in paths
        if (p.exists() or p.is_symlink())
        and not any(part in excluded for part in p.relative_to(ROOT).parts)
    ]



def check():
    """Validate the repository and print its source-file count and version.

    Raises:
        AssertionError: A package rule is violated.
        OSError: A required file cannot be read.
        ValueError: JSON or text cannot be decoded.
        KeyError: Required metadata is missing.
        TypeError: Metadata has an unexpected structure.

    Assertions must be enabled; do not run this script with Python's -O flag.
    """
    plugin = ROOT / "plugins/tafwid"
    manifest = json.loads((plugin / ".codex-plugin/plugin.json").read_text())
    marketplace = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
    version = (ROOT / "VERSION").read_text().strip()

    # Plugin identity and release metadata.
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), "Invalid VERSION"
    assert manifest["name"] == plugin.name == "tafwid"
    assert manifest["version"] == version, "Manifest/version mismatch"
    assert manifest["license"] == "MIT"

    visual = manifest["interface"]
    image_paths = [
        visual[key]
        for key in ("composerIcon", "logo", "logoDark")
        if key in visual
    ]
    image_paths += visual.get("screenshots", [])
    for name in image_paths:
        asset = plugin / name
        assert asset.resolve().is_relative_to(plugin.resolve()), (
            f"Image outside plugin: {name}"
        )
        assert asset.is_file() and asset.suffix == ".png", f"Missing PNG asset: {name}"

    assert marketplace["name"] == "tafwid"
    entries = marketplace["plugins"]
    assert len(entries) == 1 and entries[0]["name"] == "tafwid"
    assert entries[0]["source"] == {"source": "local", "path": "./plugins/tafwid"}

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

    # Skill entry points and local documentation links.
    entries = {p.parent.name: p for p in (plugin / "skills").glob("*/SKILL.md")}
    assert set(entries) == {"delegate", "account"}, (
        "Missing or unexpected skill entry points"
    )
    for name, path in entries.items():
        assert f"\nname: {name}\n" in path.read_text(), f"Skill name mismatch: {name}"
        assert (path.parent / "agents/openai.yaml").is_file(), (
            f"Missing skill metadata: {name}"
        )

    skill = plugin / "skills/delegate"
    assert (skill / "references/workflow.md").is_file(), "Missing delegation workflow"
    assert (skill / "references/gpt-accounts.md").is_file(), "Missing GPT account guide"
    for document in (plugin / "skills").rglob("*.md"):
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", document.read_text()):
            if "://" in target or target.startswith("#"):
                continue
            resource = (document.parent / target.split("#", 1)[0]).resolve()
            assert resource.is_relative_to(plugin.resolve()), (
                f"Reference outside plugin: {document.name}: {target}"
            )
            assert resource.exists(), f"Broken reference: {document.name}: {target}"

    # Required repository documents and runtime files.
    for name in (
        "README.md",
        "LICENSE",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CHANGELOG.md",
        "docs/migration.md",
        "docs/architecture.md",
        "docs/account-setup.md",
    ):
        assert (ROOT / name).is_file(), f"Missing {name}"
    for name in (
        "scripts/delegate.py",
        "scripts/completion_hook.py",
        "scripts/paths.py",
        "scripts/host.py",
        "scripts/migration.py",
        "scripts/session.py",
        "scripts/account.py",
        "scripts/accounts.py",
        "scripts/connections.py",
        "scripts/codex_cli.py",
        "scripts/run_state.py",
        "scripts/wait.py",
        "references/claude-code.md",
    ):
        assert (skill / name).is_file(), f"Missing {name}"
    hooks = json.loads((plugin / "hooks/hooks.json").read_text())["hooks"]
    assert hooks["Stop"] and hooks["UserPromptSubmit"], "Missing completion hooks"
    prefix = ("bash -c 'exec python3 \"${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
              "/skills/delegate/scripts/completion_hook.py\" ")
    for event, groups in hooks.items():
        for group in groups:
            for hook in group["hooks"]:
                assert hook["command"].startswith(prefix), f"Hook is not host-neutral: {event}"

    # Scan source files for invalid assets and recognizable private data.
    excluded = {".git", ".remember", "__pycache__", "dist", ".venv", "node_modules"}
    private_path = re.compile(r"/(?:Users|home)/[a-zA-Z0-9_.-]+/")
    secret = re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|sk-ant-[A-Za-z0-9_-]{30,})")
    # Binary assets are checked by signature instead of being read as text.
    binary_magic = {
        ".png": b"\x89PNG\r\n\x1a\n",
        ".jpg": b"\xff\xd8\xff",
        ".glb": b"glTF",
        ".wasm": b"\x00asm",
    }
    count = 0
    for path in source_files(excluded):
        relative = path.relative_to(ROOT)
        assert not path.is_symlink(), f"Unexpected symlink: {relative}"
        if not path.is_file():
            continue
        assert path.suffix not in {".jsonl", ".sqlite", ".db", ".log"}, (
            f"Runtime data: {relative}"
        )
        assert path.name != ".env", f"Environment secrets: {relative}"
        if path.suffix in binary_magic:
            assert path.read_bytes().startswith(binary_magic[path.suffix]), (
                f"Invalid {path.suffix} file: {relative}"
            )
            count += 1
            continue
        content = path.read_text()
        assert not private_path.search(content), f"Machine-specific path: {relative}"
        assert not secret.search(content), f"Possible credential: {relative}"
        count += 1

    print(f"Package integrity passed ({count} source files, version {version}).")


if __name__ == "__main__":
    check()
