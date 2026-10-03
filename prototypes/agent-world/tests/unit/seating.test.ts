import { describe, expect, it } from "vitest";
import fixture from "./fixtures/manifest.valid.json";
import type { EnvironmentManifest, SeatGroup } from "../../src/contract/manifest";
import { parseWalkable, worldToCell } from "../../src/contract/grid";
import type { LiveAgent, Role } from "../../src/live/types";
import { allocate, type SeatableAgent, type SeatAssignment } from "../../src/live/seating";

// Fixture groups (12 seats): desk-1 (3), bar (4), bench-1 (2), table-1 (3).
const STANDING: SeatGroup = {
  id: "review-1",
  kind: "standing",
  seats: [
    { id: "review-1-a", position: [4.5, 0, -2.5], facing: 3.14159, pose: "standing" },
    { id: "review-1-b", position: [5.5, 0, -2.5], facing: 3.14159, pose: "standing" },
  ],
};

function manifest(opts: { standing?: boolean; walkable?: string[] } = {}): EnvironmentManifest {
  const base = structuredClone(fixture) as unknown as EnvironmentManifest;
  if (opts.standing) base.seating.push(structuredClone(STANDING));
  if (opts.walkable) base.grid.walkable = opts.walkable;
  return base;
}

let counter = 0;
function agent(
  id: string,
  teamId: string,
  kind: LiveAgent["kind"],
  role: Role,
  startedAt = ++counter,
): LiveAgent {
  return {
    id, teamId, kind, role, name: id, label: id, action: "other", status: "working",
    host: "claude", project: "p", startedAt, lastEventAt: startedAt, statusSince: startedAt,
  };
}
const coord = (id: string, team: string, t?: number) => agent(id, team, "coordinator", "coordinator", t);
const sub = (id: string, team: string, role: Role, t?: number) => agent(id, team, "subagent", role, t);

function run(
  agents: SeatableAgent[],
  m = manifest(),
  previous = new Map<string, SeatAssignment>(),
) {
  return allocate(previous, agents, m, parseWalkable(m.grid));
}

function groupOf(map: Map<string, SeatAssignment>, id: string): string {
  const a = map.get(id);
  if (!a || !("seat" in a)) throw new Error(`${id} has no seat`);
  return a.group.id;
}
function seatKey(a: SeatAssignment): string {
  return "seat" in a ? `${a.group.id}/${a.seat.id}` : `at:${a.standAt[0]},${a.standAt[1]}`;
}

/** A previous-result map that puts the given agents on the first seats of a group. */
function holding(m: EnvironmentManifest, groupId: string, ids: string[]): Map<string, SeatAssignment> {
  const group = m.seating.find((g) => g.id === groupId)!;
  return new Map(ids.map((id, i) => [id, { seat: group.seats[i], group }]));
}

/** A team of one coordinator plus `n` filler sub-agents of one role. */
function filled(team: string, n: number, role: Role = "implementer"): LiveAgent[] {
  const list = [coord(`${team}-c`, team)];
  for (let i = 0; i < n; i++) list.push(sub(`${team}-f${i}`, team, role));
  return list;
}

describe("allocate: coordinators", () => {
  it("takes the group with the most free seats", () => {
    const out = run([coord("c1", "t1")]);
    expect(groupOf(out, "c1")).toBe("bar");
  });

  it("holds a group per team and breaks ties by manifest order", () => {
    const out = run([coord("c1", "t1"), coord("c2", "t2"), coord("c3", "t3")]);
    expect(groupOf(out, "c1")).toBe("bar");
    expect(groupOf(out, "c2")).toBe("desk-1");
    expect(groupOf(out, "c3")).toBe("table-1");
  });

  it("processes coordinators before sub-agents regardless of list order", () => {
    const list = [sub("s1", "t1", "implementer", 1), coord("c1", "t1", 5)];
    const out = run(list);
    expect(groupOf(out, "s1")).toBe(groupOf(out, "c1"));
  });
});

