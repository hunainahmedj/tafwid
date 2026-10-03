import { describe, expect, it } from "vitest";
import { createFixtureSource } from "../../src/app/fixtures";
import { ACTION_LABELS, ROLE_LABELS } from "../../src/app/types";

describe("sample scenarios", () => {
  it("give every agent a fixed start time, coordinators first in each team", () => {
    const agents = createFixtureSource("productive-day").current().agents;
    for (const a of agents) expect(Number.isFinite(a.startedAt)).toBe(true);
    const again = createFixtureSource("productive-day").current().agents;
    expect(again.map((a) => a.startedAt)).toEqual(agents.map((a) => a.startedAt));
    for (const team of new Set(agents.map((a) => a.teamId))) {
      const members = agents.filter((a) => a.teamId === team);
      const coordinator = members.find((a) => a.kind === "coordinator")!;
      for (const m of members) expect(m.startedAt).toBeGreaterThanOrEqual(coordinator.startedAt);
    }
  });

  it("the sample day ends with Ada finishing, then starts over", () => {
    const source = createFixtureSource("productive-day");
    const seen: string[] = [];
    for (let i = 0; i < 5; i++) {
      source.advance();
      seen.push(source.current().agents.find((a) => a.id === "ada")!.status);
    }
    expect(seen.at(-1)).toBe("done");
    source.advance();
    expect(source.current().agents.find((a) => a.id === "ada")!.status).toBe("working");
  });
});

describe("crowd scenario", () => {
  const snapshot = () => createFixtureSource("crowd").current();

  it("has four teams and about 44 agents, each team led by one coordinator", () => {
    const s = snapshot();
    expect(s.scenarioId).toBe("crowd");
    expect(s.teams).toHaveLength(4);
    expect(s.agents.length).toBe(44);
    for (const t of s.teams) {
      const members = s.agents.filter((a) => a.teamId === t.id);
      expect(t.count).toBe(members.length);
      expect(members.filter((a) => a.kind === "coordinator")).toHaveLength(1);
      expect(members.every((a) => a.project === t.project && a.look.accent === t.accent)).toBe(true);
    }
    expect(s.overflow).toEqual({});
  });

  it("covers every role, every action and a mix of statuses including done and uncertain", () => {
    const s = snapshot();
    expect(new Set(s.agents.map((a) => a.role))).toEqual(new Set(Object.keys(ROLE_LABELS)));
    const working = s.agents.filter((a) => a.status === "working");
    expect(new Set(working.map((a) => a.action))).toEqual(new Set(Object.keys(ACTION_LABELS)));
    const statuses = new Set(s.agents.map((a) => a.status));
    for (const status of ["working", "review", "ready", "issue", "done", "uncertain"] as const)
      expect(statuses).toContain(status);
  });

  it("is deterministic with unique ids and names", () => {
    const a = snapshot(), b = snapshot();
    expect(b).toEqual(a);
    expect(new Set(a.agents.map((x) => x.id)).size).toBe(a.agents.length);
    expect(new Set(a.agents.map((x) => x.name)).size).toBe(a.agents.length);
  });

  it("count sets how many agents are in the room; finished agents come on top", () => {
    const s = createFixtureSource("crowd", { count: 32 }).current();
    expect(s.agents.filter((a) => a.status !== "done")).toHaveLength(32);
    expect(s.agents.some((a) => a.status === "done")).toBe(true);
  });

  it("stepping finishes the next working sub-agent", () => {
    const source = createFixtureSource("crowd");
    const before = source.current().agents.filter((a) => a.status === "done").length;
    source.advance();
    const after = source.current().agents;
    expect(after.filter((a) => a.status === "done").length).toBe(before + 1);
    expect(after.filter((a) => a.status === "done" && a.kind === "coordinator")).toHaveLength(0);
  });
});
