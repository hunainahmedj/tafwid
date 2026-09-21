# Tafwid contributor instructions

Tafwid is a Codex plugin. The distributable plugin is under `plugins/tafwid`;
its skill, Python runtime, dashboard, references and offline tests are under
`plugins/tafwid/skills/delegate`. The thin dashboard, settings and scout entry points
are sibling skills sharing that runtime. Read README.md before changing behavior.

- Keep provider-specific authentication, commands and permissions explicit.
- Claude Code and the experimental OpenCode adapter (OpenRouter/Zen, LM Studio/vLLM) are
  implemented. Do not advertise other planned adapters as supported.
- Local inference connections are private user configuration, never machine-specific
  source defaults. Model discovery is not proof of working tool calls. Preserve
  endpoint identity on resume and keep credential values out of run artifacts.
- Scout and worker execution support OpenRouter and Zen;
  catalogue metadata and recorded run outcomes are not acceptance benchmarks.
- Keep dashboard usage out of routine completion context. Missing tokens/cost
  remain unknown; Claude API-equivalent cost is not a subscription charge.
- Keep runtime state, credentials, task transcripts and private evidence out of Git.
- Preserve task-local delegation, independent acceptance review and compact context.
- Tests use isolated temporary homes and fake worker executables. Do not make real
  model requests or change the developer's installed plugin during ordinary tests.
- Run `make test` for runtime changes, and `python3 scripts/check_package.py` for
  packaging changes. UI changes also need a visible desktop/mobile check.
- Use release versions in both manifests consistently; preserve license notices.
