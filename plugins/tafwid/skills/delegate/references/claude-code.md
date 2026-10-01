# Claude Code workers

This guide explains Claude Code’s tools, permissions and session behavior.
Use it with [the delegation workflow](workflow.md).

Claude loads its own configuration, plugins and hooks. It does not inherit the coordinator’s chat, plugin installation or tools.

## Tools

The `delegate.py` argument `--mode` controls which built-in tools are
available to Claude:

| Mode | Available tools |
|---|---|
| `--mode read` | Read, Glob, Grep, Skill and ToolSearch. |
| `--mode edit` | All read-mode tools, plus Edit and Write. |

Bash is available in edit mode when you use full permissions or provide
a scoped Bash allowance. See the permissions section below.

Claude may also have MCP tools from its own configuration. These are
separate from the built-in tools listed above.

## Permissions

The `delegate.py` argument `--permissions` controls Claude’s approval policy:

| Setting | Behavior |
|---|---|
| `scoped` | Preapproves the enabled inspection and editing tools. Shell commands and MCP tools need explicit allowances. |
| `full` | Uses Claude’s `bypassPermissions` mode for available tools. Edit workers get Bash without individual command allowances. |
| `inherit` | Uses `full` when Codex currently reports full access; otherwise uses `scoped`. |

Full access remains subject to host and organization restrictions.

### Scoped allowances

For shell commands, use edit mode and provide an allowance:

```bash
--mode edit \
--permissions scoped \
--allow-tool 'Bash(python3 -m unittest *)'
```

Allow a specific MCP tool using its exact configured name:

```bash
--allow-tool mcp__server__tool
```

Repeat `--allow-tool` for additional allowances. Allowing a tool does not
install or configure it.

## Notes

- Resume workers through `delegate.py`, following [the workflow](workflow.md). Do not use Claude’s global `--continue`, which can select another conversation.
- If Claude rejects a launch or resume option, check `claude --help` for supported arguments.
- Offline tests use fake workers. They do not verify a real Claude installation, login or live integration.
