# Changelog

## Unreleased

- Document the OpenCode harness decision, provider trial evidence and scoped
  documentation audit, including the limits of live Zen verification.

- Add configurable self-hosted LM Studio/vLLM workers through OpenCode: named
  private connections, exact served models, declared context/tool capabilities,
  credential references, local discovery and endpoint-pinned resumes. No cloud
  fallback or machine-specific package defaults.

- Execute free OpenCode Zen workers with fresh price/capability checks, native
  public or configured-account access, pinned helper models and session resumes.
  Reject provider switches on an existing worker and unrecognized SDK transports.

- Add `$tafwid:scout` for cached OpenRouter and OpenCode Zen free-model discovery
  with task candidates, source timestamps and separate local outcome evidence.
- Show filtered usage totals, per-worker tokens and per-run usage details.
  Separate reported costs from Claude API-equivalent estimates; preserve unknown
  values and identify effective throughput as including tool/wait time.
- Recover historical usage from available artifacts without altering worker records.
- Add an experimental OpenCode adapter for explicit OpenRouter free models, with
  capability/price preflight and pinned worker/helper models.
- Reuse task ownership, instruction deduplication, scoped command permissions,
  session resumes, compact completion waits and native handoffs.
- Record OpenCode events and token evidence; distinguish requested models from
  session-export evidence. Keep HTTP response headers out of compact errors.
- Label dashboard exchanges by harness and preserve existing Claude workers.

## 0.2.0

- Replace the all-purpose skill with delegate, dashboard, and settings entry points.
- Load the worker workflow only for delegation work, preserving review and handoff rules.
- Share one runtime across the three skills; preserve task state and worker history.
- Check entry-point names and packaged Markdown links in release validation.

## 0.1.1

- Simplify the title to Tafwid.
- Add a coordinated icon and cover image to the plugin listing and README.
- Validate bundled image paths and PNG signatures during package checks.

## 0.1.0

- Package the existing delegation skill and local dashboard as Tafwid.
- Add a portable Codex marketplace and plugin manifest.
- Use provider-neutral product branding, with Claude Code as the initial backend.
- Preserve legacy task switches, settings and worker history in place.
- Add installation, contributor, migration and architecture documentation.
- Add isolated CI and tagged source-release workflows.
