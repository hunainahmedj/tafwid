Before non-trivial work, read docs/AGENTS.md (project briefing) and the relevant module doc under docs/04-modules/.

# Tafwid contributor instructions

Tafwid is a plugin for Codex and Claude Code. The distributable plugin is under `plugins/tafwid`;
its skill, Python runtime, references and offline tests are under
`plugins/tafwid/skills/delegate`. Read README.md before changing behavior.

- Claude Code and named GPT Codex CLI accounts are supported worker backends. Keep their authentication, commands and permissions explicit; do not advertise other adapters as supported.
- Keep runtime state, credentials, task transcripts and private evidence out of Git.
- Preserve task-local delegation, independent acceptance review and compact context.
- Tests use isolated temporary homes and fake worker executables. Do not make real
  model requests or change the developer's installed plugin during ordinary tests.
- Run `make test` for runtime changes, and `python3 scripts/check_package.py` for
  packaging changes.
- Only `scripts/host.py` reads coordinator identity variables; other scripts call it.
- Use release versions in VERSION and both plugin manifests consistently; preserve license notices.
