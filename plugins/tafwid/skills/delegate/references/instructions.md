# Instruction delivery

Codex selects only the instructions needed by this worker, as it would when briefing a native worker. The launcher does not infer all skills used in the parent conversation or copy the parent's context. No particular workflow or plugin is required.

Use the existing repeatable `--instructions-file` flag for local role templates or skill entrypoints. Keep the brief focused on the assignment, acceptance criteria, constraints, and file locations. Do not paste the same instruction bodies into it or separately request a second installed copy.

```bash
# Add these to the normal delegate.py invocation, only when this task needs them:
--instructions-file /absolute/path/to/implementer.md \
--instructions-file /absolute/path/to/checking/SKILL.md
```

Select worker-relevant skills, not every skill available to Codex. Controller-only orchestration instructions stay with Codex. For a skill provided through a non-filesystem tool, materialize only the needed instructions and resources into a local file before forwarding; remote tool access is not transferred by copying instructions. Use the normal native handoff for required tools Claude cannot access.

## Resolution and context cost

- Ordinary files are supplied verbatim once. Duplicate paths and equivalent self-contained packages are deduplicated locally. Simple instructions already present verbatim in the brief are not appended again.
- For a selected `SKILL.md`, the launcher checks enabled Claude plugins and user/project skill locations. It uses a short `Use Skill name` reference only for an unambiguous, byte-matching package, including its local resources. Names or version labels alone are insufficient. Model-disabled skills, execution-changing metadata (such as `context: fork`), and detected invocation overrides prevent this optimization.
- If absent, disabled, different, ambiguous, or unverifiable, the selected source is supplied inline with its original path, so the worker can resolve referenced resources. The contract tells the worker to use that copy rather than load another installation.
- A confirmed successful prior invocation at the current registered session tail allows unchanged, verifiable instructions to be retained on resume without another body or reminder. Changed instructions are supplied again and marked as replacements. Missing/stale manifests, failed invocations, or dependencies whose equivalence cannot be established cause conservative redelivery when the file is explicitly selected again. Skills with external references, dynamic resource roots, or symlinked resources are not assumed equivalent.
- No selected skills means no plugin inventory call. Discovery, fingerprints, and the manifest require no model call. `instructions.json` is saved in the run directory and registry, not added to the worker prompt or printed in the compact launcher result. Do not routinely read this manifest into GPT context; inspect it only to diagnose forwarding.

This reduces adapter-supplied duplication, not the cost of necessary instructions. A native Skill invocation still loads that skill's content. Claude's independent startup hooks or redundant loads chosen by a worker can still add context. An instruction manifest records selection and delivery, not proof that a skill was invoked or obeyed; use the exact session's tool trace when auditing that distinction.

The comparison is deliberately conservative: bounded local package hashing, with no claim that external resources, different runtime tools, or plugin hooks are equivalent. The original paths remain authoritative when content is supplied. A resume carries its previous instruction manifest forward; use a fresh session when a different assignment requires discarding earlier instructions.
