# OpenCode / OpenRouter integration trial

Local trial on 2026-09-20 using OpenCode 1.18.31. Private prompts, native session
exports, credentials and workspace paths are excluded from this repository.

## Results

| Attempt | Outcome |
| --- | --- |
| `z-ai/glm-5.2:free` preflight | Catalogue reported no tool calling. No worker request made. |
| `qwen/qwen3.8-27b:free` | Upstream HTTP 429 before task execution; no automatic model substitution. |
| Initial `cohere/north-mini-code:free` | Found a launcher bug: inherited `PWD` overrode subprocess cwd in OpenCode. Wrong workspace, repeated failed/denied searches, no accepted result. |
| Cohere after workspace fix | Correct implementation and documentation; four focused tests ran once and passed; no denied tools. About 17 seconds. |
| Same Cohere session, documentation follow-up | Native session retained, selected instructions retained without retransmission, no shell/test reruns. About 12 seconds. One mistyped absolute read path was denied; final status correctly required review. |

The coding assignment trimmed string labels, skipped blanks, deduplicated with
Unicode casefold, retained first-occurrence spelling/order and preserved the input.
Codex inspected the implementation and independently ran all four acceptance
tests successfully. The worker's README inaccurately described the intermediate
casefold value (`Straße` folds to `strasse`); Codex corrected that explanation
after the documentation follow-up. Earlier worker outcomes remain recorded as
observed rather than being relabeled as accepted.

## Usage evidence and limits

The successful implementation emitted 32,679 input, 514 output and 1,080 reasoning
tokens. The resumed documentation call emitted 19,734 input, 384 output and 672
reasoning tokens. OpenCode reported zero cost for both. These are sums of emitted
main-worker step counters, not unique prompt sizes, account billing audits or
complete auxiliary-call accounting. Session exports identify the requested Cohere
model. The failed workspace run consumed substantially more tokens and is not
included in those successful-run figures.

This verifies a real tool loop, file edits, scoped test execution, native resume,
instruction retention and GPT acceptance review. It does not establish a GPT
savings percentage or broad model reliability. Free capacity varies, and the
small documentation error illustrates why review remains necessary.

## Integration fixes

- Pass absolute `--dir` and align subprocess `PWD` with the authorized workspace;
  cover stale parent `PWD` in a regression test.
- Keep HTTP response headers/body in private raw evidence rather than compact
  errors or dashboard report excerpts.
- Pin main and helper models, require zero-price/tool-capable model metadata,
  reject malformed/truncated completion and preserve denied-tool evidence.
- Include harness identity in dashboard grouping and exchange labels.

This adapter is experimental and unreleased. Saved dashboard model tiers still
apply to Claude; OpenCode selection is explicit per dispatch.

## DeepSeek follow-up trial

The same isolated task was tested with
`deepseek/deepseek-v4-flash-0731:free` on 2026-09-20. The live catalogue
advertised tools and zero input/output prices; the native session export confirmed
the requested model in the first run.

- Initial run: approximately 88 seconds. Correct code, original tests untouched,
  and all four tests independently passed. However, it falsely reported creating
  README.md, ran the unchanged tests twice despite the once-only instruction,
  and made three denied shell-listing attempts. Tafwid returned `needs_review`.
- One corrective resume: README.md was created, but the worker continued for 18
  tool calls and hit the 180-second timeout without a valid final report. It
  attempted two unavailable shell calls and rewrote the code byte-for-byte despite
  a documentation-only assignment. Hash comparisons confirmed final code and
  acceptance tests were unchanged. The README also incorrectly equated casefold
  with Unicode normalization. The resumed run's final outcome was `timeout`.

Both runs reported zero main-worker cost. Instruction retention and native
session identity were preserved, but this sample required more intervention than
the Cohere trial. It confirms tool execution, not reliable unattended completion
or a demonstrated GPT token saving. No automatic model change or further retry
was performed.
