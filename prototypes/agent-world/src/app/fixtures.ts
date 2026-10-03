import type { Agent, AgentStatus, Snapshot } from "./types";

/** A source of agent snapshots. Live data (TAF-3) would implement the same interface. */
export interface SnapshotSource {
  current(): Snapshot;
  subscribe(fn: (s: Snapshot) => void): () => void;
  /** Steps the scripted sample day; live sources may ignore it. */
  advance(): void;
}

export type ScenarioId = "productive-day" | "quiet-morning";

// Every name, task and timing below is fictional sample data.
const TEAM: Agent[] = [
  {
    id: "milo", name: "Milo", role: "Coordinator", provider: "GPT · Codex CLI", status: "working",
    task: "Planning the next release", elapsedMinutes: 12, next: "Hand the implementation brief to Ada.",
    look: { skin: "#f2c9a0", shirt: "#8f7ee0", hair: "#3b2a20", accent: "#ffd166" },
  },
  {
    id: "ada", name: "Ada", role: "Builder", provider: "Claude Code", status: "working",
    task: "Building the account settings flow", elapsedMinutes: 18, next: "Open the change for review.",
    look: { skin: "#c98d63", shirt: "#3fb68e", hair: "#1f1b2d", accent: "#f4f1de" },
  },
  {
    id: "cleo", name: "Cleo", role: "Reviewer", provider: "GPT · Codex CLI", status: "review",
    task: "Onboarding changes are ready for your review", elapsedMinutes: 7, next: "Wait for your decision.",
    look: { skin: "#f7d7b5", shirt: "#f29e4c", hair: "#7a4b2a", accent: "#ffffff" },
  },
  {
    id: "noor", name: "Noor", role: "Researcher", provider: "Claude Code", status: "ready",
    task: "Ready for the next question", elapsedMinutes: null, next: "Pick up the next research task.",
    look: { skin: "#8d5a3b", shirt: "#4263eb", hair: "#1f1b2d", accent: "#ffcf56" },
  },
  {
    id: "rex", name: "Rex", role: "Builder", provider: "GPT · Codex CLI", status: "issue",
    task: "Tests are failing and need a decision", elapsedMinutes: 25, next: "Choose whether to revert or fix forward.",
    look: { skin: "#f2c9a0", shirt: "#e4573d", hair: "#d9a35b", accent: "#2b2d42" },
  },
];

const SCENARIOS: Record<ScenarioId, () => Snapshot> = {
  "productive-day": () => ({ scenarioId: "productive-day", agents: structuredClone(TEAM), completedThisSession: 7 }),
  "quiet-morning": () => ({
    scenarioId: "quiet-morning",
    agents: TEAM.map((a) => ({ ...structuredClone(a), status: "ready" as const, elapsedMinutes: null, task: "Ready for the next task" })),
    completedThisSession: 0,
  }),
};

// The scripted sample day: each step changes one agent's status.
const SCRIPT: { id: string; status: AgentStatus; task: string; elapsedMinutes: number | null }[] = [
  { id: "rex", status: "working", task: "Fixing the failing tests", elapsedMinutes: 1 },
  { id: "ada", status: "review", task: "Account settings are ready for your review", elapsedMinutes: 0 },
  { id: "noor", status: "working", task: "Researching payment providers", elapsedMinutes: 0 },
  { id: "cleo", status: "ready", task: "Ready for the next review", elapsedMinutes: null },
];

export function createFixtureSource(scenario: ScenarioId): SnapshotSource {
  let snapshot = SCENARIOS[scenario]();
  let step = 0;
  const listeners = new Set<(s: Snapshot) => void>();
  return {
    current: () => snapshot,
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    advance() {
      if (step >= SCRIPT.length) {
        snapshot = SCENARIOS[scenario]();
        step = 0;
      } else {
        const change = SCRIPT[step++];
        snapshot = {
          ...snapshot,
          agents: snapshot.agents.map((a) => (a.id === change.id ? { ...a, ...change } : a)),
          completedThisSession: snapshot.completedThisSession + (change.status === "review" ? 1 : 0),
        };
      }
      listeners.forEach((fn) => fn(snapshot));
    },
  };
}
