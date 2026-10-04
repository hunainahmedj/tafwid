import type { SnapshotSource } from "../app/fixtures";
import { hostLabel, type Agent, type AgentStatus, type Snapshot } from "../app/types";
import type { LiveAgent, LiveState, LiveStatus, Role } from "./types";

/** What the bridge sends: the folded state, and whether the world switch is on. */
export interface LiveMessage {
  enabled: boolean;
  state: LiveState;
}

export interface LiveSource extends SnapshotSource {
  /** Whether the last snapshot said live activity is switched on. */
  enabled(): boolean;
  /** False from a stream error until the next message; agents then read as uncertain. */
  connected(): boolean;
  /** Closes the stream, cancels any pending reconnect and silences subscribers. */
  stop(): void;
}

/** The part of `EventSource` the source uses, so a test can pass a fake. */
export interface EventSourceLike {
  onmessage: ((event: MessageEvent) => void) | null;
  onerror: ((event: Event) => void) | null;
  close(): void;
}

export interface LiveSourceOptions {
  eventSource?: new (url: string) => EventSourceLike;
  /** Seconds since the epoch, like the timestamps in the state. */
  now?: () => number;
  /** A snapshot to show before the first stream message arrives. */
  initial?: LiveMessage;
  /** How often elapsed times are refreshed between messages. */
  refreshMs?: number;
}

const STATUS: Record<LiveStatus, AgentStatus> = {
  working: "working",
  attention: "issue",
  ready: "ready",
  done: "done",
  uncertain: "uncertain",
};

// Deterministic character colours per role; the team accent goes on `accent`.
const LOOKS: Record<Role, { skin: string; shirt: string; hair: string }> = {
  coordinator: { skin: "#f2c9a0", shirt: "#8f7ee0", hair: "#3b2a20" },
  implementer: { skin: "#c98d63", shirt: "#3fb68e", hair: "#1f1b2d" },
  reviewer: { skin: "#f7d7b5", shirt: "#f29e4c", hair: "#7a4b2a" },
  documenter: { skin: "#e8b48a", shirt: "#d86f9a", hair: "#5b3a29" },
  researcher: { skin: "#8d5a3b", shirt: "#4263eb", hair: "#1f1b2d" },
  tester: { skin: "#f2c9a0", shirt: "#e4573d", hair: "#d9a35b" },
};

const RECONNECT_FIRST_MS = 1000;
const RECONNECT_MAX_MS = 30_000;

const FALLBACK_ACCENT = "#7a869a";
// Only plain hex colours reach a style, so a bad value cannot inject CSS.
const safeAccent = (accent: string) => (/^#[0-9a-f]{6}$/i.test(accent) ? accent : FALLBACK_ACCENT);

const RANK: Record<LiveStatus, number> = { attention: 0, working: 1, ready: 2, done: 2, uncertain: 2 };

const minutes = (from: number, to: number) => Math.max(0, Math.floor((to - from) / 60));

function toAgent(a: LiveAgent, accent: string, now: number): Agent {
  return {
    id: a.id,
    name: a.name,
    role: a.role,
    provider: hostLabel(a.host),
    status: STATUS[a.status],
    task: a.label || "Working",
    // A ready agent has no active task; a finished one stops its clock when it ends.
    elapsedMinutes: a.status === "ready" ? null : minutes(a.startedAt, a.finishedAt ?? now),
    next: "",
    look: { ...LOOKS[a.role], accent },
    teamId: a.teamId,
    project: a.project,
    action: a.action,
    host: a.host,
    kind: a.kind,
    startedAt: a.startedAt * 1000,
  };
}

const byText = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);

/**
 * Turns the folded state into the app's snapshot. At most `cap` agents are
 * kept: attention first, then working, then the newest `startedAt`. The
 * agents left out are counted per project in `overflow`. Pure: no clock, no
 * input mutation. `now` is in seconds, like the state's timestamps.
 */
