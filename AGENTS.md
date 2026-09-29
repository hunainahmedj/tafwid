# Tafwid contributor instructions

Tafwid is a Codex plugin. The distributable plugin is under `plugins/tafwid`;
its skill, Python runtime, references and offline tests are under
`plugins/tafwid/skills/delegate`. Read README.md before changing behavior.

- Claude Code and named GPT Codex CLI accounts are supported worker backends. Keep their authentication, commands and permissions explicit; do not advertise other adapters as supported.
- Keep runtime state, credentials, task transcripts and private evidence out of Git.
- Preserve task-local delegation, independent acceptance review and compact context.
- Tests use isolated temporary homes and fake worker executables. Do not make real
  model requests or change the developer's installed plugin during ordinary tests.
- Run `make test` for runtime changes, and `python3 scripts/check_package.py` for
  packaging changes.
- Use release versions in both manifests consistently; preserve license notices.
