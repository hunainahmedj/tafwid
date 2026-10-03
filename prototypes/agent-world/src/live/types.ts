// Types for the live agent world: the sanitised event lines written by the
// plugin hook, the bridge's run events, and the folded live state.

export type Role =
  | "coordinator"
  | "implementer"
  | "reviewer"
  | "documenter"
  | "researcher"
  | "tester";

export type Action =
  | "edit-code"
  | "edit-docs"
  | "read"
  | "search"
  | "run-tests"
  | "run-command"
  | "web"
  | "spawn"
  | "other"
  | "thinking";

/** Status of an agent as shown in the world. */
export type LiveStatus = "working" | "attention" | "ready" | "done" | "uncertain";

export type EventHost = "claude" | "codex" | "unknown";
export type AgentHost = "claude" | "codex";

/** One sanitised line written by the plugin's activity hook. */
export interface HookEvent {
  v: 1;
  t: number;
  host: EventHost;
  session: string;
  project: string | null;
  agent: string | null;
  event:
    | "session"
    | "prompt"
    | "tool"
    | "permission"
    | "subagent-start"
    | "subagent-stop"
    | "stop"
    | "session-end"
    | "notification";
  phase: "pre" | "post" | null;
  agentType: string | null;
  label: string | null;
  action: Exclude<Action, "thinking"> | null;
  role: Role | null;
  status: "waiting" | "idle" | "done" | "error" | "interrupted" | null;
}

/** A delegated Tafwid run, produced by the bridge from run records. */
export interface RunEvent {
  v: 1;
  t: number;
  event: "run";
  /** Owner session hash; the run joins that session's team. */
  session: string;
  project: string | null;
  host: EventHost;
  /** 16-hex run hash. */
  run: string;
  label: string | null;
  role: Role | null;
  status: "working" | "done" | "attention";
}

export type WorldEvent = HookEvent | RunEvent;

export interface LiveAgent {
  id: string;
  teamId: string;
  kind: "coordinator" | "subagent" | "delegated";
  role: Role;
  name: string;
  label: string;
  action: Action;
  status: LiveStatus;
  host: AgentHost;
  project: string;
  startedAt: number;
  lastEventAt: number;
  statusSince: number;
  /** Set once a sub-agent or run has ended; drives removal in `tick`. */
  finishedAt?: number;
}

export interface LiveTeam {
  id: string;
  project: string;
  host: string;
  accent: string;
  lastEventAt: number;
}

/** A spawn the parent has announced and no sub-agent has claimed yet. */
export interface PendingSpawn {
  session: string;
  agentType: string | null;
  label: string | null;
  role: Role | null;
  t: number;
}

/** Plain JSON-serialisable state (no Maps) so the bridge can send it as-is. */
export interface LiveState {
  teams: Record<string, LiveTeam>;
  agents: Record<string, LiveAgent>;
  pendingSpawns: PendingSpawn[];
  /** Session id to end time, so trailing hook events cannot resurrect it. */
  ended: Record<string, number>;
}
