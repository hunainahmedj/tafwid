import type { Action, Role } from "../live/types";
import type { Agent, AgentStatus, Snapshot } from "./types";

/** A source of agent snapshots: the scripted sample day here, the live stream in `live/live-source.ts`. */
export interface SnapshotSource {
  current(): Snapshot;
  subscribe(fn: (s: Snapshot) => void): () => void;
  /** Steps the scripted sample day; live sources may ignore it. */
  advance(): void;
}

export type ScenarioId = "productive-day" | "quiet-morning" | "crowd";

export interface FixtureOptions {
  /** Crowd only: how many agents are in the room (finished agents come on top). */
  count?: number;
}

// Start times are fixed offsets from an arbitrary zero so seating is repeatable.
const MINUTE = 60_000;

// Two sample teams, like two live sessions: Milo coordinates Ada and Cleo in
// one project, Noor coordinates Rex in another. Every name, project and task
// below is fictional sample data.
const SAMPLE_TEAMS: { id: string; project: string; host: "claude" | "codex"; accent: string }[] = [
  { id: "sample-harbour", project: "harbour-app", host: "claude", accent: "#e4572e" },
  { id: "sample-orchard", project: "orchard-api", host: "codex", accent: "#17bebb" },
];

const TEAM: Agent[] = [
  {
    id: "milo", startedAt: 0, name: "Milo", role: "coordinator", provider: "Claude Code", status: "working", teamId: "sample-harbour",
    project: "harbour-app", host: "claude", kind: "coordinator", action: "thinking",
    task: "Planning the next release", elapsedMinutes: 12, next: "Hand the implementation brief to Ada.",
    look: { skin: "#f2c9a0", shirt: "#8f7ee0", hair: "#3b2a20", accent: "#e4572e" },
  },
  {
    id: "ada", startedAt: 4 * MINUTE, name: "Ada", role: "implementer", provider: "Claude Code", status: "working", teamId: "sample-harbour",
    project: "harbour-app", host: "claude", kind: "sample", action: "edit-code",
    task: "Building the account settings flow", elapsedMinutes: 18, next: "Open the change for review.",
    look: { skin: "#c98d63", shirt: "#3fb68e", hair: "#1f1b2d", accent: "#e4572e" },
  },
  {
    id: "cleo", startedAt: 6 * MINUTE, name: "Cleo", role: "reviewer", provider: "Claude Code", status: "review", teamId: "sample-harbour",
    project: "harbour-app", host: "claude", kind: "sample", action: "read",
    task: "Onboarding changes are ready for your review", elapsedMinutes: 7, next: "Wait for your decision.",
    look: { skin: "#f7d7b5", shirt: "#f29e4c", hair: "#7a4b2a", accent: "#e4572e" },
  },
  {
    id: "noor", startedAt: 2 * MINUTE, name: "Noor", role: "coordinator", provider: "Codex", status: "ready", teamId: "sample-orchard",
    project: "orchard-api", host: "codex", kind: "coordinator", action: "thinking",
    task: "Ready for the next question", elapsedMinutes: null, next: "Pick up the next research task.",
    look: { skin: "#8d5a3b", shirt: "#4263eb", hair: "#1f1b2d", accent: "#17bebb" },
  },
  {
    id: "rex", startedAt: 5 * MINUTE, name: "Rex", role: "implementer", provider: "Codex", status: "issue", teamId: "sample-orchard",
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

const SCENARIOS: Record<Exclude<ScenarioId, "crowd">, () => Snapshot> = {
  "productive-day": () => sampleSnapshot("productive-day", structuredClone(TEAM), 7),
  "quiet-morning": () =>
    sampleSnapshot(
      "quiet-morning",
      TEAM.map((a) => ({ ...structuredClone(a), status: "ready" as const, elapsedMinutes: null, task: "Ready for the next task", action: "thinking" as const })),
      0,
    ),
};

// The crowd: a generated stress scenario of four fictional teams for checking
// overflow and frame times. Every name, project and task is made up.
const CROWD_DEFAULT = 40;
const CROWD_TEAMS: { id: string; project: string; host: "claude" | "codex"; accent: string }[] = [
  { id: "crowd-lantern", project: "lantern-notes", host: "claude", accent: "#e4572e" },
  { id: "crowd-meadow", project: "meadow-sync", host: "codex", accent: "#17bebb" },
  { id: "crowd-pebble", project: "pebble-cli", host: "claude", accent: "#f2b134" },
  { id: "crowd-tidepool", project: "tidepool-web", host: "codex", accent: "#7b5ea7" },
];
const CROWD_NAMES = [
  "Aria", "Bram", "Cora", "Dex", "Elio", "Fern", "Gus", "Hana", "Ivo", "Juno", "Kai", "Lark", "Mira", "Nico", "Opal",
  "Pax", "Quin", "Rhea", "Sol", "Tove", "Uma", "Vik", "Wren", "Xan", "Yara", "Zeb", "Alba", "Bo", "Cyd", "Dara",
  "Emi", "Fitz", "Gia", "Hal", "Isla", "Jory", "Kit", "Lumi", "Moss", "Nell", "Odo", "Pia", "Rafe", "Sage", "Tam",
  "Ulla", "Vera", "Wim", "Yuki", "Zia", "Arlo", "Bea", "Cass", "Dune", "Edda", "Finn", "Gwen", "Hugo", "Ines", "Jax",
];
const CROWD_ROLES: Role[] = ["implementer", "reviewer", "documenter", "researcher", "tester"];
const CROWD_ACTIONS: Action[] = ["edit-code", "edit-docs", "read", "search", "run-tests", "run-command", "web", "spawn", "thinking", "other"];
// Nine-step status cycle for team members: mostly working, one of each other
// state. Nine is coprime with the five roles, so every state meets several roles.
const CROWD_STATUSES: AgentStatus[] = ["working", "working", "review", "working", "ready", "working", "issue", "working", "uncertain"];
const CROWD_WORK: Record<Role, string> = {
  coordinator: "Coordinating",
  implementer: "Building",
  reviewer: "Reviewing",
  documenter: "Writing up",
  researcher: "Researching",
  tester: "Testing",
};
const CROWD_FEATURES = ["the tide charts", "the lantern menu", "the pebble importer", "the sync queue", "night mode", "the offline cache", "the sign-up form", "the export panel"];
const CROWD_SHIRTS: Record<Role, string> = {
  coordinator: "#8f7ee0",
  implementer: "#3fb68e",
  reviewer: "#f29e4c",
  documenter: "#d86f9a",
  researcher: "#4263eb",
  tester: "#e4573d",
};
const CROWD_SKINS = ["#f2c9a0", "#c98d63", "#f7d7b5", "#8d5a3b", "#e8b48a", "#a8704b"];
const CROWD_HAIR = ["#3b2a20", "#1f1b2d", "#7a4b2a", "#d9a35b", "#5b3a29", "#9a9a9a"];
const CROWD_COORDINATOR_STATUS: AgentStatus[] = ["working", "ready", "working", "uncertain"];

/** `count` agents in the room, plus about one in ten who have finished. */
function crowdSnapshot(count: number): Snapshot {
  const inRoom = Math.max(CROWD_TEAMS.length, Math.floor(count));
  const finished = Math.max(1, Math.round(inRoom / 10));
  const agents: Agent[] = [];
  let actionIndex = 0;
  const person = (i: number, role: Role, team: (typeof CROWD_TEAMS)[number], status: AgentStatus, kind: Agent["kind"], startedAt: number): Agent => {
    const base = CROWD_NAMES[i % CROWD_NAMES.length];
    const name = i < CROWD_NAMES.length ? base : `${base} ${Math.floor(i / CROWD_NAMES.length) + 1}`;
    const action = kind === "coordinator" ? (status === "working" ? "spawn" : "thinking") : status === "working" ? CROWD_ACTIONS[actionIndex++ % CROWD_ACTIONS.length] : "thinking";
    return {
      id: `crowd-${i}`, name, role, provider: team.host === "claude" ? "Claude Code" : "Codex", teamId: team.id,
      project: team.project, host: team.host, kind, action, startedAt, status,
      task: `${CROWD_WORK[role]} ${CROWD_FEATURES[i % CROWD_FEATURES.length]}`,
      elapsedMinutes: status === "ready" ? null : (i * 7) % 50, next: "",
      look: { skin: CROWD_SKINS[i % CROWD_SKINS.length], shirt: CROWD_SHIRTS[role], hair: CROWD_HAIR[(i * 5) % CROWD_HAIR.length], accent: team.accent },
    };
  };
  CROWD_TEAMS.forEach((team, t) => agents.push(person(t, "coordinator", team, CROWD_COORDINATOR_STATUS[t], "coordinator", t * MINUTE)));
  const members = inRoom - CROWD_TEAMS.length + finished;
  for (let j = 0; j < members; j++) {
    const status = j >= members - finished ? "done" : CROWD_STATUSES[j % CROWD_STATUSES.length];
    const i = CROWD_TEAMS.length + j;
    agents.push(person(i, CROWD_ROLES[j % CROWD_ROLES.length], CROWD_TEAMS[j % CROWD_TEAMS.length], status, "sample", 10 * MINUTE + j * 45_000));
  }
  return {
    scenarioId: "crowd",
    agents,
    completedThisSession: finished,
    overflow: {},
    teams: CROWD_TEAMS.map((t) => ({ ...t, count: agents.filter((a) => a.teamId === t.id).length })),
  };
}

// The scripted sample day: each step changes one agent's status.
const SCRIPT: { id: string; status: AgentStatus; task: string; elapsedMinutes: number | null; action: Action }[] = [
  { id: "rex", status: "working", task: "Fixing the failing tests", elapsedMinutes: 1, action: "edit-code" },
  { id: "ada", status: "review", task: "Account settings are ready for your review", elapsedMinutes: 0, action: "read" },
  { id: "noor", status: "working", task: "Researching payment providers", elapsedMinutes: 0, action: "web" },
  { id: "cleo", status: "ready", task: "Ready for the next review", elapsedMinutes: null, action: "thinking" },
  { id: "ada", status: "done", task: "Account settings are merged", elapsedMinutes: 0, action: "thinking" },
];

export function createFixtureSource(scenario: ScenarioId, options: FixtureOptions = {}): SnapshotSource {
  const fresh = scenario === "crowd" ? () => crowdSnapshot(options.count ?? CROWD_DEFAULT) : SCENARIOS[scenario];
  let snapshot = fresh();
  let step = 0;
  const listeners = new Set<(s: Snapshot) => void>();
  return {
    current: () => snapshot,
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    advance() {
      if (scenario === "crowd") {
        // Each step finishes the next working sub-agent; when none is left the crowd starts over.
        const next = snapshot.agents.find((a) => a.status === "working" && a.kind !== "coordinator");
        snapshot = next
          ? {
              ...snapshot,
              agents: snapshot.agents.map((a) => (a === next ? { ...a, status: "done" as const, action: "thinking" as const } : a)),
              completedThisSession: snapshot.completedThisSession + 1,
            }
          : fresh();
      } else if (step >= SCRIPT.length) {
        snapshot = fresh();
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
