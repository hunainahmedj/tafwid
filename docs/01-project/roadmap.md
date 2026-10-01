# Roadmap

Keep the core small: task-local switches, Claude launch/resume, completion waiting,
explicit permissions and concise acceptance evidence.

Priorities:

- Make the entry point and command help easy to follow.
- Measure coordination overhead with reproducible, separately authorized benchmarks.
- Improve reliability using offline fixtures before adding integrations.

New features should justify their runtime and context cost before entering the core.


## Office dashboard sequence

- Prototype the compact office, readable roster, and sample stats before
  integrating live data — [TAF-2](backlog.md).
- Define a task-scoped read-only live view, including freshness and the
  difference between worker completion and accepted results — [TAF-3](backlog.md).
- Develop persistent role-based appearances and personality, reusable
  low-poly assets, and richer office environments — [TAF-4](backlog.md).
- Explore invitations and shared presence with explicit visibility and
  access rules — [TAF-5](backlog.md).

See the [product vision](overview.md) for the intended experience.
