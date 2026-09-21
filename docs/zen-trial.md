# OpenCode Zen execution trial

Tested 2026-09-20 with OpenCode 1.18.31 and `opencode/big-pickle`, using public
access and a disposable synthetic Python fixture. No project source or account
key was sent. These observations validate a small integration sample, not a
general model-quality benchmark. The installed Tafwid plugin was not changed.

## Initial coding run

The worker repaired `normalize_labels`: trim whitespace, remove empty labels,
deduplicate with Unicode casefold, retain first spelling/order, and preserve
the input. Only the implementation file was edited. The four supplied tests
were unchanged and were run once by the worker after its edit. Independent
inspection and a separate four-test acceptance run passed.

- Native session export confirmed `opencode/big-pickle` and the intended workspace.
- Elapsed launcher time: 35.5 seconds.
- Main-worker usage: 5,496 input, 1,293 output, 28,672 cache-read tokens.
- Harness-reported cost: $0; no invoice verification is implied.
- One initial `ls -la` request was denied by the scoped command policy. The worker
  recovered using permitted glob/read tools. Its launcher outcome remained
  `needs_review`; the successful independent acceptance did not rewrite history.

## Resume trial

A documentation-only follow-up reused the same native session and model. The
instruction manifest recorded unchanged selected instructions as `retained`,
with zero instruction characters retransmitted. Code and acceptance-test hashes
remained unchanged.

Zen rejected the request with HTTP 403 and the message “OpenCode's free tier can
only be used from within OpenCode.” No README was created, no tool work was
performed, and no usage/cost was reported. Elapsed launcher time was 2.3 seconds.
No repeat inference request, identity spoofing, credential change or model
fallback was attempted.

The original artifact records an error. The subsequent error-classification fix
was tested by replaying that saved event locally: provider HTTP 403 is now
`blocked` with `failure_kind=provider_access_denied`. Original trial records were
not relabelled. The fake-process integration test verifies successful Zen resumes,
but a successful live resume remains unverified.

Similar rejection reports exist in the upstream
[official-app issue](https://github.com/anomalyco/opencode/issues/49588) and
[free-tier issue](https://github.com/anomalyco/opencode/issues/49580). These reports
do not establish the exact cause of this trial's rejection or a verified remedy.

## Execution boundaries

Every launch/resume fetches current Zen IDs and models.dev pricing/capabilities.
Unknown prices, paid models, absent tool support, unavailable catalogues and
unrecognized SDK transports stop launch. The main worker and helper agents are
pinned to the selected model; only that model/provider is enabled. A different
provider requires a fresh worker. The harness handles configured account keys,
or its native public-access path when none is configured. Catalogues and local
cost reporting are not a hard billing cap.

A later configured-account attempt timed out without usable worker events;
it did not establish authenticated execution or a successful resume. Other Zen
models have offline coverage only.
Do not infer that every listed free model is usable from the successful initial
Big Pickle run. Provider availability and free-tier restrictions remain external.
