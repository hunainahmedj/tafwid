# GPT account workers

Use the `tafwid:account` skill to add a named GPT account. The user completes sign-in and confirms the account and workspace. A login check reports the authentication method; it cannot identify the account or show remaining usage.

For each GPT assignment, use its exact enabled connection. Read mode uses a read-only sandbox. Edit mode uses workspace-write. A resume keeps the same account, task, and workspace. If an account is unavailable, stop that assignment and report what the user needs to fix.
