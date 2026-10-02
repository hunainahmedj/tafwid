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
