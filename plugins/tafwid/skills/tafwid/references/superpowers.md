# Superpowers worker adapter

This optional adapter applies only when the user or active Codex workflow selects Superpowers. It is not a prerequisite for delegation or a reason to activate Superpowers. Follow the current selected skill and role templates, resolving their paths from the active skill catalog rather than pinning a plugin cache version.

## Roles and context

- Codex handles brainstorming with the user, plan ownership, the task ledger, dispatch, review decisions, and final integration.
- For an implementer, select the current implementer template, task brief, and relevant constraints. Explicitly select any TDD/verification skills required for that assignment with `--instructions-file /absolute/path/to/SKILL.md` (repeatable). The generic [instruction handoff](instructions.md) supplies or resolves each source; do not also tell the worker to load a second installed copy. Role templates use the same flag. Do not forward the controller's entire orchestration workflow.
- For a task reviewer or final reviewer, create a fresh Claude session with the matching review template and review package. Do not reuse the implementer's session as its independent reviewer. A read-only reviewer can inspect an existing diff/report supplied as a file without shell access.
- For corrections, resume that task's implementer with `--resume-from` and the concrete findings. Start fresh for unrelated tasks. If the workflow requires a fresh worker for escalation, do so. Record run paths and Claude session IDs in the existing task ledger so compaction does not duplicate completed work.

After dispatch, use the skill's [completion waiting](monitoring.md) procedure. Do independent work or wait on the retained process handle; for several workers, wait for any result together and then continue with only the returned pending directories. Frequent status polls and transcript reads are not review. Preserve the independent review stages when the worker completes.

Fill role-template placeholders through the brief: task/spec locations, owned files, report path, test commands, and commit authorization when the applicable workflow and user scope permit it. Superpowers may require structured report files; let workers write those when authorized and return only a compact summary to Codex. Resolve conflicting worker instructions in the brief before dispatch.

## Explicit model selection

Apply Superpowers' model-selection intent through [saved Claude routing](model-selection.md) on every dispatch. The template's required model becomes an actual launcher flag, normally `--task-type`; a model name only in the prompt does not select it. Read `settings.py show`, pass `--role` and `--selection-reason`, and announce the resolved model.

Use `mechanical` for fully specified mechanical implementation, `implementation` for prose-based implementation, `task_review` for spec/code-quality reviewers, and `final_review` for the whole-change review. Use `architecture` for architecture and difficult reasoning, or the appropriate debugging, investigation, testing, or documentation task type. Initial tier defaults are Sonnet / Opus / Fable, but saved task overrides and tier models take precedence over these defaults. Do not hard-code an Opus floor or Fable final reviewer after the user changes settings.

Preserve Superpowers fix-loop escalation: when it calls for a fresh, more capable implementer, start a fresh session with the findings and deliberately select a suitable saved tier using `--profile`. Explain the change from task routing and check that the selected model actually differs where a stronger model is required. A higher tier name alone may map to the same model; do not claim an escalation beyond the configured ceiling.

Example flow: `--task-type mechanical --role implementer`, a fresh `--task-type task_review --role task-reviewer`, and a fresh `--task-type final_review --role final-reviewer`. This changes model routing, not the number of workflow stages. Documentation produced under Archivist instructions should explicitly use `--task-type documentation` with an appropriate documentation role.

## Boundaries

Use one implementer at a time per overlapping checkout. Preserve the workflow's independent review and final review stages. Never pass GPT model identifiers to Claude. An authentication or quota failure is a blocker, not permission to silently spend GPT usage on the delegated implementation.

Claude's own enabled plugins remain available through Skill and ToolSearch; a Claude Superpowers installation is not required when Codex supplies the needed instructions. The launcher checks matching skills locally, without putting a plugin inventory into GPT context. Workers do not inherit Codex's chat, browser sessions, or native app tools. Keep orchestration and nested dispatch in Codex and give each worker its assigned role. Matching plugin names do not prove matching versions or capabilities.

If a worker cannot perform a browser, computer-use, or other capability-dependent step, it returns `native_required`. Follow [native handoff](native-handoff.md): Codex performs that authorized step with its own appropriate tools and returns evidence to the same worker. A handoff to Codex does not replace an independent review stage or justify bypassing a permission denial.

The on/off flag selects the worker backend; it grants no additional permissions. With delegation off, normal Superpowers behavior continues.
