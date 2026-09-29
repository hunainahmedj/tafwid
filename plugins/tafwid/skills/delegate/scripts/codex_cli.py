"""Build restricted Codex CLI worker runs and check their private result files."""

import json
from pathlib import Path
import shutil

import accounts

CONTRACT = "You are a Codex worker for a task assigned by Tafwid. Follow the task brief and the workspace rules. Stay within the assigned files and permissions. Do not delegate again. Do not commit, push, deploy, send messages, or change account settings unless the brief asks you to. If you cannot finish, report what is done and what remains. Return `completed` only when the assignment is finished. Keep your report short: outcome, changed files or findings, checks run, and remaining risks."
OUTPUT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"status": {"type": "string", "enum": ["completed", "blocked"]},
                   "report": {"type": "string", "minLength": 1}},
    "required": ["status", "report"],
}


def check_ready(account: dict, *, cwd: Path | None = None) -> dict:
    """Check one named ChatGPT CLI login without making a model request."""
    checked = accounts.check(account)
    if account["status"] != "ready" or checked["login_method"] != "chatgpt":
        raise ValueError(f"GPT account {account['name']} is unavailable: {checked['reason']}")
    executable = shutil.which("codex")
    if not executable:
        raise ValueError("Install the Codex CLI, then retry this GPT assignment")
    return {"executable": executable, "home": account["home"], "account_id": account["id"]}


def build_command(executable: str, *, cwd: Path, schema: Path, mode: str,
                  model: str | None, session_id: str | None, output: Path) -> list[str]:
    """Build a fresh or resumed CLI command with identical approval limits."""
    if mode not in ("read", "edit"):
        raise ValueError("GPT workers support read or edit mode only")
    sandbox = "read-only" if mode == "read" else "workspace-write"
    common = ["--json", "--output-schema", str(schema), "-o", str(output),
              "-c", 'approval_policy="never"']
    if session_id:
        command = [executable, "exec", "resume", *common,
                   "-c", f'sandbox_mode="{sandbox}"']
    else:
        command = [executable, "exec", *common, "-C", str(cwd), "--sandbox", sandbox]
    if model:
        command += ["--model", model]
    if session_id:
        command += [session_id]
    command += ["-"]
    return command


def parse_result(events: Path, final_message: Path, *, exit_code: int,
                 expected_session_id: str | None = None) -> dict:
    """Accept only a completed turn with a valid structured final report."""
    session_id = None
    ended = False
    failed = False
    try:
        with events.open(encoding="utf-8") as stream:
            for line in stream:
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError("Invalid Codex event")
                if event.get("type") == "thread.started":
                    session_id = event.get("thread_id")
                elif event.get("type") == "turn.completed":
                    ended = True
                elif event.get("type") == "turn.failed":
                    failed = True
        if expected_session_id and session_id and session_id != expected_session_id:
            raise ValueError("Resumed Codex worker belongs to a different thread")
        if expected_session_id and not session_id:
            session_id = expected_session_id
        result = json.loads(final_message.read_text(encoding="utf-8"))
        if (exit_code != 0 or failed or not ended or not isinstance(result, dict)
                or set(result) != {"status", "report"}
                or result.get("status") not in ("completed", "blocked")
                or not isinstance(result.get("report"), str) or not result["report"].strip()
                or not session_id):
            raise ValueError("Codex worker result needs review")
        return {"status": result["status"], "report": result["report"],
                "session_id": session_id, "models_used": []}
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        if isinstance(exc, ValueError) and "different thread" in str(exc):
            raise
        return {"status": "needs_review", "report":
                "Codex worker result is incomplete or invalid. Inspect private events and stderr.",
                "session_id": session_id or expected_session_id, "models_used": []}
