# Workers dashboard

Run `python3 "${TAFWID_SKILL_DIR}/scripts/dashboard.py" start` and open the returned URL in Codex. Use the full URL, including its fragment: it carries a local access token and the current task filter. Repeating `start` reuses the running server. After a restart or reboot, run it again to get the current link. There is no scheduled background launch.

## What it shows

- Active and Done lists contain one worker per Claude session and Codex conversation, with a run count on each card. A resumed invocation continues that session and appears inside its history. Missing session IDs stay separate; unrelated conversations never merge.
- Filter by conversation, requested model, role, status (including Needs attention), and start time. Filters match individual runs, then show the whole matching worker with its complete recorded history. A card shows the latest run's model/role/outcome, or an active status while any run is active; a previous failed run may match even when the latest run succeeded. The card title comes from the earliest recorded run.
- Started offers 15/30 minutes, 1/3/6/12/24 hours, 7/30 days, **Since latest user message**, and **Since a chosen message**. Message filters require one selected conversation. Latest follows new user messages automatically; choosing a message pins that starting point through later messages and refreshes. The message picker shows timestamps and short request previews, including replies to clarification questions. It reads up to 200 recent requests from the local task log, skipping known injected context. Missing logs/messages show no matches and an explanation, never an unfiltered result. These are time boundaries for run starts, not semantic assignment to a feature: an earlier run that remains active is excluded unless that worker has a later matching run. Matching workers still include their full run history.
- Sort within each list by newest/oldest latest-run start, last update, longest/shortest total run duration, or worker title. Duration sums recorded invocation durations, excluding time between runs. Search includes conversation names and status labels.
- “This conversation” selects the conversation encoded in the launch link; “Opened from” names it explicitly. The conversation dropdown can select any recorded conversation. It does not follow the active Codex window automatically.
- Filtered counts distinguish unique workers from matching runs. Active and Done count workers, and Done includes failed/blocked workers. The coordinator section shows the full recorded totals for each selected conversation, irrespective of other filters.
- Filters and sorting persist in the URL fragment through refresh. Reset restores the link's original conversation, clears other filters and returns to newest-first sorting.
- A human-readable title (`delegate.py --title`), requested model, role, elapsed time, and outcome.
- An Exchanges tab shows each run in chronological order: Codex's recorded instructions, then the saved report or launcher outcome. The other tabs have a run selector for that invocation's report, brief, diagnostic stderr, and metadata.
- Codex coordinators are identified by their actual parent conversation ID and title. The activity view reads their recorded model and public tool/message activity from local task logs, including reviews/tests outside worker handoffs. A completed worker or returned tool call does not prove independent review or acceptance.
- Codex assigns role labels. Some correspond to Superpowers stages; others are task-specific. Labels alone neither select a named plugin agent nor prove a specific role template was supplied. Historical role-template provenance is not recorded.
- Requested profile, effort, selection reason, Claude session, artifact path, and model usage keys. Usage keys can include helper models; they do not prove which model did the main work.

The page refreshes every two seconds. A worker whose launcher stops reporting for more than fifteen seconds is shown as interrupted, with a note to inspect artifacts. This does not prove the Claude process has exited. Completed means the worker finished; Codex still verifies its work. Workers requesting native help or review are distinguished from successful completion.

The dashboard is a separate browser tab. It cannot insert external workers into Codex's native Subagents panel. It cannot stop, resume, or dispatch workers. Its separate Settings page controls model routing and worker permissions for future launcher invocations. Logs are the launcher's diagnostic stderr output, not a streaming Claude tool transcript. Reports normally appear at the end of a run. Exchanges use `input.txt` (launcher contract, brief, supplied instructions), falling back to `brief.md` when unavailable, and `report.md` (the normalized worker result or launcher diagnostic). They are recorded handoffs, not a verbatim chat or complete orchestration trace. Only registered runs are included; missing older history is not reconstructed.

Conversation titles are resolved from Codex's local `session_index.jsonl` metadata on refresh, using the latest recorded title for each ID. Only names for registered workers are returned. Missing titles fall back to an abbreviated ID; no conversation transcript is read. Two conversations with the same name remain separate choices, distinguished by their ID suffix.

## Storage and history

For existing installations, all paths below use `state/claude-delegate` instead
when that is the only state directory. Tafwid reuses settings and history in
place; it stops with a conflict error if both state directories exist.

Records live in `$CODEX_HOME/state/tafwid/workers/` (default `~/.codex`). Each invocation keeps a unique run identifier; grouping changes presentation without deleting or merging records. Finished records cache a bounded copy of the report, brief, full input, and diagnostic log, keeping history readable if temporary artifacts are later removed. Older records may only have the brief cached. Each document is limited to 64 KiB, with a truncation note; the diagnostic log retains its tail. Full artifacts stay at the original run location.

