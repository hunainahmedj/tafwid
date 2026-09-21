# Self-hosted execution trial

Tested 2026-09-20 with OpenCode 1.18.31, using disposable synthetic Python
fixtures. LM Studio served a 4-bit Qwen3.8-27B model with API authentication;
vLLM 0.26.0 served cached Qwen3.8-27B-NVFP4 through a private overlay connection.
Both used a 32,768-token context and 4,096-token output limit. These small trials
establish integration behavior, not benchmark parity or general model quality.

## Observed behavior

On both connections the initial worker implemented label trimming, blank removal,
Unicode casefold deduplication, first-spelling/order preservation and input
immutability. Each ran the requested four-test command once. Codex independently
reviewed the implementation and reran the unchanged supplied tests: all passed.

Each documentation follow-up reused its original native session and model.
Code/test hashes remained unchanged, no shell or test tools were used, and the
instruction manifest retained existing instructions with zero characters resent.
There were no permission denials or observed model substitutions in these runs.

Acceptance review found issues that successful execution alone did not establish:

- LM Studio's first final response contained prose before JSON, so Tafwid kept
  its outcome as `needs_review` despite correct code. Its resumed response used
  the required report format after explicit feedback.
- LM Studio's documentation overstated what casefold does to Unicode code points.
  Codex corrected the wording to distinguish casefold from normalization.
- vLLM's documentation used an incorrect raw-string equality while explaining
  casefold. Codex changed it to compare the actual `casefold()` results.

The two documentation corrections were native acceptance edits, not successful
self-corrections by the delegated workers. Both vLLM launcher reports were
`completed`; that status did not remove the need for content review.

## Recorded usage

| Server / run | Input | Output | Reasoning | Cache read |
| --- | ---: | ---: | ---: | ---: |
| LM Studio / edit | 35,657 | 912 | 981 | 0 |
| LM Studio / resumed documentation | 39,489 | 1,038 | 966 | 0 |
| vLLM / edit | 33,533 | 1,212 | 0 | 0 |
| vLLM / resumed documentation | 26,786 | 1,423 | 0 | 0 |

These are current-run main-worker step totals reported by OpenCode. Repeated
input across tool steps counts again; totals are not one request's context size.
Zero reasoning/cache fields describe reported telemetry, not proof that no
reasoning or server-side cache reuse occurred. All four reported $0 harness cost;
hardware and electricity were not measured. No GPT token-savings percentage or
controlled throughput comparison was established.

## Configuration and validation

vLLM required automatic tool choice and the `qwen3_xml` tool parser. Initial
startup at 65,536 context tokens exceeded available cache memory; 32,768 tokens
and a reduced concurrency setting started successfully. No image upgrade or
model download was needed. Machine addresses and deployment details remain in
private operational documentation rather than this distributable package.

LM Studio's token file was mode 600. Its value did not appear in the inspected
trial artifacts. The runtime stores credential references, not token values.
Live authenticated execution exercised OpenCode's key-file interpolation.

The offline suite passed 159 Python and 14 JavaScript tests. An independent
static review found no actionable issues in the local-provider addition; it did
not audit the SDK's inference transport. See the [connection reference](../plugins/tafwid/skills/delegate/references/local-models.md)
for discovery safeguards, endpoint trust assumptions and resume restrictions.
The tested plugin package was installed locally; this was not a GitHub release.
