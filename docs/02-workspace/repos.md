# Repositories and packages

This is an embedded documentation tree in the Tafwid Git repository.
Adjacent personal projects are outside this documentation scope.

| Path | Role |
| --- | --- |
| `plugins/tafwid/` | Distributable Codex plugin, including manifests, skills, hooks, and brand assets |
| `plugins/tafwid/skills/delegate/` | Python worker runtime, backend references, and isolated offline tests |
| `plugins/tafwid/skills/account/` | Named-account user-facing skill entry point |
| `scripts/check_package.py` | Source/package integrity validation |
| `docs/` | Archivist documentation and existing user guides |
| `docs/superpowers/` | Working specs and implementation plans, preserved in place |
| `prototypes/agent-office/` (planned, [TAF-2](../01-project/backlog.md)) | Local sample-data dashboard; design reference, outside the distributable plugin |

## Documentation migration

The complete former `docs/architecture.md` content moved to
[system architecture](../03-architecture/system.md); its old path remains a
pointer. The original `docs/roadmap.md` content moved to the
[project roadmap](../01-project/roadmap.md), with the office phases added;
its old path also remains a pointer. Account, migration, benchmark, and
brand-asset guides retain their existing locations and content.

## New machine setup

The repository vendors Archivist hooks and briefing pointers. No separate
docs checkout is needed. Hook configuration is present for Codex and
Cursor; execution still depends on each host's hook support and trust.
