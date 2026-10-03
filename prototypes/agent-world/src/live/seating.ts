// Seat allocator for the live agent world. Pure: no DOM, no Three.js, no
// input mutation. The world calls it whenever the agent list changes and
// passes the previous result back so seated agents stay where they are.

import { worldToCell } from "../contract/grid";
import type { EnvironmentManifest, Seat, SeatGroup, SeatGroupKind, Vec2 } from "../contract/manifest";
import { findPath, type Cell, type WalkGrid } from "../world/pathfinding";
import type { LiveAgent, Role } from "./types";

export type SeatAssignment = { seat: Seat; group: SeatGroup } | { standAt: Vec2 };

/** Group kinds that suit a role, best first. */
const KIND_PREFERENCE: Record<Role, readonly SeatGroupKind[]> = {
  coordinator: [],
  implementer: ["desk", "table"],
  tester: ["desk", "table"],
  documenter: ["table"],
  researcher: ["bench", "lounge", "bar"],
  reviewer: ["standing"],
};

/** Spacing of the rings that overflow agents stand on, in metres. */
const RING_SPACING = 0.8;
/** Standing points closer than this count as the same spot. */
const MIN_SEPARATION = 0.6;
/** Rings beyond this radius index may land on blocked cells. */
const MAX_WALKABLE_RING = 40;

const seatKey = (group: SeatGroup, seat: Seat) => `${group.id}\u0000${seat.id}`;

/** Coordinators first, then by start time, then by id. */
function stableOrder(a: LiveAgent, b: LiveAgent): number {
  const ca = a.kind === "coordinator" ? 0 : 1;
  const cb = b.kind === "coordinator" ? 0 : 1;
  if (ca !== cb) return ca - cb;
  if (a.startedAt !== b.startedAt) return a.startedAt - b.startedAt;
  return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
}

function pathCost(path: Cell[]): number {
  let cost = 0;
  for (let i = 1; i < path.length; i++) {
    const diagonal = path[i][0] !== path[i - 1][0] && path[i][1] !== path[i - 1][1];
    cost += diagonal ? Math.SQRT2 : 1;
  }
  return cost;
}

/**
 * Overflow standing points: lounge loop points, then lounge positions, then
 * entrances. Ring 0 is the anchor itself; ring r adds 6r points at r * 0.8 m,
 * so spacing stays near 0.8 m. Rings are interleaved across anchors.
 */
function standSlots(manifest: EnvironmentManifest, walk: WalkGrid, count: number): Vec2[] {
  const anchors: Vec2[] = [];
  for (const zone of manifest.zones.lounge) for (const p of zone.loop ?? []) anchors.push([p[0], p[1]]);
  for (const zone of manifest.zones.lounge) anchors.push([zone.position[0], zone.position[2]]);
  for (const e of manifest.entrances) anchors.push([e[0], e[1]]);
  if (anchors.length === 0) anchors.push([0, 0]);

  const slots: Vec2[] = [];
  const free = (p: Vec2) => slots.every((s) => Math.hypot(s[0] - p[0], s[1] - p[1]) >= MIN_SEPARATION);
  const open = (p: Vec2) => {
    const [c, r] = worldToCell(manifest.grid, p[0], p[1]);
    return walk.walkable(c, r);
  };
  for (let ring = 0; slots.length < count; ring++) {
    for (const anchor of anchors) {
      const points = ring === 0 ? 1 : 6 * ring;
      for (let k = 0; k < points && slots.length < count; k++) {
        const angle = (2 * Math.PI * k) / points;
        const p: Vec2 =
          ring === 0
            ? [anchor[0], anchor[1]]
            : [anchor[0] + Math.cos(angle) * RING_SPACING * ring, anchor[1] + Math.sin(angle) * RING_SPACING * ring];
        if (ring > 0 && ring <= MAX_WALKABLE_RING && !open(p)) continue;
        if (free(p)) slots.push(p);
      }
    }
  }
  return slots;
}