export function toSnapshot(state: LiveState, now: number, cap = 32): Snapshot {
  const all = Object.values(state.agents);
  const kept = new Set(
    [...all]
      .sort((a, b) => RANK[a.status] - RANK[b.status] || b.startedAt - a.startedAt || byText(a.id, b.id))
      .slice(0, Math.max(0, cap))
      .map((a) => a.id),
  );

  const overflow: Record<string, number> = {};
  for (const a of all) if (!kept.has(a.id)) overflow[a.project] = (overflow[a.project] ?? 0) + 1;

  const teams = Object.values(state.teams)
    .filter((t) => all.some((a) => a.teamId === t.id))
    .sort((a, b) => byText(a.project, b.project) || byText(a.id, b.id));
  const accentOf = new Map(teams.map((t) => [t.id, safeAccent(t.accent)]));

  // Roster order: by team, the coordinator first, then oldest first.
  const order = new Map(teams.map((t, i) => [t.id, i]));
  const agents = all
    .filter((a) => kept.has(a.id) && order.has(a.teamId))
    .sort(
      (a, b) =>
        order.get(a.teamId)! - order.get(b.teamId)! ||
        Number(b.kind === "coordinator") - Number(a.kind === "coordinator") ||
        a.startedAt - b.startedAt ||
        byText(a.id, b.id),
    )
    .map((a) => toAgent(a, accentOf.get(a.teamId)!, now));

  return {
    scenarioId: "live",
    agents,
    completedThisSession: all.filter((a) => a.status === "done").length,
    overflow,
    teams: teams.map((t) => ({
      id: t.id,
      project: t.project,
      host: t.host,
      accent: accentOf.get(t.id)!,
      count: agents.filter((a) => a.teamId === t.id).length,
    })),
  };
}

/** Reads a bridge message (a snapshot response or a stream event); null when it is not one. */
export function parseLiveMessage(data: unknown): LiveMessage | null {
  if (typeof data !== "string") return null;
  try {
    const m = JSON.parse(data) as Partial<LiveMessage> | null;
    const s = m?.state;
    if (typeof m?.enabled !== "boolean" || !s || typeof s.teams !== "object" || typeof s.agents !== "object" || !s.teams || !s.agents) return null;
    return m as LiveMessage;
  } catch {
    return null;
  }
}

const sameElapsed = (a: Snapshot, b: Snapshot) =>
  a.agents.length === b.agents.length && a.agents.every((x, i) => x.elapsedMinutes === b.agents[i].elapsedMinutes);

/**
 * The live snapshot source: follows the bridge's event stream. When the
 * stream errors it closes it and reconnects with a capped backoff (1 s,
 * doubling, at most 30 s; reset by the next message). The client cannot age
 * agents itself, so while disconnected every agent reads "uncertain" rather
 * than a stale "working". The next message after a reconnect replaces the state.
 */
export function createLiveSource(url = "/api/world/stream", options: LiveSourceOptions = {}): LiveSource {
  const Stream = options.eventSource ?? (EventSource as unknown as new (url: string) => EventSourceLike);
  const now = options.now ?? (() => Date.now() / 1000);
  const listeners = new Set<(s: Snapshot) => void>();
  const doneSeen = new Set<string>();
  let message: LiveMessage = options.initial ?? { enabled: false, state: { teams: {}, agents: {}, pendingSpawns: [], ended: {}, finishedRuns: {} } };
  let stopped = false;
  let connected = true;
  let delay = RECONNECT_FIRST_MS;
  let retry: ReturnType<typeof setTimeout> | undefined;
  let stream: EventSourceLike;

  const build = () => {
    for (const a of Object.values(message.state.agents)) if (a.status === "done") doneSeen.add(a.id);
    const base = toSnapshot(message.state, now());
    return {
      ...base,
      agents: connected ? base.agents : base.agents.map((a) => ({ ...a, status: "uncertain" as const })),
      completedThisSession: doneSeen.size,
    };
  };
  let snapshot = build();
  const notify = () => listeners.forEach((fn) => fn(snapshot));

  function open() {
    retry = undefined;
    const current = new Stream(url);
    stream = current;
    current.onmessage = (event) => {
      const next = stopped || stream !== current ? null : parseLiveMessage(event.data);
      if (!next) return;
      message = next;
      connected = true;
      delay = RECONNECT_FIRST_MS;
      snapshot = build();
      notify();
    };
    current.onerror = () => {
      if (stopped || stream !== current) return;
      // Close it ourselves: a CLOSED stream never retries, and the browser's own retries have no backoff cap.
      current.close();
      if (connected) {
        connected = false;
        snapshot = build();
        notify();
      }
      retry = setTimeout(open, delay);
      delay = Math.min(delay * 2, RECONNECT_MAX_MS);
    };
  }
  open();

  // Elapsed times would otherwise freeze while the log is quiet.
  const timer = setInterval(() => {
    if (!connected) return;
    const next = build();
    if (sameElapsed(snapshot, next)) return;
    snapshot = next;
    notify();
  }, options.refreshMs ?? 30_000);
  (timer as { unref?: () => void }).unref?.();

  return {
    current: () => snapshot,
    enabled: () => message.enabled,
    connected: () => connected,
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    advance() {},
    stop() {
      stopped = true;
      clearInterval(timer);
      clearTimeout(retry);
      stream.close();
      listeners.clear();
    },
  };
}