describe("allocate: sample agents", () => {
  it("sorts the sample kind like a sub-agent, after the coordinator", () => {
    const sample: SeatableAgent = { id: "s1", teamId: "t1", kind: "sample", role: "implementer", startedAt: 1 };
    const out = run([sample, coord("c1", "t1", 5)]);
    expect(groupOf(out, "c1")).toBe("bar");
    expect(groupOf(out, "s1")).toBe("bar");
  });
});

describe("allocate: team members", () => {
  it("fill the team's home group first", () => {
    const list = [coord("c1", "t1"), sub("a", "t1", "researcher"), sub("b", "t1", "documenter"), sub("c", "t1", "reviewer")];
    const out = run(list);
    for (const id of ["a", "b", "c"]) expect(groupOf(out, id)).toBe("bar");
    const seats = ["c1", "a", "b", "c"].map((id) => seatKey(out.get(id)!));
    expect(new Set(seats).size).toBe(4);
  });

  it("overflow goes to the nearest group by walking-path length", () => {
    // No standing group, so a reviewer has no preferred kind: pure distance.
    const out = run([...filled("t1", 3), sub("late", "t1", "reviewer", 1_000_000)]);
    expect(groupOf(out, "late")).toBe("desk-1");
  });

  it("measures walking-path length, not straight-line distance", () => {
    // A wall at column 2 forces a long detour to desk-1 and table-1, so the
    // bench (5 cells away along an open row) is nearer on foot.
    const rows = Array.from({ length: 8 }, (_, r) => (r < 7 ? "..#........." : "............"));
    const out = run([...filled("t1", 3), sub("late", "t1", "reviewer", 1_000_000)], manifest({ walkable: rows }));
    expect(groupOf(out, "late")).toBe("bench-1");
  });

  it("ranks unreachable groups last", () => {
    // Wall in the bench (cols 9-10 of row 3). A researcher prefers the bench,
    // but it cannot be reached, so the reachable desk wins.
    const rows = [
      "............",
      "............",
      "..##....####",
      "........#..#",
      "........####",
      "............",
      "............",
      "............",
    ];
    const out = run([...filled("t1", 3), sub("a", "t1", "researcher", 1_000_000)], manifest({ walkable: rows }));
    expect(groupOf(out, "a")).toBe("desk-1");
  });

  it("falls back to any free seat when no preferred kind has room", () => {
    const out = run([...filled("t1", 3), sub("doc", "t1", "documenter", 1_000_000)]);
    expect(groupOf(out, "doc")).toBe("table-1");
  });
});

describe("allocate: kind preferences outside the home group", () => {
  const full = (late: LiveAgent, m = manifest({ standing: true })) => run([...filled("t1", 3), late], m);
  const late = (id: string, role: Role) => sub(id, "t1", role, 1_000_000);

  it("implementers prefer desk, then table", () => {
    const m = manifest({ standing: true });
    expect(groupOf(full(late("x", "implementer"), m), "x")).toBe("desk-1");
    // Fill the desk with another team's coordinator: desk gone, table next.
    const list = [...filled("t1", 3), coord("c2", "t2"), sub("d1", "t2", "implementer"), sub("d2", "t2", "implementer"), sub("x", "t1", "implementer")];
    // t2 coordinator takes desk-1 (most free after bar); its members fill it.
    const out = run(list, m);
    expect(groupOf(out, "c2")).toBe("desk-1");
    expect(groupOf(out, "x")).toBe("table-1");
  });

  it("testers prefer desk, then table", () => {
    expect(groupOf(full(late("x", "tester")), "x")).toBe("desk-1");
  });

  it("documenters prefer table", () => {
    expect(groupOf(full(late("x", "documenter")), "x")).toBe("table-1");
  });

  it("researchers prefer bench, then lounge, then bar", () => {
    expect(groupOf(full(late("x", "researcher")), "x")).toBe("bench-1");

    // Orphan team (no coordinator), with other agents already in the way.
    const m = manifest();
    m.seating.push({
      id: "lounge-s",
      kind: "lounge",
      seats: [{ id: "lounge-s-a", position: [0.5, 0, 2.5], facing: 0, pose: "seated" }],
    });
    const benchFull = holding(m, "bench-1", ["o1", "o2"]);
    const others = [sub("o1", "t9", "implementer", 1), sub("o2", "t9", "implementer", 2)];
    const researcher = sub("x", "t2", "researcher", 3);
    expect(groupOf(run([...others, researcher], m, benchFull), "x")).toBe("lounge-s");

    const loungeToo = new Map([...benchFull, ...holding(m, "lounge-s", ["o3"])]);
    const more = [...others, sub("o3", "t9", "implementer", 2.5), researcher];
    expect(groupOf(run(more, m, loungeToo), "x")).toBe("bar");
  });

  it("reviewers prefer standing", () => {
    expect(groupOf(full(late("x", "reviewer")), "x")).toBe("review-1");
  });

  it("a reviewer goes to a free standing seat even when the home group has room", () => {
    const out = run([coord("c1", "t1"), sub("r", "t1", "reviewer")], manifest({ standing: true }));
    expect(groupOf(out, "c1")).toBe("bar");
    expect(groupOf(out, "r")).toBe("review-1");
  });

  it("with no coordinator seated, members go to the nearest suitable group", () => {
    const out = run([sub("a", "orphan", "documenter"), sub("b", "orphan", "documenter")]);
    expect(groupOf(out, "a")).toBe("table-1");
    expect(groupOf(out, "b")).toBe("table-1");
  });
});

