import { describe, expect, it } from "vitest";
import valid from "./fixtures/manifest.valid.json";
import { nearestEntrance, placeAgents, seatableAgents, type Placement } from "../../src/app/behaviour";
import { createFixtureSource } from "../../src/app/fixtures";
import { parseWalkable } from "../../src/contract/grid";
import type { EnvironmentManifest } from "../../src/contract/manifest";
import type { Agent } from "../../src/app/types";
import type { SeatAssignment } from "../../src/live/seating";

const manifest = valid as unknown as EnvironmentManifest;
const walk = parseWalkable(manifest.grid);
const seats = manifest.seating.flatMap((group) => group.seats);
const sample = () => structuredClone(createFixtureSource("productive-day").current().agents);
const withStatus = (list: Agent[], id: string, status: Agent["status"]) =>
  list.map((a) => (a.id === id ? { ...a, status } : a));
const place = (agents: Agent[], previous = new Map<string, SeatAssignment>()) =>
  placeAgents(previous, agents, manifest, walk);

/** `n` working sub-agents in one team, after its coordinator. */
function crowd(n: number, status: Agent["status"] = "working"): Agent[] {
  const base = sample()[0];
  const list: Agent[] = [{ ...base, id: "c", kind: "coordinator", role: "coordinator", startedAt: 0 }];
  for (let i = 0; i < n; i++)
    list.push({ ...base, id: `s${i}`, kind: "sample", role: "implementer", status, startedAt: 1000 + i });
  return list;
}

const distance = (a: Placement, b: Placement) => Math.hypot(a.at[0] - b.at[0], a.at[1] - b.at[1]);

describe("placeAgents", () => {
  it("places more agents than the environment has seats without throwing", () => {
    const list = crowd(19); // 20 agents, 12 seats
    expect(seats.length).toBe(12);
    const { placements } = place(list);
    expect(placements.size).toBe(20);
    const standing = [...placements.values()].filter((p) => !p.seated);
    expect(standing.length).toBe(8);
  });

  it("keeps every placement at least 0.85 m (wider than a head) from every other one in a crowd", () => {
    const list = crowd(30).map((a, i) => (i % 5 === 1 ? { ...a, status: "review" as const } : a));
    const all = [...place(list).placements.values()];
    for (let i = 0; i < all.length; i++)
      for (let j = i + 1; j < all.length; j++) expect(distance(all[i], all[j])).toBeGreaterThanOrEqual(0.85);
  });

  it("seats working agents at their seat with the action activity", () => {
    const { seats: assigned, placements } = place(sample());
    const ada = assigned.get("ada");
    if (!ada || !("seat" in ada)) throw new Error("ada has no seat");
    expect(placements.get("ada")).toMatchObject({
      at: [ada.seat.position[0], ada.seat.position[2]],
      facing: ada.seat.facing,
      seated: true,
      activity: "action",
      dimmed: false,
    });
  });

  it("is sticky: passing the previous seats back keeps everyone in place", () => {
    const first = place(sample());
    const second = place(withStatus(sample(), "rex", "working"), first.seats);
    for (const id of ["milo", "ada", "noor", "rex"])
      expect(second.placements.get(id)!.at).toEqual(first.placements.get(id)!.at);
  });

  it("leaves done agents out of the allocation and out of the placements", () => {
    const list = withStatus(sample(), "ada", "done");
    const { seats: assigned, placements } = place(list);
    expect(assigned.has("ada")).toBe(false);
    expect(placements.has("ada")).toBe(false);
    expect(seatableAgents(list).map((a) => a.id)).not.toContain("ada");
  });

  it("frees a done agent's seat for the next newcomer", () => {
    const list = crowd(11); // 12 agents fill the 12 seats
    const first = place(list);
    const doneSeat = first.placements.get("s3")!.at;
    const next = [...list.map((a) => (a.id === "s3" ? { ...a, status: "done" as const } : a)),
      { ...list[1], id: "late", startedAt: 9999 }];
    const second = place(next, first.seats);
    expect(second.placements.get("late")).toMatchObject({ seated: true, at: doneSeat });
  });

  it("dims uncertain agents and keeps them seated", () => {
    const { placements } = place(withStatus(sample(), "ada", "uncertain"));
    expect(placements.get("ada")).toMatchObject({ seated: true, dimmed: true, activity: "idle" });
  });

  it("ready agents sit with their idle personality", () => {
    expect(place(sample()).placements.get("noor")).toMatchObject({ seated: true, activity: "idle", dimmed: false });
  });

  it("issue agents stand at their own seat with the alert", () => {
    const { seats: assigned, placements } = place(sample());
    const rex = assigned.get("rex");
    if (!rex || !("seat" in rex)) throw new Error("rex has no seat");
    expect(placements.get("rex")).toMatchObject({
      at: [rex.seat.position[0], rex.seat.position[2]],
      seated: false,
      lift: 0,
      activity: "alert",
    });
  });

  it("review agents stand at the review zone and keep their seat for later", () => {
    const { seats: assigned, placements } = place(sample());
    const zone = manifest.zones.review[0];
    expect(placements.get("cleo")).toMatchObject({ at: [zone.position[0], zone.position[2]], seated: false, activity: "review" });
    expect(assigned.has("cleo")).toBe(true);
  });

  it("several review agents get separate spots near the board", () => {
    const list = sample().map((a) => (a.kind === "coordinator" ? a : { ...a, status: "review" as const }));
    const spots = list.filter((a) => a.status === "review").map((a) => place(list).placements.get(a.id)!);
    const zone = manifest.zones.review[0];
    for (const s of spots) expect(Math.hypot(s.at[0] - zone.position[0], s.at[1] - zone.position[2])).toBeLessThan(3);
    expect(new Set(spots.map((s) => s.at.join(","))).size).toBe(spots.length);
  });

  it("overflow agents stand, facing the lounge", () => {
    const { placements } = place(crowd(19));
    const standing = [...placements.values()].find((p) => !p.seated && p.activity === "action");
    expect(standing).toBeDefined();
    expect(standing!.lift).toBe(0);
  });
});

describe("nearestEntrance", () => {
  const m = { ...manifest, entrances: [[0, 0], [10, 0], [0, 10]] as [number, number][] };

  it("picks the closest entrance to a point", () => {
    expect(nearestEntrance(m, [9, 1])).toEqual([10, 0]);
    expect(nearestEntrance(m, [1, 8])).toEqual([0, 10]);
  });

  it("falls back to the origin when there is none", () => {
    expect(nearestEntrance({ ...manifest, entrances: [] }, [3, 3])).toEqual([0, 0]);
  });
});
