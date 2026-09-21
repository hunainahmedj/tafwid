# Roadmap

## Implemented in 0.1

Claude Code delegation from Codex; task-local on/off; model routing and permission
settings; bounded completion waiting; generic instruction handoff and resume
deduplication; worker/run dashboard; public orchestrator activity; test evidence
and acceptance-review guidance.

## Next

The current checkout includes an experimental OpenCode/OpenRouter/Zen free-model
adapter. It uses explicit model IDs; shared task-type routing across harnesses
and a provider selector in Settings remain future work.

Named self-hosted LM Studio/vLLM connections also use the OpenCode adapter.
Connection setup is currently CLI-based, with configurable private endpoints,
context limits and credential references. GUI connection management and shared
task-type routing remain future work.

The checkout also includes cached scouting for free OpenRouter/Zen candidates
and dashboard usage metrics. Repeatable bounded evaluations and
accepted quality scores remain future work; metadata-based candidates and local
run outcomes are deliberately separate.

- More actionable timeout, crash and quota reports, including unfinished work and
  cleanup evidence.
- Consolidated review/correction checkpoints without removing independent review.
- Cursor and additional adapters, each with explicit permissions and resume rules.
- Harness/provider selection and saved OpenRouter task-type model mappings.
- Broader platform and live compatibility coverage.

No dates or support claims are implied for planned integrations. Track concrete
work through repository issues once the project is published.
