# Delegation benchmarks

Tafwid's goal is to let Codex coordinate external work without spending more
model usage on coordination than the work warrants. We measure the coordinator,
any native monitoring agent, and Claude workers separately. A completed worker
run is not automatically an accepted task; independent checks and required UI
walkthroughs remain part of the measured task.

## What is measured

- **Time:** the Codex task turn from its first benchmark request through its
  final answer, including implementation, waiting, corrections and acceptance.
- **Codex tokens:** input plus output recorded for each coordinator model
  request. Cached input is included in input, not subtracted from the total.
- **Monitor tokens:** native agent usage, if a monitoring agent is used.
- **Claude tokens:** all reported model usage from each worker launch and resume,
  including cache reads and cache creation.
- **Quality:** task-specific checks run independently after the task turn.
  Browser evidence is assessed separately from HTTP checks.

The combined token figure adds usage reported by separate providers. It is
useful for comparing runs, but is not a subscription charge or a measure of
remaining quota. A cached token is counted each time it appears in a request;
that does not mean the model generated that token again.

## Stop-hook trials

The table compares the last Luna-monitor trial with the first packaged
Stop-hook trial for each task. Each pair used the same frozen fixture and task
requirements. Coordinators used `gpt-6-astra` at high effort; Claude launches
and resumes used `claude-opus-5-5` at medium effort. Trials ran in separate,
fresh Codex chats with full access and no approval prompts.

| Task | Wait method | Time | Coordinator requests / tokens | Monitor tokens | Claude tokens | Combined tokens | Independent result |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| Crawl | Luna, R11 | 10.55 min | 14 / 591,309 | 255,872 | 2,342,755 | 3,189,936 | 26/26 and large-price probe |
| Crawl | Stop hook, R12 | 7.94 min | 14 / 641,003 | 0 | 1,748,100 | 2,389,103 | 26/26 and large-price probe |
| Signal Desk web app | Luna, R2 | 17.85 min | 65 / 4,926,231 | 415,582 | 4,840,246 | 10,182,059 | 15/15 API checks |
| Signal Desk web app | Stop hook, R3 | 19.41 min | 35 / 3,016,840 | 0 | 5,350,845 | 8,367,685 | 15/15 API checks |
| Exact scheduler | Luna, R2 | 18.53 min | 36 / 1,652,440 | 730,931 | 4,596,892 | 6,980,263 | 10/10 check groups |
| Exact scheduler | Stop hook, R3 | 13.50 min | 13 / 567,609 | 0 | 2,345,633 | 2,913,242 | 10/10 check groups |

The Stop hook replaced Luna and dedicated idle coordinator polling in all
three tasks. In the crawl trial, two hook waits lasted 261.1 and 72.3 seconds
with no coordinator model requests between arming and notification. The web app
and scheduler request audits likewise found zero dedicated idle polling requests.
The web app collector initially labeled three mixed-purpose requests as waits;
manual inspection showed worker-result retrieval, report inspection and browser
interaction instead. The scheduler collector found none.

The R3 web app completed visible desktop/mobile, keyboard, export, recovery,
deletion and empty-state checks. Its first suite passed 42 tests; focused worker
corrections followed. The independent evaluator passed all 15 API checks. Its
recorded mobile viewport was 390×843 rather than the specified 390×844, so the
exact-size visual evidence has a one-pixel limit. The R3 scheduler's 51
regression tests, seven focused independent-verifier tests and all 10 external
check groups passed.

These are single runs per variant. Implementation and correction choices
differed, including the number of Claude worker runs. The token and elapsed
time changes cannot be attributed entirely to the hook. The direct finding is
that the packaged hook removed Luna and idle coordinator polling while
preserving completion and independent acceptance on these three tasks. In the
crawl pair, the coordinator alone used more tokens with the hook, even though
combined Codex usage fell when Luna was removed.

## Repeating a trial

1. Freeze a starting fixture and task prompt, and record hashes for the fixture
   and installed plugin files. Keep the evaluator unavailable to the task chat.
2. Use a fresh chat for each variant. Record the coordinator model, effort,
   access and approval policy, plus the actual worker models and effort. Keep
   preparation outside the measured task turn.
3. Run compared trials serially when timing matters. Let the task finish all
   worker, correction and acceptance work before stopping the clock.
4. Run the same independent evaluator on a disposable copy after each task.
   Record visible UI evidence separately where applicable.
5. Collect each model response once, with cached input included. Classify
   waiting requests by inspecting their actions; a process-result read or UI
   interaction is not necessarily an idle poll.
6. Repeat before treating a token or timing difference as stable. Report
   quality and unresolved acceptance gaps alongside usage.

The current fixture copies, prompts, raw rollouts, worker records and evaluator
outputs are private local benchmark artifacts under the user's Codex home. They
are deliberately not committed because they can contain task transcripts and
machine-specific paths. This document records the method and results, but a
fresh clone of this repository alone cannot replay those exact workloads. A
future public benchmark suite should use sanitized, versioned fixtures and an
independent evaluator.
