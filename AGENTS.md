# Tafwid contributor instructions

Tafwid is a Codex plugin. The distributable plugin is under `plugins/tafwid`;
its skill, Python runtime, dashboard, references and offline tests are under
`plugins/tafwid/skills/delegate`. The thin dashboard and settings entry points
are sibling skills sharing that runtime. Read README.md before changing behavior.

- Keep provider-specific authentication, commands and permissions explicit.
- Only Claude Code is implemented. Do not advertise planned adapters as supported.
- Keep runtime state, credentials, task transcripts and private evidence out of Git.
- Preserve task-local delegation, independent acceptance review and compact context.
- Tests use isolated temporary homes and a fake Claude executable. Do not make real
  model requests or change the developer's installed plugin during ordinary tests.
- Run `make test` for runtime changes, and `python3 scripts/check_package.py` for
  packaging changes. UI changes also need a visible desktop/mobile check.
- Use release versions in both manifests consistently; preserve license notices.
