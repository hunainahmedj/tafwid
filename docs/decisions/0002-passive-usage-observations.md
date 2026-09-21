# ADR-0002: Observe account limits and worker usage without model prompts

- Date: 2026-09-21
- Status: Accepted

## Context

Worker token totals, context occupancy and subscription allowance answer
different questions. Users need account limits and resets alongside usage since
a selected message, without spending inference tokens to obtain those numbers.

## Options considered

- Estimate allowance from token totals: simple but misleading because provider
  allocation rules, other sessions and reset windows are not encoded in tokens.
- Read credentials and call an internal provider HTTP endpoint directly: avoids
  model prompts but makes Tafwid responsible for credential handling and refresh.
- Ask the installed Claude client for quota metadata and read registered worker
  usage locally: retains native authentication and avoids inference, at the cost
  of compatibility with version-sensitive client/log formats.

## Decision

Use the third approach. A bounded Claude subprocess receives only `initialize`
and `get_usage` control requests, never a user message. Disable hooks, tools,
project/user settings discovery and MCP servers for that subprocess; retain
Claude's subscription authentication. Do not use `--bare`, which disables OAuth.
Persist only normalized windows, observation times and an opaque account
fingerprint. Never persist raw auth/control responses or read credential stores.

Keep account observations independent of task filters. Read per-response/step
token evidence only for registered workers. Use completion timestamps for time
filters and keep context measurements separate for every worker session.
Do not reconstruct missing history, infer capacity from model names, or subtract
observations across changed accounts or reset windows.

## Consequences

Dashboard refreshes require no model prompts or extra worker instructions.
Quota retrieval is asynchronous and throttled, and parsing caches retain only
bounded metadata. Unsupported Claude versions or auth failures preserve an
explicit stale/unavailable state. A quota difference includes other activity
on the account and cannot be attributed to the selected worker.

The first/peak/latest context values are request occupancy observations, not a
sample exactly at the user's message or a guarantee about current live context.
Response-level attribution cannot split a response that crosses a time boundary.
The [dashboard reference](../../plugins/tafwid/skills/delegate/references/dashboard.md)
owns collection intervals, retention, field semantics and coverage limits.
