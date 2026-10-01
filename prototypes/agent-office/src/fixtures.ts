import type { Scenario } from "./model";
const active: Scenario = {
  id: "active",
  fresh: true,
  completedRuns: 7,
  agents: [
    {
      id: "milo",
      name: "Milo",
      role: "Coordinator",
      backend: "gpt",
      status: "working",
      task: "Planning the next release",
      elapsedSeconds: 732,
      nextStep: "Hand the implementation brief to Ada.",
      color: "#A496E8",
    },
    {
      id: "ada",
      name: "Ada",
      role: "Builder",
      backend: "claude",
      status: "working",
      task: "Building the account settings flow",
      elapsedSeconds: 1104,
      nextStep: "Finish the form validation, then run the checks.",
      color: "#52C8A0",
    },
    {
      id: "cleo",
      name: "Cleo",
      role: "Reviewer",
      backend: "claude",
      status: "review",
      task: "Reviewing the onboarding changes",
      elapsedSeconds: 428,
      nextStep:
        "The review report is ready for the coordinator to assess. Worker completion does not mean the result has been accepted.",
      color: "#FFB66E",
    },
    {
      id: "noor",
      name: "Noor",
      role: "Researcher",
      backend: "gpt",
      status: "ready",
      task: "Ready for the next question",
      elapsedSeconds: 0,
      nextStep: "Available for a new research brief.",
      color: "#7EA8EF",
    },
  ],
};
export const scenarios: Record<Scenario["id"], Scenario> = {
  active,
  empty: { id: "empty", fresh: true, completedRuns: 0, agents: [] },
  unavailable: {
    id: "unavailable",
    fresh: false,
    completedRuns: 4,
    agents: active.agents.map((a) =>
      a.id === "ada"
        ? {
            ...a,
            status: "attention",
            task: "Waiting for access to the project dependencies",
            nextStep:
              "Check the worker report before deciding whether to resume. This is a fictional example.",
          }
        : { ...a },
    ),
  },
};
