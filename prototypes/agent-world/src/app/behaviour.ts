import { worldToCell } from "../contract/grid";
import type { EnvironmentManifest, Vec2 } from "../contract/manifest";
import { allocate, type SeatAssignment } from "../live/seating";
import type { WalkGrid } from "../world/pathfinding";
import type { Agent } from "./types";

/**
 * What the character does once in place: its current action (working), its
 * role's idle personality (ready or quiet), the attention alert (issue) or a
 * wave at the review board (review).
 */
export type Activity = "action" | "idle" | "alert" | "review";

/** Where one agent belongs in the world and how it behaves there. */
export interface Placement {
  /** World [x, z]. */
  at: Vec2;
  /** Yaw in radians; 0 faces +Z. */
  facing: number;
  /** Height of the seat (bar stools sit higher); 0 when standing. */
  lift: number;
  seated: boolean;
  activity: Activity;
  /** No recent activity: shown desaturated. */
  dimmed: boolean;
}

export interface Placements {
  /** The allocator's result; pass it back next time so seats stay sticky. */
  seats: Map<string, SeatAssignment>;
  placements: Map<string, Placement>;
}

// Review spots: the classic huddle first, then rings around the board.
const HUDDLE: Vec2[] = [[0, 0], [0.9, 0.3], [-0.9, 0.3], [0.5, 1], [-0.5, 1]];
const REVIEW_RING_SPACING = 0.9;
const REVIEW_RINGS = 6;
/** A review spot keeps this far from seats, standing points and other spots. */
const REVIEW_CLEARANCE = 0.85;

/** Agents that hold a seat: finished agents are on their way out and give theirs up. */
export function seatableAgents(agents: Agent[]): Agent[] {
  return agents.filter((a) => a.status !== "done");
}

/** The declared entrance closest (in a straight line) to a world point; the origin when there is none. */
export function nearestEntrance(manifest: Pick<EnvironmentManifest, "entrances">, from: Vec2): Vec2 {
  let best: Vec2 = [0, 0];
  let bestDistance = Infinity;
  for (const e of manifest.entrances) {
    const d = Math.hypot(e[0] - from[0], e[1] - from[1]);
    if (d < bestDistance) {
      bestDistance = d;
      best = [e[0], e[1]];
    }
  }
  return best;
}

/**
 * Spots around the review zones, in a fixed order, each clear of `occupied`
 * points and of every earlier spot, and on a walkable cell.
 */
function reviewSpots(manifest: EnvironmentManifest, walk: WalkGrid, occupied: Vec2[], count: number): Vec2[] {
  const spots: Vec2[] = [];
  if (count === 0) return spots;
  const clear = (p: Vec2) =>
    [...occupied, ...spots].every((q) => Math.hypot(q[0] - p[0], q[1] - p[1]) >= REVIEW_CLEARANCE) &&
    walk.walkable(...worldToCell(manifest.grid, p[0], p[1]));
  const anchors = manifest.zones.review.map((z): Vec2 => [z.position[0], z.position[2]]);
  const offsets: Vec2[] = [...HUDDLE];
  for (let ring = 1; ring <= REVIEW_RINGS; ring++)
    for (let k = 0; k < 6 * ring; k++) {
      const angle = (2 * Math.PI * k) / (6 * ring);
      offsets.push([Math.cos(angle) * REVIEW_RING_SPACING * ring, Math.sin(angle) * REVIEW_RING_SPACING * ring]);
    }
  for (const offset of offsets)
    for (const anchor of anchors) {
      if (spots.length >= count) return spots;
      const p: Vec2 = [anchor[0] + offset[0], anchor[1] + offset[1]];
      if (clear(p)) spots.push(p);
    }
  // A board boxed in on every side: share its spot rather than vanish.
  while (spots.length < count) spots.push(anchors[0] ?? [0, 0]);
  return spots;
}

/** The middle of the first lounge (its loop's centroid), which overflow agents face. */
function loungeCentre(manifest: EnvironmentManifest): Vec2 | null {
  const zone = manifest.zones.lounge[0];
  if (!zone) return null;
  const points = zone.loop?.length ? zone.loop : [[zone.position[0], zone.position[2]] as Vec2];
  return [points.reduce((s, p) => s + p[0], 0) / points.length, points.reduce((s, p) => s + p[1], 0) / points.length];
}

/**
 * Places every agent that is still in the room. Seats come from the sticky
 * allocator (finished agents are left out, so their seat is free at once).
 * Working agents act out their current action; ready agents show their
 * role's idle personality; quiet ("uncertain") agents stay seated and are
 * dimmed; agents that need attention stand at their seat with the alert;
 * agents awaiting review walk to the review board and keep their seat for
 * later. Agents beyond the seats stand where the allocator puts them.
 */
export function placeAgents(
  previous: Map<string, SeatAssignment>,
  agents: Agent[],
  manifest: EnvironmentManifest,
  walk: WalkGrid,
): Placements {
  const present = seatableAgents(agents);
  const seats = allocate(previous, present, manifest, walk);
  const placements = new Map<string, Placement>();

  const occupied: Vec2[] = manifest.seating.flatMap((g) => g.seats.map((s): Vec2 => [s.position[0], s.position[2]]));
  for (const a of seats.values()) if ("standAt" in a) occupied.push(a.standAt);
  const reviewers = present.filter((a) => a.status === "review");
  const spots = reviewSpots(manifest, walk, occupied, reviewers.length);
  const reviewFacing = manifest.zones.review[0]?.facing ?? 0;
  const lounge = loungeCentre(manifest);

  reviewers.forEach((agent, i) => {
    placements.set(agent.id, { at: spots[i], facing: reviewFacing, lift: 0, seated: false, activity: "review", dimmed: false });
  });

  for (const agent of present) {
    if (agent.status === "review") continue;
    const seat = seats.get(agent.id);
    if (!seat) continue;
    const activity = agent.status === "working" ? "action" : agent.status === "issue" ? "alert" : "idle";
    const dimmed = agent.status === "uncertain";
    if ("standAt" in seat) {
      const [x, z] = seat.standAt;
      const facing = lounge ? Math.atan2(lounge[0] - x, lounge[1] - z) : 0;
      placements.set(agent.id, { at: [x, z], facing, lift: 0, seated: false, activity, dimmed });
      continue;
    }
    const at: Vec2 = [seat.seat.position[0], seat.seat.position[2]];
    const seated = activity !== "alert" && seat.seat.pose === "seated";
    placements.set(agent.id, { at, facing: seat.seat.facing, lift: seated ? seat.seat.position[1] : 0, seated, activity, dimmed });
  }
  return { seats, placements };
}
