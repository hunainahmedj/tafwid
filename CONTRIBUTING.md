# Contributing

Start with README.md and docs/architecture.md. Keep contributions scoped and
document user-visible changes in CHANGELOG.md. Discuss new providers before
adding their dependencies or changing shared permission/billing behavior.

Run `make test` with Python 3.10+. It checks packaging and Python regressions
using offline fixtures.

Do not use your personal run history as fixtures. Use synthetic tasks, temporary
homes and a fake worker executable. Never commit credentials, auth files, task
transcripts or private workspace paths.
Claude plugins may create a local `.remember` directory while working in this
repository; it is ignored by Git and excluded from the package check.

The supported operating systems are macOS and Linux. CI exercises Python 3.10
and 3.13 on both. Local plugin installation can be tested without changing your
normal Codex configuration:

```sh
test_home=$(mktemp -d)
CODEX_HOME="$test_home" codex plugin marketplace add "$PWD"
CODEX_HOME="$test_home" codex plugin add tafwid@tafwid
```

For Claude Code, load the plugin for one session without installing it, and
validate both manifests before a release:

```sh
TAFWID_HOME="$test_home/tafwid" claude --plugin-dir "$PWD/plugins/tafwid"
claude plugin validate . && claude plugin validate plugins/tafwid
```

Validation reports one expected warning: the `Interrupt` hook is a Codex event
that Claude Code ignores.

Use a separate test home, including `TAFWID_HOME`, for runtime checks as well. A live Claude test uses
the account's quota and should be requested explicitly; ordinary CI never does this.

## Releases

Update VERSION, both plugin manifest versions, and CHANGELOG.md. Run `make test`,
review the staged file list for private material, and commit. Pushing a matching
`v<VERSION>` tag runs CI before publishing a source archive and SHA256 checksum.
Never create a release from private local runtime state.
