# Self-hosted workers: LM Studio and vLLM

Use only when the user selects self-hosted inference. OpenCode runs in the
orchestrator's workspace and executes its tools there; the configured server
performs inference. A remote GPU does not move file edits or test execution to
that machine. Relevant prompts and source excerpts go to that server.

Connections are private, per-user settings in Tafwid's state directory, not
machine-specific source code. No cloud provider catalogue or key is required.
The model and all OpenCode helper models are pinned to the selected connection;
there is no cloud fallback. Keep acceptance review and task-local delegation.

## Register a connection

Start the user's existing LM Studio/vLLM server and obtain its exact served ID
from `/v1/models`. Do not download or replace an existing model merely to match
an example. Use the server's configured context limit, not the checkpoint's
advertised maximum. vLLM must have automatic tool choice and the appropriate
model-specific tool parser enabled. LM Studio must support that model's tool
format. A model-list response alone does not establish usable tool calling.

```sh
python3 "${TAFWID_SKILL_DIR}/scripts/local_models.py" add \
  --name laptop --kind lmstudio --base-url http://127.0.0.1:1234/v1 \
  --model YOUR_SERVED_MODEL_ID --context 32768 --output 4096 --tools

python3 "${TAFWID_SKILL_DIR}/scripts/local_models.py" add \
  --name gpu --kind vllm --base-url http://YOUR_PRIVATE_HOST:8000/v1 \
  --model YOUR_SERVED_MODEL_ID --context 32768 --output 4096 --tools
```

`--tools` explicitly declares server capability; it is not a benchmark or a
successful tool-call test. Verify a bounded edit/test/resume trial before using
a new setup for substantial work. Omitting it prevents worker launch. Register
another name for another model or machine. Adding an existing name updates it;
an existing worker cannot resume across a changed connection configuration.

Supported destinations are loopback, private LAN, and private overlay networks
(including Tailscale). URLs must end in `/v1`, without query strings, credentials
or fragments. Discovery does not follow redirects or use an HTTP proxy. This
validates intended private destinations; it is not an OS network sandbox or a
guarantee against a compromised server/DNS. Use trusted endpoints and keep
firewall/network policy in place. The plugin never changes those policies.

If authentication is enabled, add `--api-key-env LOCAL_MODEL_API_KEY`, or
`--api-key-file /absolute/path/to/private.key`. The file contains only the token;
use mode 600. Never put the token in a brief, CLI argument, connection JSON or
chat. OpenCode resolves the credential reference locally. Tafwid sends it only
to the configured endpoint during model discovery. Use dedicated credentials;
do not reuse a hosted-provider key. No authentication is required by Tafwid when
the local server does not require it.

```sh
python3 "${TAFWID_SKILL_DIR}/scripts/local_models.py" list
python3 "${TAFWID_SKILL_DIR}/scripts/local_models.py" check --name laptop
```

`check` verifies the connection, model availability, declared tools and known
context bounds; it performs no inference. Each dispatch/resume repeats this
small local check. It does not load a cloud catalogue or forward these setup
instructions into the worker's context.

## Dispatch and resume

```sh
python3 "${TAFWID_SKILL_DIR}/scripts/delegate.py" --backend opencode --once \
  --cwd /absolute/workspace --prompt-file /private/brief.md \
  --output-dir /private/run-1 --model local-laptop/YOUR_SERVED_MODEL_ID \
  --title "Implement the focused change" --role implementer --mode edit \
  --allow-command 'python3 -m unittest *'
```

Use `local-gpu/YOUR_SERVED_MODEL_ID` for the other example connection. IDs may
contain `/`, as many served checkpoint names do. The `local-NAME/` prefix is
the connection identity in OpenCode and the dashboard. Normal permissions,
instruction deduplication, compact waiting, structured handoffs and acceptance
review apply. Resume with `--resume-from /private/run-1`, a new output directory,
and the appropriate mode/command allowances. A connection/model change requires
a fresh worker. Start with one worker per server; concurrency consumes context
cache and can reduce throughput.

Dashboard token/rate figures use the existing OpenCode evidence. Missing tokens
stay unknown. The usage source identifies self-hosted inference; a zero
harness-reported cost is not an estimate of electricity or hardware costs.
Saved Claude task-tier routing is unchanged; select local models explicitly.

Official setup: [LM Studio](https://lmstudio.ai/docs/developer/openai-compat),
[LM Studio authentication](https://lmstudio.ai/docs/developer/core/authentication),
[vLLM tool calling](https://docs.vllm.ai/en/latest/features/tool_calling/).