describe("allocate: stickiness and reuse", () => {
  it("keeps previous assignments and never moves a seated agent", () => {
    const m = manifest();
    const first = run([sub("a", "t1", "implementer", 1), sub("b", "t1", "implementer", 2)], m);
    const second = run(
      [coord("c1", "t1", 0), sub("a", "t1", "implementer", 1), sub("b", "t1", "implementer", 2), sub("z", "t2", "researcher", 3)],
      m,
      first,
    );
    expect(seatKey(second.get("a")!)).toBe(seatKey(first.get("a")!));
    expect(seatKey(second.get("b")!)).toBe(seatKey(first.get("b")!));
    const keys = [...second.values()].map(seatKey);
    expect(new Set(keys).size).toBe(keys.length);
  });

  it("ignores a previous seat that no longer exists in the manifest", () => {
    const m = manifest();
    const prev = new Map<string, SeatAssignment>([
      ["a", { seat: { id: "gone", position: [0, 0, 0], facing: 0, pose: "seated" }, group: { id: "gone-group", kind: "desk", seats: [] } }],
    ]);
    const out = run([sub("a", "t1", "implementer")], m, prev);
    expect(groupOf(out, "a")).not.toBe("gone-group");
  });

  it("reuses a freed seat", () => {
    const m = manifest();
    const team = [coord("c1", "t1", 1), sub("a", "t1", "implementer", 2), sub("b", "t1", "implementer", 3)];
    const first = run(team, m);
    const bSeat = seatKey(first.get("b")!);
    const second = run([team[0], team[1]], m, first);
    expect(second.has("b")).toBe(false);
    const third = run([team[0], team[1], sub("d", "t1", "implementer", 9)], m, second);
    expect(seatKey(third.get("d")!)).toBe(bSeat);
  });

  it("does not mutate its inputs", () => {
    const m = manifest();
    const snapshot = JSON.stringify(m);
    const agents = [coord("c1", "t1"), sub("a", "t1", "implementer")];
    const agentsSnap = JSON.stringify(agents);
    const prev = run(agents, m);
    const prevKeys = [...prev.entries()].map(([k, v]) => [k, seatKey(v)]);
    run(agents, m, prev);
    expect(JSON.stringify(m)).toBe(snapshot);
    expect(JSON.stringify(agents)).toBe(agentsSnap);
    expect([...prev.entries()].map(([k, v]) => [k, seatKey(v)])).toEqual(prevKeys);
  });
});

