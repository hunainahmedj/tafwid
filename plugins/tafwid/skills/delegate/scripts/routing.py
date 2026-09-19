"""Model routing shared by settings, the dashboard, and the worker launcher."""
MODELS = ("sonnet", "opus", "fable")
PROFILES = {"fast": "sonnet", "standard": "opus", "deep": "fable"}
PROFILE_EFFORTS = {"fast": None, "standard": "medium", "deep": "high"}
TASKS = {
    "mechanical": ("Mechanical work", "Exact-code edits, transcription, and bounded extraction.", "fast"),
    "investigation": ("Investigation", "Explore code, trace behavior, and report findings.", "standard"),
    "implementation": ("Implementation", "Build features and integrate changes from a specification.", "standard"),
    "debugging": ("Debugging", "Find causes, fix defects, and verify the result.", "standard"),
    "documentation": ("Documentation", "Write project docs, guides, and walkthroughs.", "standard"),
    "testing": ("Testing", "Create or run focused tests and evaluate results.", "standard"),
    "task_review": ("Task review", "Independent specification and code-quality reviews of a bounded task.", "standard"),
    "architecture": ("Architecture", "Design decisions, difficult reasoning, and high-risk changes.", "deep"),
    "final_review": ("Final review", "Independent review of the complete change.", "deep"),
}


def defaults():
    return {"profiles": dict(PROFILES), "tasks": dict.fromkeys(TASKS)}


def validate(models):
    if not isinstance(models, dict) or set(models) != {"profiles", "tasks"}:
        raise ValueError("Invalid model routing settings")
    profiles, tasks = models["profiles"], models["tasks"]
    if (not isinstance(profiles, dict) or set(profiles) != set(PROFILES)
            or any(value not in MODELS for value in profiles.values())):
        raise ValueError("Each tier must select Sonnet, Opus, or Fable")
    if (not isinstance(tasks, dict) or set(tasks) != set(TASKS)
            or any(value is not None and value not in MODELS for value in tasks.values())):
        raise ValueError("Each task type must select a model or its tier default")
    return models


def select(models, *, profile=None, task_type=None):
    validate(models)
    if task_type is not None:
        if task_type not in TASKS:
            raise ValueError("Unknown task type")
        profile = TASKS[task_type][2]
        override = models["tasks"][task_type]
        model = override or models["profiles"][profile]
        source = "task_override" if override else "task_default"
    else:
        model = models["profiles"][profile]
        source = "profile"
    return profile, model, PROFILE_EFFORTS[profile], source


def catalog():
    return {"models": list(MODELS),
            "profiles": [{"id": key, "label": key.title(), "effort": PROFILE_EFFORTS[key]} for key in PROFILES],
            "tasks": [{"id": key, "label": label, "description": description, "profile": profile}
                      for key, (label, description, profile) in TASKS.items()]}
