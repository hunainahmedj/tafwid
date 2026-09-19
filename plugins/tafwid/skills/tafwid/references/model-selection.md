# Task-based Claude worker selection

Codex classifies the task and chooses its role before launching the worker. The launcher selects the model from user settings; Claude does not infer its own model or start a second orchestration loop. Use the current Superpowers role template when that workflow applies.

## Saved routing

Read `python3 /path/to/tafwid/scripts/settings.py show` before dispatch so the announced model matches the current settings. The dashboard's **Settings** page edits two layers:

1. Tier defaults: Fast starts as Sonnet, Standard as Opus, Deep as Fable. All three are editable.
2. Task overrides: each task can use its tier default or explicitly select Sonnet, Opus, or Fable. An override wins over a later tier-default change.

| `--task-type` | Use for | Default tier |
| --- | --- | --- |
| `mechanical` | Fully specified mechanical changes, exact-code transcription, bounded extraction | Fast |
| `investigation` | Code exploration, tracing behavior, finding evidence | Standard |
| `implementation` | Implementation from prose and integration | Standard |
| `debugging` | Diagnosing and fixing defects | Standard |
| `documentation` | Project docs, Archivist documentation, guides, walkthroughs | Standard |
| `testing` | Focused test authoring, execution, result analysis | Standard |
| `task_review` | Independent spec or code-quality review of a bounded task | Standard |
| `architecture` | Architecture, difficult reasoning, subtle high-risk changes | Deep |
| `final_review` | Independent whole-change review | Deep |

For example, Architecture can inherit Deep → Fable while Final review overrides it with Opus. Existing `--profile deep` calls also use the saved Deep model, but bypass task-specific overrides. Prefer `--task-type` for ordinary dispatches. Classify the actual assignment rather than using the free-form role label as an implicit routing rule. A `document author` role should use `--task-type documentation`; a reviewer uses task_review or final_review according to scope.

Effort remains tied to the task's tier: Fast omits the effort flag, Standard uses medium, Deep uses high. A task's model override retains that tier effort. `--effort` can explicitly override it where supported by Claude. No model availability probes or worker launches occur when saving settings.

File count alone is not a difficulty measure. Default tiers are recommendations, not fixed model floors that override the user's saved choices. If difficult work calls for escalation, explain why and deliberately select a different tier. Two tiers can select the same model, so moving to a higher-named tier is not proof of a more capable model. Keep independent review stages even when they use the same model.

Aliases resolve through Claude's installed configuration and account availability. Honor an explicitly requested model with `--model`. Do not silently replace an unavailable selection or fall back to API billing.

As checked on 2026-09-17, [Fable is included on Max plans](https://support.claude.com/en/articles/15424964-claude-fable-models-on-your-plan), drawing from the regular weekly allowance up to the Fable limit (50% of that allowance). Account usage-credit settings can affect billing after limits; non-interactive Claude does not prompt before charging available usage credits. The launcher does not change those settings or enforce a spending cap. Recheck plan coverage if the account changes.

## Dispatch and recovery

Example implementer:

```bash
python3 /path/to/tafwid/scripts/delegate.py \
  --once --cwd /path/to/workspace \
  --prompt-file /path/to/brief.md --output-dir /path/to/new-run \
  --task-type implementation --role implementer \
  --selection-reason 'Prose specification requiring implementation judgment' \
  --instructions-file /path/to/current/implementer-prompt.md
```

Add edit mode when shell or file changes are needed, and scoped shell allowances when using the Scoped permission policy. Omit `--once` when relying on an enabled task switch. Every selector is independent of permissions, plugin availability, and the on/off flag.

- `--task-type`, `--profile`, and `--model` are mutually exclusive. An exact model ID can pin a version; an alias tracks Claude's resolution.
- `--effort` overrides the profile effort. Only select effort values supported by the chosen model; no effort flag is sent by the fast profile. A model error is reported, not retried with another model automatically.
- `--role` and `--selection-reason` record the controller's decision. They do not invoke a Claude `--agent` definition. The brief and role template provide specialization. If changing the role on a resume, supply a new reason too; retained selection metadata otherwise keeps the earlier justification. Independent reviewers still require fresh sessions.
- Resume corrections or a native handoff with `--resume-from`; absent a new selector, the recorded model and effort persist even if the profile mapping has since changed. Pass a task type or profile explicitly to adopt its current mapping. A new profile uses its own defaults. A new explicit model drops the old profile and effort unless effort is supplied again.
- When Superpowers requires a fresh worker after a stuck fix loop, start a new session at a higher tier with the findings and current files. Do not merely resume the stuck session. If already at deep, report the tier ceiling and have the controller reconsider the task or provide an explicitly authorized stronger model.
- Independent task reviewers and final reviewers always start fresh. Use task_review or final_review and retain the matching role template; the user’s saved route selects the model.

Record task type, role, profile/model, effort, reason, session ID, and artifact path in the task ledger before moving on. `model_selection` records the requested configuration and route source (task_default, task_override, profile, explicit, or resume). `models_used` contains all modelUsage keys returned by Claude, including possible helpers; do not count those keys as subagents. For a live routing test, verify the primary assistant model in the exact session trace as well as the task result.

Claude documents aliases and selection precedence in [model configuration](https://code.claude.com/docs/en/model-config) and flags in the [CLI reference](https://code.claude.com/docs/en/cli-reference). Do not copy GPT model IDs or reasoning-effort names into a Claude command.