describe("allocate: overflow", () => {
  it("gives standAt lounge positions, with no duplicates, when every seat is taken", () => {
    const m = manifest();
    const agents = [coord("c1", "t1")];
    for (let i = 0; i < 17; i++) agents.push(sub(`s${i}`, "t1", "implementer"));
    const out = run(agents, m);
    expect(out.size).toBe(18);
    const seated = [...out.values()].filter((a) => "seat" in a);
    const standing = [...out.values()].filter((a): a is { standAt: [number, number] } => "standAt" in a);
    expect(seated).toHaveLength(12);
    expect(standing).toHaveLength(6);
    const keys = [...out.values()].map(seatKey);
    expect(new Set(keys).size).toBe(keys.length);
    // The first stand points are the lounge loop points.
    const loop = m.zones.lounge[0].loop!;
    for (const p of loop) {
      expect(standing.some((s) => s.standAt[0] === p[0] && s.standAt[1] === p[1])).toBe(true);
    }
    // Spacing: no two standing agents closer than 0.5 m.
    for (let i = 0; i < standing.length; i++) {
      for (let j = i + 1; j < standing.length; j++) {
        const d = Math.hypot(standing[i].standAt[0] - standing[j].standAt[0], standing[i].standAt[1] - standing[j].standAt[1]);
        expect(d).toBeGreaterThan(0.5);
      }
    }
  });

  it("keeps a standing agent's spot while it still stands", () => {
    const m = manifest();
    const agents = [coord("c1", "t1")];
    for (let i = 0; i < 14; i++) agents.push(sub(`s${i}`, "t1", "implementer"));
    const first = run(agents, m);
    const second = run([...agents, sub("extra", "t1", "implementer", 999)], m, first);
    for (const a of agents) expect(seatKey(second.get(a.id)!)).toBe(seatKey(first.get(a.id)!));
  });

  it("seats a standing agent when a seat frees up", () => {
    const m = manifest();
    const agents = [coord("c1", "t1")];
    for (let i = 0; i < 12; i++) agents.push(sub(`s${i}`, "t1", "implementer"));
    const first = run(agents, m);
    expect("standAt" in first.get("s11")!).toBe(true);
    const second = run(agents.filter((a) => a.id !== "s3"), m, first);
    expect("seat" in second.get("s11")!).toBe(true);
  });
});

describe("allocate: overflow stickiness and ordering", () => {
  const standAt = (a: SeatAssignment): [number, number] => {
    if (!("standAt" in a)) throw new Error("expected standAt");
    return a.standAt;
  };

  it("keeps a standing agent's exact spot when the standers ahead of it leave", () => {
    const m = manifest();
    const agents = [coord("c1", "t1", 1)];
    for (let i = 0; i < 31; i++) agents.push(sub(`s${String(i).padStart(2, "0")}`, "t1", "implementer", 2 + i));
    const first = run(agents, m);
    const standers = agents.filter((a) => "standAt" in first.get(a.id)!);
    const seated = agents.filter((a) => "seat" in first.get(a.id)!);
    expect(standers).toHaveLength(20);
    expect(seated).toHaveLength(12);

    const keep = standers.slice(-3);
    const second = run([...seated, ...keep], m, first);
    for (const a of keep) expect(standAt(second.get(a.id)!)).toEqual(standAt(first.get(a.id)!));
    for (const a of seated) expect(seatKey(second.get(a.id)!)).toBe(seatKey(first.get(a.id)!));
    const keys = [...second.values()].map(seatKey);
    expect(new Set(keys).size).toBe(keys.length);
  });

  it("fills the lounge before any entrance", () => {
    const m = manifest();
    m.entrances = [[-5.5, 3.5]];
    const agents = [coord("c1", "t1", 1)];
    for (let i = 0; i < 41; i++) agents.push(sub(`s${String(i).padStart(2, "0")}`, "t1", "implementer", 2 + i));
    const out = run(agents, m);
    const standing = [...out.values()].filter((a) => "standAt" in a).map(standAt);
    expect(standing).toHaveLength(30);
    const lounge = m.zones.lounge[0].loop!;
    for (const p of standing) {
      expect(Math.hypot(p[0] - -5.5, p[1] - 3.5)).toBeGreaterThan(1);
      // Every spot sits near the lounge, not near the doorway.
      const nearest = Math.min(...lounge.map((l) => Math.hypot(p[0] - l[0], p[1] - l[1])));
      expect(nearest).toBeLessThan(4);
    }
  });
});

