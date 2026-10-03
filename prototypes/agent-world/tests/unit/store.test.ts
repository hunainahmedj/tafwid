import { describe, expect, it, vi } from "vitest";
import { createStore, deriveStats, initialState, visibleAgents } from "../../src/app/store";
import { createFixtureSource } from "../../src/app/fixtures";
import { STATUS_LABELS, type Agent, type Snapshot } from "../../src/app/types";

const fresh = () => createStore(initialState(createFixtureSource("productive-day").current()));

describe("store", () => {
  it("select updates selection and notifies", () => {
    const store = fresh();
    const fn = vi.fn();
    store.subscribe(fn);
    store.dispatch({ type: "select", id: "ada" });
    expect(store.get().selectedId).toBe("ada");
    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn.mock.calls[0][1].selectedId).toBeNull();
  });

  it("setFilter keeps a selected agent selected even when filtered out", () => {
    const store = fresh();
    store.dispatch({ type: "select", id: "noor" });
    store.dispatch({ type: "setFilter", filter: "working" });
    expect(store.get().selectedId).toBe("noor");
  });

  it("snapshot that removes the selected agent clears selection", () => {
    const store = fresh();
    store.dispatch({ type: "select", id: "rex" });
    const snapshot = structuredClone(store.get().snapshot);
    snapshot.agents = snapshot.agents.filter((a) => a.id !== "rex");
    store.dispatch({ type: "snapshot", snapshot });
    expect(store.get().selectedId).toBeNull();
  });

  it("worldUnavailable forces dashboard mode", () => {
    const store = fresh();
    store.dispatch({ type: "worldUnavailable", reason: "no WebGL" });
    expect(store.get().mode).toBe("dashboard");
    store.dispatch({ type: "setMode", mode: "explore" });
    expect(store.get().mode).toBe("dashboard");
  });

  it("does not notify when an action changes nothing", () => {
    const store = fresh();
    const fn = vi.fn();
    store.subscribe(fn);
    store.dispatch({ type: "setMode", mode: "explore" });
    expect(fn).not.toHaveBeenCalled();
  });
});

const liveAgent = (id: string, project: string, status: Agent["status"] = "working"): Agent => ({
  ...structuredClone(createFixtureSource("productive-day").current().agents[0]),
  id,
  name: id,
  teamId: `team-${project}`,
  project,
  status,
  kind: "subagent",
});

const liveSnapshot = (agents: Agent[]): Snapshot => {
  const projects = [...new Set(agents.map((a) => a.project))];
  return {
    scenarioId: "live",
    agents,
    completedThisSession: 0,
    overflow: {},
    teams: projects.map((project) => ({
      id: `team-${project}`,
      project,
      host: "claude",
      accent: "#e4572e",
      count: agents.filter((a) => a.project === project).length,
    })),
  };
};

