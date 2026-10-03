import type { Action } from "../live/types";
import type { Agent, AgentStatus, Snapshot } from "./types";

/** A source of agent snapshots: the scripted sample day here, the live stream in `live/live-source.ts`. */
export interface SnapshotSource {
  current(): Snapshot;
  subscribe(fn: (s: Snapshot) => void): () => void;
  /** Steps the scripted sample day; live sources may ignore it. */
  advance(): void;
}

export type ScenarioId = "productive-day" | "quiet-morning";

// Two sample teams, like two live sessions: Milo coordinates Ada and Cleo in
// one project, Noor coordinates Rex in another. Every name, project and task
// below is fictional sample data.
const SAMPLE_TEAMS: { id: string; project: string; host: "claude" | "codex"; accent: string }[] = [
  { id: "sample-harbour", project: "harbour-app", host: "claude", accent: "#e4572e" },
  { id: "sample-orchard", project: "orchard-api", host: "codex", accent: "#17bebb" },
];

const TEAM: Agent[] = [
  {
    id: "milo", name: "Milo", role: "coordinator", provider: "Claude Code", status: "working", teamId: "sample-harbour",
    project: "harbour-app", host: "claude", kind: "coordinator", action: "thinking",
    task: "Planning the next release", elapsedMinutes: 12, next: "Hand the implementation brief to Ada.",
    look: { skin: "#f2c9a0", shirt: "#8f7ee0", hair: "#3b2a20", accent: "#e4572e" },
  },
  {
    id: "ada", name: "Ada", role: "implementer", provider: "Claude Code", status: "working", teamId: "sample-harbour",
    project: "harbour-app", host: "claude", kind: "sample", action: "edit-code",
    task: "Building the account settings flow", elapsedMinutes: 18, next: "Open the change for review.",
    look: { skin: "#c98d63", shirt: "#3fb68e", hair: "#1f1b2d", accent: "#e4572e" },
  },
  {
    id: "cleo", name: "Cleo", role: "reviewer", provider: "Claude Code", status: "review", teamId: "sample-harbour",
    project: "harbour-app", host: "claude", kind: "sample", action: "read",
    task: "Onboarding changes are ready for your review", elapsedMinutes: 7, next: "Wait for your decision.",
    look: { skin: "#f7d7b5", shirt: "#f29e4c", hair: "#7a4b2a", accent: "#e4572e" },
  },
  {
    id: "noor", name: "Noor", role: "coordinator", provider: "Codex", status: "ready", teamId: "sample-orchard",
    project: "orchard-api", host: "codex", kind: "coordinator", action: "thinking",
    task: "Ready for the next question", elapsedMinutes: null, next: "Pick up the next research task.",
    look: { skin: "#8d5a3b", shirt: "#4263eb", hair: "#1f1b2d", accent: "#17bebb" },
  },
  {
    id: "rex", name: "Rex", role: "implementer", provider: "Codex", status: "issue", teamId: "sample-orchard",
    project: "orchard-api", host: "codex", kind: "sample", action: "run-tests",
    task: "Tests are failing and need a decision", elapsedMinutes: 25, next: "Choose whether to revert or fix forward.",
    look: { skin: "#f2c9a0", shirt: "#e4573d", hair: "#d9a35b", accent: "#17bebb" },
  },
];

function sampleSnapshot(scenarioId: ScenarioId, agents: Agent[], completedThisSession: number): Snapshot {
  return {
    scenarioId,
    agents,
    completedThisSession,
    overflow: {},
    teams: SAMPLE_TEAMS.map((t) => ({ ...t, count: agents.filter((a) => a.teamId === t.id).length })),
  };
}

const SCENARIOS: Record<ScenarioId, () => Snapshot> = {
  "productive-day": () => sampleSnapshot("productive-day", structuredClone(TEAM), 7),
  "quiet-morning": () =>
    sampleSnapshot(
      "quiet-morning",
      TEAM.map((a) => ({ ...structuredClone(a), status: "ready" as const, elapsedMinutes: null, task: "Ready for the next task", action: "thinking" as const })),
      0,
    ),
};

// The scripted sample day: each step changes one agent's status.
const SCRIPT: { id: string; status: AgentStatus; task: string; elapsedMinutes: number | null; action: Action }[] = [
  { id: "rex", status: "working", task: "Fixing the failing tests", elapsedMinutes: 1, action: "edit-code" },
  { id: "ada", status: "review", task: "Account settings are ready for your review", elapsedMinutes: 0, action: "read" },
  { id: "noor", status: "working", task: "Researching payment providers", elapsedMinutes: 0, action: "web" },
  { id: "cleo", status: "ready", task: "Ready for the next review", elapsedMinutes: null, action: "thinking" },
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
