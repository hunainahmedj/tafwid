# Set up GPT worker accounts

Use `$tafwid:account add gpt` for a personal ChatGPT account or
`$tafwid:account add gpt business` for a Business account. Tafwid asks for a
short, unique name, announces its private Codex home, and opens Codex sign-in.
Complete the browser or device-code login yourself. Then confirm that you used
the intended account and workspace. Until you confirm, the account stays pending.

Each named account has its own `CODEX_HOME` under Tafwid's private state. Tafwid
does not copy or read credentials. Your ordinary Codex CLI home and sign-in remain
unchanged. A private home selects CLI authentication; it is not a separate macOS
user or filesystem security boundary.

`$tafwid:account list` shows names, types, and status. `$tafwid:account check NAME`
runs `codex login status` for that home. It makes no model request and reports
only whether the method is clearly ChatGPT. It cannot identify the account or
workspace, verify a data-processing agreement, or show remaining usage. If login
expires, retry sign-in and confirm the intended account again.

To use accounts in a task, enable each one with `$tafwid:delegate on gpt NAME`.
`$tafwid:delegate on claude` can add Claude to the same pool. Route each worker
assignment with `--connection gpt:NAME` or `--connection claude`. Separate
assignments may run at the same time; Tafwid does not split or balance work
automatically. A failed assignment stays on its chosen connection.

The coordinating task, in Codex or Claude Code, still receives the user's request
and reviews the worker's result. For Business-only data under a Codex coordinator,
start that coordinating task while signed into the Business account. A Claude Code
coordinator sends the request to your Claude account instead. The `business` label is user-confirmed metadata,
not proof of any workspace policy or contract.