describe("source and project filter", () => {
  it("starts in sample mode with live off and no project filter", () => {
    const s = fresh().get();
    expect(s.source).toBe("sample");
    expect(s.liveEnabled).toBe(false);
    expect(s.projectFilter).toBeNull();
  });

  it("setSource switches source, swaps the snapshot and notifies", () => {
    const store = fresh();
    const fn = vi.fn();
    store.subscribe(fn);
    const snapshot = liveSnapshot([liveAgent("a", "alpha")]);
    store.dispatch({ type: "setSource", source: "live", snapshot });
    expect(store.get().source).toBe("live");
    expect(store.get().snapshot).toBe(snapshot);
    expect(fn).toHaveBeenCalledTimes(1);
    store.dispatch({ type: "setSource", source: "live" });
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("setSource clears a selection that is not in the new snapshot", () => {
    const store = fresh();
    store.dispatch({ type: "select", id: "ada" });
    store.dispatch({ type: "setSource", source: "live", snapshot: liveSnapshot([liveAgent("a", "alpha")]) });
    expect(store.get().selectedId).toBeNull();
  });

  it("setSource keeps a selection that is still there", () => {
    const store = fresh();
    const sample = store.get().snapshot;
    store.dispatch({ type: "select", id: "ada" });
    store.dispatch({ type: "setSource", source: "sample", snapshot: structuredClone(sample) });
    store.dispatch({ type: "setSource", source: "live" });
    expect(store.get().selectedId).toBe("ada");
  });

  it("setSource clears a project filter whose project is gone", () => {
    const store = fresh();
    const [first] = store.get().snapshot.teams;
    store.dispatch({ type: "setProjectFilter", project: first.project });
    store.dispatch({ type: "setSource", source: "live", snapshot: liveSnapshot([liveAgent("a", "alpha")]) });
    expect(store.get().projectFilter).toBeNull();
  });

  it("setLiveEnabled records whether the bridge reports live activity on", () => {
    const store = fresh();
    store.dispatch({ type: "setLiveEnabled", enabled: true });
    expect(store.get().liveEnabled).toBe(true);
    const fn = vi.fn();
    store.subscribe(fn);
    store.dispatch({ type: "setLiveEnabled", enabled: true });
    expect(fn).not.toHaveBeenCalled();
  });

  it("the project filter keeps a selection whose agent is visible", () => {
    const store = fresh();
    store.dispatch({ type: "snapshot", snapshot: liveSnapshot([liveAgent("a", "alpha"), liveAgent("b", "beta")]) });
    store.dispatch({ type: "select", id: "a" });
    store.dispatch({ type: "setProjectFilter", project: "alpha" });
    expect(store.get().projectFilter).toBe("alpha");
    expect(store.get().selectedId).toBe("a");
  });

  it("the project filter clears a selection whose agent is filtered out", () => {
    const store = fresh();
    store.dispatch({ type: "snapshot", snapshot: liveSnapshot([liveAgent("a", "alpha"), liveAgent("b", "beta")]) });
    store.dispatch({ type: "select", id: "b" });
    store.dispatch({ type: "setProjectFilter", project: "alpha" });
    expect(store.get().selectedId).toBeNull();
  });

  it("clearing the project filter keeps the selection", () => {
    const store = fresh();
    store.dispatch({ type: "snapshot", snapshot: liveSnapshot([liveAgent("a", "alpha"), liveAgent("b", "beta")]) });
    store.dispatch({ type: "setProjectFilter", project: "alpha" });
    store.dispatch({ type: "select", id: "a" });
    store.dispatch({ type: "setProjectFilter", project: null });
    expect(store.get().selectedId).toBe("a");
  });

  it("an empty project name is a real project, not 'no filter'", () => {
    const store = fresh();
    store.dispatch({ type: "snapshot", snapshot: liveSnapshot([liveAgent("a", ""), liveAgent("b", "beta")]) });
    store.dispatch({ type: "setProjectFilter", project: "" });
    expect(store.get().projectFilter).toBe("");
    expect(visibleAgents(store.get().snapshot, "").map((a) => a.id)).toEqual(["a"]);
  });

  it("a snapshot that drops the filtered project clears the filter", () => {
    const store = fresh();
    store.dispatch({ type: "snapshot", snapshot: liveSnapshot([liveAgent("a", "alpha"), liveAgent("b", "beta")]) });
    store.dispatch({ type: "setProjectFilter", project: "alpha" });
    store.dispatch({ type: "snapshot", snapshot: liveSnapshot([liveAgent("b", "beta")]) });
    expect(store.get().projectFilter).toBeNull();
  });

  it("a snapshot that moves the selected agent out of the filtered project clears it", () => {
    const store = fresh();
    store.dispatch({ type: "snapshot", snapshot: liveSnapshot([liveAgent("a", "alpha"), liveAgent("b", "beta")]) });
    store.dispatch({ type: "setProjectFilter", project: "alpha" });
    store.dispatch({ type: "select", id: "a" });
    store.dispatch({ type: "snapshot", snapshot: liveSnapshot([liveAgent("a", "beta"), liveAgent("b", "beta"), liveAgent("c", "alpha")]) });
    expect(store.get().selectedId).toBeNull();
  });

  it("selecting an agent the project filter hides clears the filter and selects it", () => {
    const store = fresh();
    store.dispatch({ type: "snapshot", snapshot: liveSnapshot([liveAgent("a", "alpha"), liveAgent("b", "beta")]) });
    store.dispatch({ type: "setProjectFilter", project: "alpha" });
    store.dispatch({ type: "select", id: "b" });
    expect(store.get().projectFilter).toBeNull();
    expect(store.get().selectedId).toBe("b");
  });

  it("selecting a visible agent keeps the project filter", () => {
    const store = fresh();
    store.dispatch({ type: "snapshot", snapshot: liveSnapshot([liveAgent("a", "alpha"), liveAgent("b", "beta")]) });
    store.dispatch({ type: "setProjectFilter", project: "alpha" });
    store.dispatch({ type: "select", id: "a" });
    expect(store.get().projectFilter).toBe("alpha");
    store.dispatch({ type: "select", id: null });
    expect(store.get().projectFilter).toBe("alpha");
  });

  it("selecting an agent the filter hides clears an empty-name filter too", () => {
    const store = fresh();
    store.dispatch({ type: "snapshot", snapshot: liveSnapshot([liveAgent("a", ""), liveAgent("b", "beta")]) });
    store.dispatch({ type: "setProjectFilter", project: "" });
    store.dispatch({ type: "select", id: "b" });
    expect(store.get().projectFilter).toBeNull();
  });

  it("records whether the live bridge is reachable", () => {
    const store = fresh();
    expect(store.get().liveReachable).toBe(true);
    store.dispatch({ type: "setLiveReachable", reachable: false });
    expect(store.get().liveReachable).toBe(false);
    const fn = vi.fn();
    store.subscribe(fn);
    store.dispatch({ type: "setLiveReachable", reachable: false });
    expect(fn).not.toHaveBeenCalled();
  });

  it("a snapshot that still holds the selected agent under the filter keeps it", () => {
    const store = fresh();
    store.dispatch({ type: "snapshot", snapshot: liveSnapshot([liveAgent("a", "alpha"), liveAgent("b", "beta")]) });
    store.dispatch({ type: "setProjectFilter", project: "alpha" });
    store.dispatch({ type: "select", id: "a" });
    store.dispatch({ type: "snapshot", snapshot: liveSnapshot([liveAgent("a", "alpha")]) });
    expect(store.get().selectedId).toBe("a");
  });
});

describe("sample fixtures", () => {
  it("produce two teams with a coordinator each and sub-agents", () => {
    const { agents, teams } = createFixtureSource("productive-day").current();
    expect(teams).toHaveLength(2);
    expect(new Set(teams.map((t) => t.project)).size).toBe(2);
    for (const t of teams) {
      const members = agents.filter((a) => a.teamId === t.id);
      expect(t.count).toBe(members.length);
      expect(members.length).toBeGreaterThan(1);
      expect(members.filter((a) => a.kind === "coordinator")).toHaveLength(1);
      expect(members.filter((a) => a.kind === "sample").length).toBe(members.length - 1);
      for (const m of members) expect(m.project).toBe(t.project);
    }
    expect(agents.every((a) => a.teamId && a.project && a.role && a.action && a.host)).toBe(true);
  });

  it("keep the same two teams in the quiet morning", () => {
    expect(createFixtureSource("quiet-morning").current().teams).toHaveLength(2);
  });

  it("every status has a label", () => {
    for (const status of ["working", "review", "ready", "issue", "done", "uncertain"] as const)
      expect(STATUS_LABELS[status]).toBeTruthy();
  });
});

describe("deriveStats", () => {
  it("counts the productive day", () => {
    expect(deriveStats(createFixtureSource("productive-day").current())).toEqual({
      working: 2,
      review: 1,
      attention: 1,
      ready: 1,
      completed: 7,
    });
  });
});

describe("fixture source", () => {
  it("advance steps the scripted day and notifies", () => {
    const source = createFixtureSource("productive-day");
    const fn = vi.fn();
    source.subscribe(fn);
    source.advance();
    const rex = source.current().agents.find((a) => a.id === "rex")!;
    expect(rex.status).toBe("working");
    expect(fn).toHaveBeenCalledTimes(1);
  });
});
