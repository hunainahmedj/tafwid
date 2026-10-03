import { classifyRole } from "./roles";
import type {
  Action,
  AgentHost,
  HookEvent,
  LiveAgent,
  LiveState,
  LiveStatus,
  LiveTeam,
  PendingSpawn,
  RunEvent,
  WorldEvent,
} from "./types";

// Pure reducer from events to live state. Time only comes from event
// timestamps and the `now` passed to `tick`; nothing here reads a clock.

const THINKING_AFTER = 10;
const FINISHED_LINGER = 20;
const ATTENTION_LINGER = 120;
const UNCERTAIN_AFTER = 300;
const TEAM_SILENT_AFTER = 1800;
const SPAWN_EXPIRES_AFTER = 60;

const NAMES = [
  "Ada", "Bram", "Cleo", "Dara", "Eli", "Faye", "Gus", "Hana",
  "Ivo", "Juno", "Kai", "Lena", "Milo", "Nora", "Otto", "Pia",
  "Quin", "Rhea", "Sam", "Tess", "Uma", "Vic", "Wren", "Xavi",
  "Yara", "Zane", "Beau", "Cora", "Dex", "Esme", "Finn", "Gigi",
] as const;

const ACCENTS = [
  "#e4572e", "#17bebb", "#ffc914", "#76b041", "#7768ae",
  "#f78fb3", "#2e86ab", "#f28f3b", "#8d6a9f", "#3bb273",
] as const;