describe("allocate: capacity limits", () => {
  it("gives 12 seats plus 20 unique, well-spaced standing points for 32 agents", () => {
    const m = manifest();
    const agents = [coord("c1", "t1", 1)];
    for (let i = 0; i < 31; i++) agents.push(sub(`s${i}`, "t1", "implementer", 2 + i));
    const out = run(agents, m);
    const stand = [...out.values()].filter((a) => "standAt" in a).map((a) => (a as { standAt: [number, number] }).standAt);
    expect(out.size).toBe(32);
    expect([...out.values()].filter((a) => "seat" in a)).toHaveLength(12);
    expect(stand).toHaveLength(20);
    const seatPositions = m.seating.flatMap((g) => g.seats.map((s) => [s.position[0], s.position[2]]));
    for (let i = 0; i < stand.length; i++) {
      for (const sp of seatPositions) expect(Math.hypot(stand[i][0] - sp[0], stand[i][1] - sp[1])).toBeGreaterThanOrEqual(0.6);
      for (let j = i + 1; j < stand.length; j++) {
        expect(Math.hypot(stand[i][0] - stand[j][0], stand[i][1] - stand[j][1])).toBeGreaterThanOrEqual(0.6);
      }
    }
  });

  it("keeps standing points off blocked cells", () => {
    const rows = [
      "............",
      "............",
      "..##....##..",
      "............",
      "..##.##.##..",
      "............",
      "..##....##..",
      "............",
    ];
    const m = manifest({ walkable: rows });
    const agents = [coord("c1", "t1", 1)];
    for (let i = 0; i < 31; i++) agents.push(sub(`s${i}`, "t1", "implementer", 2 + i));
    const out = run(agents, m);
    const walk = parseWalkable(m.grid);
    const stand = [...out.values()].filter((a) => "standAt" in a);
    expect(stand).toHaveLength(20);
    for (const a of stand) {
      const [x, z] = (a as { standAt: [number, number] }).standAt;
      const [c, r] = worldToCell(m.grid, x, z);
      expect(walk.walkable(c, r)).toBe(true);
    }
  });

  it("prefers a farther kind-matched group over a nearer unsuited one", () => {
    // Same layout, bar full, desk and table nearer than the bench.
    const nearest = run([...filled("t1", 3), sub("late", "t1", "reviewer", 1_000_000)]);
    expect(groupOf(nearest, "late")).toBe("desk-1");
    const researcher = run([...filled("t1", 3), sub("late", "t1", "researcher", 1_000_000)]);
    expect(groupOf(researcher, "late")).toBe("bench-1");
    const documenter = run([...filled("t1", 3), sub("late", "t1", "documenter", 1_000_000)]);
    expect(groupOf(documenter, "late")).toBe("table-1");
  });
});

describe("allocate: determinism", () => {
  it("returns the same output for the same input", () => {
    const agents = [coord("c1", "t1"), coord("c2", "t2"), sub("a", "t1", "reviewer"), sub("b", "t2", "researcher"), sub("c", "t1", "tester")];
    const m = manifest({ standing: true });
    const one = [...run(agents, m).entries()].map(([k, v]) => [k, seatKey(v)]);
    const two = [...run(agents, m).entries()].map(([k, v]) => [k, seatKey(v)]);
    expect(two).toEqual(one);
  });

  it("does not depend on the order new agents are listed in", () => {
    const agents = [coord("c1", "t1", 1), coord("c2", "t2", 2), sub("a", "t1", "reviewer", 3), sub("b", "t2", "researcher", 4), sub("c", "t1", "tester", 5)];
    const m = manifest({ standing: true });
    const seats = (list: LiveAgent[]) => Object.fromEntries([...run(list, m).entries()].map(([k, v]) => [k, seatKey(v)]));
    expect(seats([...agents].reverse())).toEqual(seats(agents));
  });
});
