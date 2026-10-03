# Changelog

## 0.5.0

- Add an opt-in local activity log. `python3 scripts/world.py on|off|status` switches it;
  it is off by default and nothing is written until you turn it on. When on, hooks append
  one short event per session start, prompt, tool call, permission request, subagent
  start or stop, stop, session end and notification to `~/.tafwid/state/world`
  (`$TAFWID_HOME/state/world`), kept for 7 days. Events hold only derived labels (an
  action such as `run-tests`, the host, a project folder name, a short worker label and
  role) and hashed session and agent ids. Prompts, file paths, commands, tool input and
  output, and raw ids are never recorded.
- Register async observer hooks for Claude Code and Codex. They exit at once when the log
  is off and never print or block, so they cannot disturb a session. Existing completion
  hooks are unchanged.
- After updating, Codex asks to trust Tafwid's hooks once more, because Codex re-prompts
  whenever `hooks.json` changes (`/hooks` in the CLI). Until you trust them, the
  `wait.py` fallback applies. Claude Code needs no trust step.
- Measured on an M5 Max, 150 runs of the registered hook command with a Claude PreToolUse
  payload: median 4.7 ms with the log off and 29.8 ms with it on. The hooks run
  asynchronously, so neither adds wait time to a turn. They start Python with `-S`
  (stdlib only) and import modules lazily to stay within that budget.

## 0.4.0

- Support Claude Code as a coordinator alongside Codex, with Claude Code marketplace
  and plugin manifests.
- Keep state in a host-neutral home, `~/.tafwid/state`, shared by both coordinators.
  Existing state under the Codex home is used in place until `settings.py migrate`.
- Share one hooks file between hosts; on Claude Code the prompt hook records that
  hooks are active and the session's permission mode.
- Record run ownership as `coordinator_task_id` and `coordinator_host`; older
  records remain readable.
- Hook actions no longer exit with a blocking status when state is unreadable.
- Keep an armed completion hook valid until the turn ends; a slow final reply no longer
  expires it after two minutes and silently skips the resume.
- Rename the `codex_full_access` permission result field to `coordinator_full_access`.
- Fix personal GPT account setup on Python 3.10 when the optional account type is omitted.
- Add named personal and Business GPT worker accounts with private Codex homes,
  visible sign-in, and user confirmation.
- Let each task enable Claude and multiple GPT connections, with exact routing
  for every worker run and resume.
- Keep completion monitoring and legacy Claude switch state compatible.
- Remove the dashboard and account/activity collection, native handoff protocol,
  Superpowers adapter and automatic instruction-file delivery.
- Keep task switches, launch/resume, compact completion waiting and CLI settings.
- Split shared workflow and Claude guidance; document scripts and CLI help.
- Preserve private run artifacts and existing saved state.
- Add a trusted, one-time completion hook that resumes Codex when a selected
  worker finishes; retain `wait.py` as the fallback.
- Document benchmark method and measured results for crawl, web app and
  exact-scheduler tasks.

## 0.2.0

- Replace the all-purpose skill with delegate, dashboard, and settings entry points.
- Load the worker workflow only for delegation work, preserving review and handoff rules.
- Share one runtime across the three skills; preserve task state and worker history.
- Check entry-point names and packaged Markdown links in release validation.

## 0.1.1

- Simplify the title to Tafwid.
- Add a coordinated icon and cover image to the plugin listing and README.
- Validate bundled image paths and PNG signatures during package checks.

## 0.1.0

- Package the existing delegation skill and local dashboard as Tafwid.
- Add a portable Codex marketplace and plugin manifest.
- Use provider-neutral product branding, with Claude Code as the initial backend.
- Preserve legacy task switches, settings and worker history in place.
- Add installation, contributor, migration and architecture documentation.
- Add isolated CI and tagged source-release workflows.
