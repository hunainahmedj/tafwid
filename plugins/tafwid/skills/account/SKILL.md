---
name: account
description: Use when the user adds, checks, or lists named GPT accounts for Tafwid.
---

# Tafwid account

Use Tafwid to add and check named GPT accounts. `add gpt` means a personal account; `add gpt business` means a Business account. Ask for a unique short name, then state the account type and private sign-in destination before starting Codex login. The user completes sign-in. Check the login method without reading credentials, then ask the user to confirm the account and workspace. Mark the account ready only after that confirmation. If the user cancels or the login method is unclear, keep it pending. Never use another account as a fallback. Use the account script's `--help` for exact arguments.

The account script is `../delegate/scripts/account.py` relative to this skill. Resolve its absolute path before running it. Use `--help` for arguments and exit codes.

1. `What short name should Tafwid use for this GPT account?`
2. `I'll open Codex sign-in for the {personal|Business} account named {name}. Your own Codex login, if you have one, will stay signed in.`
3. `Did you sign in to the intended {personal|Business} account and workspace?` Choices: `Yes, use this account`, `Retry sign-in`, `Cancel`.
4. For a missing destination: `No GPT account named {name} is ready. Set it up now?` Choices: `Set up account`, `Cancel`.