export function allocate(
  previous: Map<string, SeatAssignment>,
  agents: LiveAgent[],
  manifest: EnvironmentManifest,
  walk: WalkGrid,
): Map<string, SeatAssignment> {
  const groups = manifest.seating;
  const groupIndex = new Map(groups.map((g, i) => [g.id, i]));
  const taken = new Set<string>();
  const result = new Map<string, SeatAssignment>();
  const homes = new Map<string, SeatGroup>();
  const heldBy = new Map<string, string>();
  const teamOf = new Map<string, string>();

  const seen = new Set<string>();
  const ordered = agents.filter((a) => !seen.has(a.id) && !!seen.add(a.id)).sort(stableOrder);
  for (const a of ordered) teamOf.set(a.id, a.teamId);

  const freeSeats = (g: SeatGroup) => g.seats.filter((s) => !taken.has(seatKey(g, s)));
  const firstFree = (g: SeatGroup) => g.seats.find((s) => !taken.has(seatKey(g, s)));

  const claim = (agent: LiveAgent, group: SeatGroup, seat: Seat) => {
    taken.add(seatKey(group, seat));
    result.set(agent.id, { seat, group });
    if (agent.kind === "coordinator" && !homes.has(agent.teamId)) {
      homes.set(agent.teamId, group);
      heldBy.set(group.id, agent.teamId);
    }
  };

  // Walking distance between two groups' first seats, cached per call.
  const cellOfSeat = (g: SeatGroup): Cell | null => {
    const s = g.seats[0];
    return s ? worldToCell(manifest.grid, s.position[0], s.position[2]) : null;
  };
  const distances = new Map<string, number>();
  const distanceFrom = (origin: Cell | null, g: SeatGroup): number => {
    const to = cellOfSeat(g);
    if (!origin || !to) return Infinity;
    const key = `${origin[0]},${origin[1]}>${g.id}`;
    let d = distances.get(key);
    if (d === undefined) {
      const path = findPath(walk, origin, to);
      d = path ? pathCost(path) : Infinity;
      distances.set(key, d);
    }
    return d;
  };

  // Pass 1: seated agents keep their seat when it still exists.
  for (const a of ordered) {
    const prev = previous.get(a.id);
    if (!prev || !("seat" in prev)) continue;
    const group = groups[groupIndex.get(prev.group.id) ?? -1];
    const seat = group?.seats.find((s) => s.id === prev.seat.id);
    if (group && seat && !taken.has(seatKey(group, seat))) claim(a, group, seat);
  }

  const pickCoordinator = (a: LiveAgent): SeatGroup | undefined => {
    const open = groups.filter((g) => freeSeats(g).length > 0);
    const unheld = open.filter((g) => !heldBy.has(g.id) || heldBy.get(g.id) === a.teamId);
    const pool = unheld.length > 0 ? unheld : open;
    let best: SeatGroup | undefined;
    for (const g of pool) if (!best || freeSeats(g).length > freeSeats(best).length) best = g;
    return best;
  };

  const rank = (a: LiveAgent, candidates: SeatGroup[], origin: Cell | null): SeatGroup | undefined => {
    const prefs = KIND_PREFERENCE[a.role];
    const scored = candidates.map((g) => {
      const d = distanceFrom(origin, g);
      const tier = prefs.indexOf(g.kind);
      return {
        g,
        key: [d === Infinity ? 1 : 0, tier < 0 ? prefs.length : tier, d, groupIndex.get(g.id)!],
      };
    });
    scored.sort((x, y) => {
      for (let i = 0; i < x.key.length; i++) {
        if (x.key[i] !== y.key[i]) return x.key[i] < y.key[i] ? -1 : 1;
      }
      return 0;
    });
    return scored[0]?.g;
  };

  const pickMember = (a: LiveAgent): SeatGroup | undefined => {
    const home = homes.get(a.teamId);
    let anchor = home;
    if (!anchor) {
      for (const [id, assignment] of result) {
        if (teamOf.get(id) === a.teamId && "seat" in assignment) {
          anchor = assignment.group;
          break;
        }
      }
    }
    const entrance = manifest.entrances[0];
    const origin: Cell | null = anchor
      ? cellOfSeat(anchor)
      : entrance
        ? worldToCell(manifest.grid, entrance[0], entrance[1])
        : null;

    const open = groups.filter((g) => freeSeats(g).length > 0);
    if (a.role === "reviewer") {
      const standing = open.filter((g) => g.kind === "standing");
      if (standing.length > 0) return rank(a, standing, origin);
    }
    if (home && freeSeats(home).length > 0) return home;
    return rank(a, open, origin);
  };

  // Pass 2: everyone else, coordinators first.
  const standing: LiveAgent[] = [];
  for (const a of ordered) {
    if (result.has(a.id)) continue;
    const group = a.kind === "coordinator" ? pickCoordinator(a) : pickMember(a);
    const seat = group && firstFree(group);
    if (group && seat) claim(a, group, seat);
    else standing.push(a);
  }

  // Pass 3: overflow. Agents already standing somewhere keep that spot.
  if (standing.length > 0) {
    const kept = standing.filter((a) => {
      const prev = previous.get(a.id);
      return prev !== undefined && "standAt" in prev;
    });
    const slots = standSlots(manifest, walk, standing.length + kept.length);
    const used = new Set<number>();
    const same = (p: Vec2, q: Vec2) => Math.abs(p[0] - q[0]) < 1e-6 && Math.abs(p[1] - q[1]) < 1e-6;
    const placed = new Set<string>();
    for (const a of kept) {
      const prev = previous.get(a.id) as { standAt: Vec2 };
      const i = slots.findIndex((s, idx) => !used.has(idx) && same(s, prev.standAt));
      if (i >= 0) {
        used.add(i);
        placed.add(a.id);
        result.set(a.id, { standAt: [slots[i][0], slots[i][1]] });
      }
    }
    let next = 0;
    for (const a of standing) {
      if (placed.has(a.id)) continue;
      while (used.has(next)) next++;
      used.add(next);
      result.set(a.id, { standAt: [slots[next][0], slots[next][1]] });
    }
  }

  return result;
}
