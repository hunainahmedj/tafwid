import { describe, expect, it, vi } from "vitest";
import { createStore, deriveStats, initialState } from "../../src/app/store";
import { createFixtureSource } from "../../src/app/fixtures";

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

describe("deriveStats", () => {
  it("counts the productive day", () => {
    expect(deriveStats(createFixtureSource("productive-day").current())).toEqual({
      working: 2,
      review: 1,
      attention: 1,
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
