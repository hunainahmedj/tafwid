import type { Action as LiveAction, AgentHost, Role } from "../live/types";

export type AgentStatus = "working" | "review" | "ready" | "issue" | "done" | "uncertain";
export type Tier = "low" | "medium" | "high";
export type Mode = "explore" | "dashboard";
export type Variant = "kit" | "baked";
export type Filter = "all" | "working" | "attention";
export type SourceId = "live" | "sample";

export interface Agent {
  id: string;
  name: string;
  /** What the agent does in the team; `ROLE_LABELS` gives the display text. */
  role: Role;
  /** Display name of the tool the agent runs in (the host's label). */
  provider: string;
  teamId: string;
  project: string;
  /** What the agent is doing right now; shown while it is working. */
  action: LiveAction;
  host: AgentHost;
  kind: "coordinator" | "subagent" | "delegated" | "sample";
  /** When the agent started, in milliseconds since the epoch; orders seating. */
  startedAt: number;
  status: AgentStatus;
  task: string;
  elapsedMinutes: number | null;
  next: string;
  look: { skin: string; shirt: string; hair: string; accent: string };
}

export interface SnapshotTeam {
  id: string;
  project: string;
  /** "claude", "codex" or "unknown"; `HOST_LABELS` gives the display text. */
  host: string;
  accent: string;
  /** Agents of this team in `Snapshot.agents` (the ones that fit under the cap). */
  count: number;
}

export interface Snapshot {
  scenarioId: string;
  agents: Agent[];
  completedThisSession: number;
  teams: SnapshotTeam[];
  /** Project to the number of agents hidden by the cap. */
  overflow: Record<string, number>;
}

export interface AppState {
  snapshot: Snapshot;
  selectedId: string | null;
  mode: Mode;
  environmentId: string;
  variant: Variant;
  filter: Filter;
  quality: Tier;
  qualityAuto: boolean;
  worldAvailable: boolean;
  worldError: string | null;
  source: SourceId;
  /** Whether the bridge reports live activity switched on. */
  liveEnabled: boolean;
  /** False when the bridge could not be reached or the live stream dropped. */
  liveReachable: boolean;
  /** A project name (possibly empty) narrows the roster to it; null shows every project. */
  projectFilter: string | null;
}

export type Action =
  | { type: "select"; id: string | null }
  | { type: "setMode"; mode: Mode }
  | { type: "setVariant"; variant: Variant }
  | { type: "setFilter"; filter: Filter }
  | { type: "snapshot"; snapshot: Snapshot }
  | { type: "setQuality"; tier: Tier; auto: boolean }
  | { type: "worldUnavailable"; reason: string }
  | { type: "worldError"; message: string | null }
  /** Switches source; pass the new source's snapshot to swap it in the same step. */
  | { type: "setSource"; source: SourceId; snapshot?: Snapshot }
  | { type: "setLiveEnabled"; enabled: boolean }
  | { type: "setLiveReachable"; reachable: boolean }
  | { type: "setProjectFilter"; project: string | null };

export const STATUS_LABELS: Record<AgentStatus, string> = {
  working: "Working",
  review: "Awaiting review",
  ready: "Ready",
  issue: "Needs attention",
  done: "Done",
  uncertain: "No recent activity",
};

export const ROLE_LABELS: Record<Role, string> = {
  coordinator: "Coordinator",
  implementer: "Builder",
  reviewer: "Reviewer",
  documenter: "Documenter",
  researcher: "Researcher",
  tester: "Tester",
};

export const ACTION_LABELS: Record<LiveAction, string> = {
  "edit-code": "Editing code",
  "edit-docs": "Editing docs",
  read: "Reading",
  search: "Searching",
  "run-tests": "Running tests",
  "run-command": "Running a command",
  web: "Browsing the web",
  spawn: "Starting a helper",
  other: "Working",
  thinking: "Thinking",
};

export const HOST_LABELS: Record<string, string> = {
  claude: "Claude Code",
  codex: "Codex",
  unknown: "Unknown host",
};

export const hostLabel = (host: string) => HOST_LABELS[host] ?? HOST_LABELS.unknown;

/** What the roster and the details card say the agent is doing. */
export function actionText(a: Pick<Agent, "status" | "action">): string {
  if (a.status === "working") return ACTION_LABELS[a.action];
  if (a.status === "uncertain") return "No recent activity";
  return "None right now";
}
