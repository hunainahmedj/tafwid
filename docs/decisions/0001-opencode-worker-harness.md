# ADR-0001: Use OpenCode for API-backed workers

- Date: 2026-09-21
- Status: Accepted

## Context

Tafwid needs workers for hosted free models and user-operated model servers.
A model API alone cannot inspect a workspace, edit files, run checks, or retain
a coding-agent session. Those operations require an execution harness.

## Options considered

- Build a new tool loop in Tafwid: complete control, but duplicates tool,
  session, permission and provider integration work.
- Add a separate harness for each provider: provider-specific flexibility,
  with more lifecycle and resume behavior to maintain.
- Reuse OpenCode alongside Claude Code: an existing CLI supplies tools and
  native sessions, while Tafwid retains orchestration and acceptance review.

## Decision

Use OpenCode for OpenRouter, OpenCode Zen and configured OpenAI-compatible
LM Studio/vLLM servers. Retain the Claude Code adapter as the default backend.
Keep provider preflight and configuration separate from process/session handling.
See [architecture](../architecture.md#backend-boundary) for the shared contract.

Model selection is explicit. Main/helper models are pinned, provider changes
require fresh sessions, and connection changes prevent local-worker resumes.
Hosted candidates must pass the free-price/tool-capability gate; local servers
use private user configuration and declared capabilities. Neither route silently
falls back to another provider. Credentials remain in the harness's auth store
or private environment/file references, outside the distributable package.

## Consequences

One adapter supplies tool execution for several inference providers, preserving
task switches, instruction retention, permissions, run history and usage evidence.
The harness runs tools in the orchestrator's workspace even when inference uses
a remote GPU. Availability, authentication and telemetry remain provider-specific.
Tafwid does not control every detail of the SDK's inference transport.

Catalogue metadata is not a quality benchmark and reported cost is not a billing
cap. Codex retains independent acceptance review. See the recorded
[OpenRouter](../opencode-trial.md), [Zen](../zen-trial.md) and
[self-hosted](../local-inference-trial.md) trials for observed limits.