function hash(text: string): number {
  // FNV-1a, 32-bit.
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

export function nameFor(id: string): string {
  return NAMES[hash(id) % NAMES.length];
}

export function accentFor(teamId: string): string {
  return ACCENTS[hash(`accent:${teamId}`) % ACCENTS.length];
}

export function emptyLiveState(): LiveState {
  return { teams: {}, agents: {}, pendingSpawns: [], ended: {} };
}

function hostOf(host: HookEvent["host"]): AgentHost {
  return host === "codex" ? "codex" : "claude";
}

function copy(state: LiveState): LiveState {
  return {
    teams: { ...state.teams },
    agents: { ...state.agents },
    pendingSpawns: [...state.pendingSpawns],
    ended: { ...state.ended },
  };
}

function removeSession(state: LiveState, session: string): void {
  delete state.teams[session];
  for (const [id, agent] of Object.entries(state.agents)) {
    if (agent.teamId === session) delete state.agents[id];
  }
  state.pendingSpawns = state.pendingSpawns.filter((spawn) => spawn.session !== session);
}

function ensureTeam(
  state: LiveState,
  event: { session: string; project: string | null; host: HookEvent["host"]; t: number },
): LiveTeam {
  const existing = state.teams[event.session];
  const team: LiveTeam = existing
    ? {
        ...existing,
        project: existing.project || event.project || "",
        lastEventAt: Math.max(existing.lastEventAt, event.t),
      }
    : {
        id: event.session,
        project: event.project ?? "",
        host: event.host,
        accent: accentFor(event.session),
        lastEventAt: event.t,
      };
  state.teams[event.session] = team;
  return team;
}

/** Returns a copy of `agent` with the given status, tracking when it changed. */
function update(
  agent: LiveAgent,
  t: number,
  patch: { status?: LiveStatus; action?: Action } = {},
): LiveAgent {
  const status = patch.status ?? agent.status;
  return {
    ...agent,
    status,
    action: patch.action ?? agent.action,
    lastEventAt: Math.max(agent.lastEventAt, t),
    statusSince: status === agent.status ? agent.statusSince : t,
  };
}

function newCoordinator(event: HookEvent, project: string): LiveAgent {
  return {
    id: event.session,
    teamId: event.session,
    kind: "coordinator",
    role: "coordinator",
    name: nameFor(event.session),
    label: project || "session",
    action: "thinking",
    // A fresh session waits for its first message; any other event is activity.
    status: event.event === "session" ? "ready" : "working",
    host: hostOf(event.host),
    project,
    startedAt: event.t,
    lastEventAt: event.t,
    statusSince: event.t,
  };
}

/** Oldest unmatched spawn in the session: exact type first, then untyped. */
function takeSpawn(
  state: LiveState,
  session: string,
  agentType: string | null,
  now: number,
): PendingSpawn | null {
  // Expiry follows event time, so a replayed backlog cannot match a stale spawn.
  state.pendingSpawns = state.pendingSpawns.filter((s) => now - s.t < SPAWN_EXPIRES_AFTER);
  const inSession = (spawn: PendingSpawn) => spawn.session === session;
  let index = -1;
  if (agentType !== null) {
    index = state.pendingSpawns.findIndex((s) => inSession(s) && s.agentType === agentType);
  }
  if (index < 0) {
    index = state.pendingSpawns.findIndex((s) => inSession(s) && s.agentType === null);
  }
  if (index < 0) return null;
  const [spawn] = state.pendingSpawns.splice(index, 1);
  return spawn;
}

function foldRun(state: LiveState, event: RunEvent): LiveState {
  const existing = state.agents[event.run];
  // A done run is final. A run that ended in attention may be revived by a
  // later "working" event.
  if (existing && existing.finishedAt !== undefined && existing.status === "done") return state;
  const next = copy(state);
  const team = ensureTeam(next, event);
  let agent: LiveAgent;
  if (existing) {
    agent = update(existing, event.t, { status: event.status });
  } else {
    agent = {
      id: event.run,
      teamId: event.session,
      kind: "delegated",
      role: event.role ?? "implementer",
      name: nameFor(event.run),
      label: event.label ?? "delegated run",
      action: "thinking",
      status: event.status,
      host: hostOf(event.host),
      project: team.project,
      startedAt: event.t,
      lastEventAt: event.t,
      statusSince: event.t,
    };
  }
  // "done" and "attention" are terminal: the run leaves after a short linger.
  if (event.status === "working") {
    delete agent.finishedAt;
  } else if (event.status === "done" || agent.finishedAt === undefined) {
    agent.finishedAt = event.t;
  }
  next.agents[event.run] = agent;
  return next;
}

export function fold(state: LiveState, event: WorldEvent): LiveState {
  const session = event.session;
  const endedAt = state.ended[session];
  // Async hooks can deliver trailing events after session-end. Only a new
  // "session" event (a resume or restart) brings the session back.
  if (endedAt !== undefined && event.event !== "session") return state;
  if (endedAt !== undefined) {
    const { [session]: _cleared, ...ended } = state.ended;
    state = { ...state, ended };
  }

  if (event.event === "run") return foldRun(state, event);

  if (event.event === "session-end") {
    const next = copy(state);
    removeSession(next, session);
    next.ended[session] = event.t;
    return next;
  }

  if (event.event === "subagent-stop") {
    const sub = event.agent ? state.agents[event.agent] : undefined;
    if (!sub || sub.teamId !== session || sub.kind !== "subagent" || sub.finishedAt !== undefined) {
      return state;
    }
  }

  const next = copy(state);
  const team = ensureTeam(next, event);
  if (!next.agents[session]) next.agents[session] = newCoordinator(event, team.project);

  if (event.event === "subagent-start") {
    foldSubagentStart(next, event, team);
    return next;
  }

  const targetId = event.agent ?? session;
  const target = next.agents[targetId];
  // Events for sub-agents we never saw start, or that already ended, only
  // keep the team alive.
  if (!target || target.teamId !== session || target.finishedAt !== undefined) return next;

  const isCoordinator = target.kind === "coordinator";
  switch (event.event) {
    case "session":
      next.agents[targetId] = update(target, event.t);
      break;
    case "prompt":
      next.agents[targetId] = update(target, event.t, { status: "working", action: "thinking" });
      break;
    case "tool":
      next.agents[targetId] = update(target, event.t, {
        status: "working",
        action: event.action ?? "other",
      });
      if (event.action === "spawn" && event.phase !== "post") {
        next.pendingSpawns.push({
          session,
          agentType: event.agentType,
          label: event.label,
          role: event.role,
          t: event.t,
        });
      }
      break;
    case "permission":
      next.agents[targetId] = update(target, event.t, { status: "attention" });
      break;
    case "notification":
      if (event.status === "waiting") {
        next.agents[targetId] = update(target, event.t, { status: "attention" });
      } else if (event.status === "idle" && isCoordinator) {
        next.agents[targetId] = update(target, event.t, { status: "ready", action: "thinking" });
      } else {
        next.agents[targetId] = update(target, event.t);
      }
      break;
    case "stop":
      next.agents[targetId] = isCoordinator
        ? update(target, event.t, { status: "ready", action: "thinking" })
        : update(target, event.t);
      break;
    case "subagent-stop": {
      const status: LiveStatus =
        event.status === "error" || event.status === "interrupted" ? "attention" : "done";
      next.agents[targetId] = {
        ...update(target, event.t, { status, action: "thinking" }),
        finishedAt: event.t,
      };
      break;
    }
  }
  return next;
}

function foldSubagentStart(state: LiveState, event: HookEvent, team: LiveTeam): void {
  if (!event.agent) return;
  const existing = state.agents[event.agent];
  if (existing) {
    if (existing.teamId === event.session && existing.finishedAt === undefined) {
      state.agents[event.agent] = update(existing, event.t, { status: "working" });
    }
    return;
  }
  const spawn = takeSpawn(state, event.session, event.agentType, event.t);
  const label = spawn?.label ?? event.agentType ?? "sub-agent";
  state.agents[event.agent] = {
    id: event.agent,
    teamId: event.session,
    kind: "subagent",
    role: classifyRole(event.agentType, label, spawn?.role ?? event.role),
    name: nameFor(event.agent),
    label,
    action: "thinking",
    status: "working",
    host: hostOf(event.host),
    project: team.project,
    startedAt: event.t,
    lastEventAt: event.t,
    statusSince: event.t,
  };
}

export function tick(state: LiveState, now: number): LiveState {
  const silent = new Set<string>();
  for (const team of Object.values(state.teams)) {
    if (now - team.lastEventAt >= TEAM_SILENT_AFTER) silent.add(team.id);
  }

  let changed = silent.size > 0;
  const agents: Record<string, LiveAgent> = {};
  for (const agent of Object.values(state.agents)) {
    if (silent.has(agent.teamId)) continue;
    let current = agent;
    if (agent.finishedAt !== undefined) {
      const linger = agent.status === "attention" ? ATTENTION_LINGER : FINISHED_LINGER;
      if (now - agent.finishedAt >= linger) {
        changed = true;
        continue;
      }
    } else {
      if (current.action !== "thinking" && now - current.lastEventAt >= THINKING_AFTER) {
        current = { ...current, action: "thinking" };
      }
      // A coordinator is alive while any event arrives for its session.
      const lastActivity =
        agent.kind === "coordinator"
          ? Math.max(agent.lastEventAt, state.teams[agent.teamId]?.lastEventAt ?? 0)
          : agent.lastEventAt;
      if (current.status === "working" && now - lastActivity >= UNCERTAIN_AFTER) {
        current = { ...current, status: "uncertain", statusSince: lastActivity + UNCERTAIN_AFTER };
      }
    }
    if (current !== agent) changed = true;
    agents[agent.id] = current;
  }

  const ended: Record<string, number> = {};
  for (const [session, endedAt] of Object.entries(state.ended)) {
    if (now - endedAt < TEAM_SILENT_AFTER) ended[session] = endedAt;
    else changed = true;
  }

  const pendingSpawns = state.pendingSpawns.filter(
    (spawn) => !silent.has(spawn.session) && now - spawn.t < SPAWN_EXPIRES_AFTER,
  );
  if (pendingSpawns.length !== state.pendingSpawns.length) changed = true;

  if (!changed) return state;
  const teams: Record<string, LiveTeam> = {};
  for (const team of Object.values(state.teams)) {
    if (!silent.has(team.id)) teams[team.id] = team;
  }
  return { teams, agents, pendingSpawns, ended };
}
