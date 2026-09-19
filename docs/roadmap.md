# Roadmap

## Implemented in 0.1

Claude Code delegation from Codex; task-local on/off; model routing and permission
settings; bounded completion waiting; generic instruction handoff and resume
deduplication; worker/run dashboard; public orchestrator activity; test evidence
and acceptance-review guidance.

## Next

- More actionable timeout, crash and quota reports, including unfinished work and
  cleanup evidence.
- Consolidated review/correction checkpoints without removing independent review.
- Backend adapter extraction with a real second implementation.
- Cursor and OpenCode adapters, each with explicit permissions and resume rules.
- OpenRouter execution integration, including opt-in free-model selection with
  paid fallback prevented explicitly.
- Broader platform and live compatibility coverage.

No dates or support claims are implied for planned integrations. Track concrete
work through repository issues once the project is published.