Only new launches are recorded automatically. Import a known older run explicitly:

```bash
python3 "${TAFWID_SKILL_DIR}/scripts/dashboard.py" import \
  /absolute/path/to/previous-run --title "Review the implementation"
```

Import requires its `summary.json`, preserves its recorded model/task information, and is idempotent for the same directory. Do not scan unrelated tasks or directories to discover history.

The service binds only to `127.0.0.1`, and private API data requires the generated token. Keep the launch link private. Registry files and service credentials use owner-only permissions. The dashboard does not send worker data to an external service. `dashboard.py status` reports whether the server is running. Opening the dashboard and importing history never enable delegation.

## Codex activity

Choose **View activity** on a coordinator. The dashboard incrementally reads that registered conversation's local Codex rollout, including existing history. It shows the recorded model/effort, last recorded turn state, public assistant updates, tool-call arguments, and whether a corresponding result was recorded. Search and activity-type filters apply across retained history; older pages stop automatic refresh until **Latest activity** is selected. Latest activity refreshes every two seconds while open. No agent is launched and no model tokens are spent by this reader.

Activity uses an observed local file format, not a stable public API. A missing log is shown as unavailable. The reader resolves only the requested registered conversation, verifies the log's session identity, refuses symlinks/out-of-root paths, and retains at most 5,000 events in memory. Tool/message excerpts are capped at 6,000 characters. Partial appended records are retried on the next read. Internal reasoning, user messages, instruction context, and raw tool-result bodies are excluded from the activity view. The separate message-filter endpoint returns only recorded request timestamps, line identifiers, and previews capped at 240 characters for that registered conversation. It uses the same token/origin and conversation checks. Result markers indicate a return, not success. “Running” is the last recorded turn state, not a process heartbeat; the last-activity timestamp remains visible. No review or acceptance is inferred from tool names or a completed turn: look for explicit public statements and the actual tool actions, then inspect results in the original task when needed.

The activity endpoint has the same local token/origin checks as worker data and rejects conversation IDs with no registered workers. It stores no second copy of task transcripts. Changes to Codex's log format may require updating `scripts/activity.py`.

## Worker permissions

Open **Settings** beside the dashboard title, then the **Worker permissions** section. Select **Scoped**, **Full access**, or **Follow Codex**, then **Save settings**. Unsaved edits do not change configuration; Discard changes restores the last saved values. This is one default for this Codex home across all conversations; the per-conversation delegation switch stays separate. Running workers keep their existing permissions. Every future launch or resume resolves the setting again.

Scoped preserves existing allowances and `dontAsk`. Full access uses Claude `bypassPermissions`; edit workers receive unrestricted Bash, while read workers retain their inspection tool inventory. Task scope and host/organization restrictions still apply. Follow Codex uses full access only when the launching Codex process exposes the recognized full-access signal; missing, restricted, or unknown signals fall back to Scoped. The dashboard does not guess another conversation’s access from its own environment.

Run info displays the requested policy, effective permissions, Claude mode, setting/override source, and reason for new runs. Historical permissions are shown as Not recorded. Saving requires the same local Host, Origin, and bearer-token checks as private APIs, plus a bounded JSON request. Settings use an atomic owner-only file at `$CODEX_HOME/state/tafwid/settings.json`.

## Settings page and model routing

The separate `/settings` page preserves the dashboard link’s private token and filters. **Workers** returns to the same filtered view. It has editable Fast / Standard / Deep model defaults and task overrides for mechanical work, investigation, implementation, debugging, documentation, testing, task review, architecture, and final review. Each override can select Sonnet, Opus, or Fable, or inherit its tier default. Effective model labels update before saving. Save persists models and permissions together; Discard changes restores the last saved values.

Initial tier models remain Sonnet / Opus / Fable. The task’s tier still determines effort (model default / medium / high). Saves do not launch Claude or probe account availability. New `--task-type` launches apply saved routes; `--profile` applies the saved tier alone. Explicit `--model` remains available. Resumes retain the recorded model until a selector explicitly reroutes them. Run info records task type and routing source alongside the requested model. Free-form role names remain descriptive and do not automatically select a route.

Settings schema version 2 adds model maps. Existing version 1 permission settings load with the original model defaults and preserve their permission choice. Saving upgrades the file atomically. Older open permission dialogs and `settings.py set --policy ...` preserve model settings when changing only permissions. Settings apply across this Codex home; they do not enable delegation for any conversation.
