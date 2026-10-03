import type { Action, AppState, Snapshot } from "./types";

export interface Store {
  get(): AppState;
  dispatch(action: Action): void;
  subscribe(fn: (state: AppState, prev: AppState) => void): () => void;
}

export function initialState(snapshot: Snapshot, overrides: Partial<AppState> = {}): AppState {
  return {
    snapshot,
    selectedId: null,
    mode: "explore",
    environmentId: "cafe",
    variant: "kit",
    filter: "all",
    quality: "high",
    qualityAuto: true,
    worldAvailable: true,
    worldError: null,
    source: "sample",
    liveEnabled: false,
    projectFilter: null,
    ...overrides,
  };
}

/** The agents the project filter lets through. */
export function visibleAgents(snapshot: Snapshot, projectFilter: string | null) {
  return projectFilter === null ? snapshot.agents : snapshot.agents.filter((a) => a.project === projectFilter);
}

/**
 * Brings the filter and the selection back in line with the snapshot: a
 * filter on a project that has gone is dropped, and a selection survives only
 * while its agent is still visible.
 */
function settle(s: AppState): AppState {
  const projectFilter =
    s.projectFilter !== null && !s.snapshot.teams.some((t) => t.project === s.projectFilter) ? null : s.projectFilter;
  const selectedId =
    s.selectedId !== null && visibleAgents(s.snapshot, projectFilter).some((a) => a.id === s.selectedId) ? s.selectedId : null;
  return projectFilter === s.projectFilter && selectedId === s.selectedId ? s : { ...s, projectFilter, selectedId };
}

function reduce(s: AppState, a: Action): AppState {
  switch (a.type) {
    case "select":
      return s.selectedId === a.id ? s : { ...s, selectedId: a.id };
    case "setMode":
      if (!s.worldAvailable || s.mode === a.mode) return s;
      return { ...s, mode: a.mode };
    case "setVariant":
      return s.variant === a.variant ? s : { ...s, variant: a.variant, worldError: null };
    case "setFilter":
      return s.filter === a.filter ? s : { ...s, filter: a.filter };
    case "snapshot":
      return settle({ ...s, snapshot: a.snapshot });
    case "setSource":
      return s.source === a.source && !a.snapshot ? s : settle({ ...s, source: a.source, snapshot: a.snapshot ?? s.snapshot });
    case "setLiveEnabled":
      return s.liveEnabled === a.enabled ? s : { ...s, liveEnabled: a.enabled };
    case "setProjectFilter":
      return s.projectFilter === a.project ? s : settle({ ...s, projectFilter: a.project });
    case "setQuality":
      return s.quality === a.tier && s.qualityAuto === a.auto ? s : { ...s, quality: a.tier, qualityAuto: a.auto };
    case "worldUnavailable":
      return { ...s, worldAvailable: false, mode: "dashboard", worldError: a.reason };
    case "worldError":
      return s.worldError === a.message ? s : { ...s, worldError: a.message };
  }
}

export function createStore(initial: AppState): Store {
  let state = initial;
  const listeners = new Set<(s: AppState, p: AppState) => void>();
  return {
    get: () => state,
    dispatch(action) {
      const prev = state;
      state = reduce(state, action);
      if (state !== prev) listeners.forEach((fn) => fn(state, prev));
    },
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
  };
}

export function deriveStats(s: Snapshot) {
  const count = (status: string) => s.agents.filter((a) => a.status === status).length;
  return {
    working: count("working"),
    review: count("review"),
    attention: count("issue"),
    ready: count("ready"),
    completed: s.completedThisSession,
  };
}
