# Contributing

Start with README.md and docs/architecture.md. Keep contributions scoped and
document user-visible changes in CHANGELOG.md. Discuss new providers before
adding their dependencies or changing shared permission/billing behavior.

Run `make test` with Python 3.10+ and Node.js 20+. It checks packaging, Python
regressions and dashboard logic using offline fixtures. UI changes also need a
visible desktop/mobile pass against an isolated local state directory.

Do not use your personal run history as fixtures. Use synthetic tasks, temporary
homes and a fake worker executable. Never commit credentials, auth files, task
transcripts, local dashboard tokens or private workspace paths.

The supported operating systems are macOS and Linux. CI exercises Python 3.10
and 3.13 on both. Local plugin installation can be tested without changing your
normal Codex configuration:

```sh
test_home=$(mktemp -d)
CODEX_HOME="$test_home" codex plugin marketplace add "$PWD"
CODEX_HOME="$test_home" codex plugin add tafwid@tafwid
```

Use a separate test home for runtime checks as well. Starting a dashboard there
does not require Claude authentication. A live Claude test uses the account's
quota and should be requested explicitly; ordinary CI never does this.

## Releases

Update VERSION, the plugin manifest version, and CHANGELOG.md. Run `make test`,
review the staged file list for private material, and commit. Pushing a matching
`v<VERSION>` tag runs CI before publishing a source archive and SHA256 checksum.
Never create a release from private local runtime state.
