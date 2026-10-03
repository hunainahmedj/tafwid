export type AgentStatus = "working" | "review" | "ready" | "issue";
export type Tier = "low" | "medium" | "high";
export type Mode = "explore" | "dashboard";
export type Variant = "kit" | "baked";
export type Filter = "all" | "working" | "attention";

export interface Agent {
  id: string;
  name: string;
  role: string;
  provider: string;
  status: AgentStatus;
  task: string;
  elapsedMinutes: number | null;
  next: string;
  look: { skin: string; shirt: string; hair: string; accent: string };
}

export interface Snapshot {
  scenarioId: string;
  agents: Agent[];
  completedThisSession: number;
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
}

export type Action =
  | { type: "select"; id: string | null }
  | { type: "setMode"; mode: Mode }
  | { type: "setVariant"; variant: Variant }
  | { type: "setFilter"; filter: Filter }
  | { type: "snapshot"; snapshot: Snapshot }
  | { type: "setQuality"; tier: Tier; auto: boolean }
  | { type: "worldUnavailable"; reason: string }
  | { type: "worldError"; message: string | null };

export const STATUS_LABELS: Record<AgentStatus, string> = {
  working: "Working",
  review: "Awaiting review",
  ready: "Ready",
  issue: "Needs attention",
};
