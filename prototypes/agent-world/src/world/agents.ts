import * as THREE from "three/webgpu";
import type { Agent, SnapshotTeam } from "../app/types";
import { nearestEntrance, type Placement } from "../app/behaviour";
import type { Vec2, Vec3 } from "../contract/manifest";
import { cellToWorld, worldToCell } from "../contract/grid";
import { findPath, simplifyPath } from "./pathfinding";
import { createCharacter, phaseOf, type CharacterRig, type Gesture } from "./characters";
import type { LoadedEnvironment } from "./environment";

const WALK_SPEED = 1.7; // metres per second
/** How long a finished agent lingers by its coordinator before heading out. */
const HANDOFF_SECONDS = 1.6;

/**
 * Where a tracked character is in its lifecycle: in the room, or leaving
 * (finished agents first walk to their coordinator and wave, then everyone
 * leaving walks to the nearest entrance and is removed there).
 */
type Phase = "present" | "toCoordinator" | "handoff" | "toExit";

interface Tracked {
  agent: Agent;
  rig: CharacterRig;
  blob: THREE.Mesh;
  ring: THREE.Mesh;
  pos: THREE.Vector3;
  yaw: number;
  placement: Placement | null;
  route: Vec2[]; // remaining world points while travelling
  phase: Phase;
  handoffLeft: number;
  /** Who a finished agent walks to before leaving. */
  coordinatorId: string | null;
  /** False once the agent has dropped out of the snapshot (it has no badge then). */
  inSnapshot: boolean;
  dimmed: boolean;
}

const GESTURES: Record<Placement["activity"], Gesture> = { action: "action", idle: "idle", alert: "alert", review: "wave" };

const placementKey = (p: Placement) => `${p.at[0]},${p.at[1]}|${p.seated}|${p.lift}|${p.facing}`;
const wrap = (a: number) => ((a + Math.PI * 3) % (Math.PI * 2)) - Math.PI;

let blobParts: { geometry: THREE.PlaneGeometry; material: THREE.MeshBasicMaterial } | null = null;

/** A soft contact shadow for baked scenes; geometry, texture and material are shared. */
function blobShadow(): THREE.Mesh {
  if (!blobParts) {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 64;
    const ctx = canvas.getContext("2d")!;
    const g = ctx.createRadialGradient(32, 32, 4, 32, 32, 30);
    g.addColorStop(0, "rgba(28,18,30,0.75)");
    g.addColorStop(0.6, "rgba(28,18,30,0.35)");
    g.addColorStop(1, "rgba(28,18,30,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 64, 64);
    blobParts = {
      geometry: new THREE.PlaneGeometry(1.5, 1.5),
      material: new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(canvas), transparent: true, depthWrite: false }),
    };
  }
  const mesh = new THREE.Mesh(blobParts.geometry, blobParts.material);
  mesh.rotation.x = -Math.PI / 2;
  mesh.position.y = 0.02;
  mesh.renderOrder = 1;
  return mesh;
}

let ringParts: { geometry: THREE.PlaneGeometry; texture: THREE.CanvasTexture } | null = null;

/** A soft ring in the team's accent on the ground under each agent; its material is per agent (colour, pulse). */
function statusRing(): THREE.Mesh {
  if (!ringParts) {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 128;
    const ctx = canvas.getContext("2d")!;
    ctx.strokeStyle = "white";
    ctx.lineWidth = 12;
    ctx.beginPath();
    ctx.arc(64, 64, 50, 0, Math.PI * 2);
    ctx.stroke();
    ctx.globalAlpha = 0.25;
    ctx.fillStyle = "white";
    ctx.fill();
    ringParts = { geometry: new THREE.PlaneGeometry(1.25, 1.25), texture: new THREE.CanvasTexture(canvas) };
  }
  const mesh = new THREE.Mesh(
    ringParts.geometry,
    new THREE.MeshBasicMaterial({ map: ringParts.texture, transparent: true, depthWrite: false, toneMapped: false }),
  );
  mesh.rotation.x = -Math.PI / 2;
  mesh.renderOrder = 2;
  return mesh;
}

/**
 * The agents in the world. New agents enter from the nearest entrance and
 * walk to their place by A*; agents present when an environment loads start
 * in place. Finished agents walk to their team's coordinator, then out;
 * agents that leave the snapshot (or whose whole team does) walk out.
 */
export class AgentLayer {
  readonly group = new THREE.Group();
  private tracked = new Map<string, Tracked>();
  private env: LoadedEnvironment | null = null;
  private blobs = false;
  private warned = new Set<string>();
  /** True until the first sync after an environment loads: agents then start in place. */
  private fresh = true;
  selectedId: string | null = null;
  /** Simpler idle motion, for the lower quality tiers. */
  calm = false;

  constructor(scene: THREE.Scene) {
    scene.add(this.group);
  }

  get count() {
    return this.tracked.size;
  }

  setEnvironment(env: LoadedEnvironment) {
    this.env = env;
    this.blobs = env.manifest.lighting === "baked";
    this.fresh = true;
    for (const t of [...this.tracked.values()]) {
      if (t.phase !== "present") {
        this.remove(t);
        continue;
      }
      t.blob.visible = this.blobs;
      t.placement = null; // forces a re-seat in the new space
      t.route = [];
    }
  }

  sync(agents: Agent[], placements: Map<string, Placement>, teams: SnapshotTeam[]) {
    const fresh = this.fresh;
    this.fresh = false;
    const listed = new Set(agents.map((a) => a.id));
    const accents = new Map(teams.map((t) => [t.id, t.accent]));

    for (const t of this.tracked.values()) {
      if (listed.has(t.agent.id)) continue;
      t.inSnapshot = false;
      if (t.phase === "present") this.leave(t, false);
    }

    for (const agent of agents) {
      let t = this.tracked.get(agent.id);
      if (agent.status === "done") {
        // Finished: never shown if it was already finished when first seen.
        if (!t) continue;
        t.agent = agent;
        t.inSnapshot = true;
        if (t.phase === "present") this.leave(t, true);
        this.paint(t, accents);
        continue;
      }
      const placement = placements.get(agent.id);
      if (!placement) continue;
      const isNew = !t;
      if (t && t.rig.role !== agent.role) this.rebuild(t, agent);
      t ??= this.create(agent);
      t.agent = agent;
      t.inSnapshot = true;
      const changed = !t.placement || placementKey(t.placement) !== placementKey(placement) || t.phase !== "present";
      t.placement = placement;
      t.phase = "present";
      t.coordinatorId = null;
      if (changed) {
        if (fresh) this.teleport(t, placement.at, placement.facing);
        else {
          if (isNew && this.env) {
            const door = nearestEntrance(this.env.manifest, placement.at);
            this.teleport(t, door, Math.atan2(placement.at[0] - door[0], placement.at[1] - door[1]));
          }
          t.route = this.route(t, placement.at) ?? [];
          if (!t.route.length) this.teleport(t, placement.at, placement.facing);
        }
      }
      this.paint(t, accents);
    }
  }

  private create(agent: Agent): Tracked {
    const rig = createCharacter(agent.look, "agent", agent.role, phaseOf(agent.id));
    rig.group.userData.agentId = agent.id;
    const blob = blobShadow();
    blob.visible = this.blobs;
    const ring = statusRing();
    this.group.add(rig.group, blob, ring);
    const t: Tracked = {
      agent, rig, blob, ring, pos: new THREE.Vector3(), yaw: 0, placement: null, route: [], phase: "present",
      handoffLeft: 0, coordinatorId: null, inSnapshot: true, dimmed: false,
    };
    this.tracked.set(agent.id, t);
    return t;
  }

  /** A role change swaps the character's look. */
  private rebuild(t: Tracked, agent: Agent) {
    t.rig.dispose();
    t.rig = createCharacter(agent.look, "agent", agent.role, phaseOf(agent.id));
    t.rig.group.userData.agentId = agent.id;
    t.dimmed = false;
    this.group.add(t.rig.group);
  }

  private paint(t: Tracked, accents: Map<string, string>) {
    (t.ring.material as THREE.MeshBasicMaterial).color.set(accents.get(t.agent.teamId) ?? t.agent.look.accent);
    t.rig.setAlert(t.phase === "present" && t.agent.status === "issue");
    const dimmed = t.agent.status === "uncertain";
    if (dimmed !== t.dimmed) {
      t.rig.setDimmed(dimmed);
      t.dimmed = dimmed;
    }
  }

  /** Starts leaving: finished agents call on their coordinator first; everyone ends at an entrance. */
  private leave(t: Tracked, viaCoordinator: boolean) {
    t.placement = null;
    t.rig.setAlert(false);
    const coordinator = viaCoordinator ? this.coordinatorOf(t) : null;
    if (!coordinator) return this.exit(t);
    t.phase = "toCoordinator";
    t.coordinatorId = coordinator.agent.id;
    t.route = this.route(t, [coordinator.pos.x, coordinator.pos.z], true) ?? [];
  }

  private exit(t: Tracked) {
    t.phase = "toExit";
    t.coordinatorId = null;
    if (!this.env) return this.remove(t);
    const route = this.route(t, nearestEntrance(this.env.manifest, [t.pos.x, t.pos.z]));
    if (!route) return this.remove(t);
    t.route = route;
  }

  /** The agent's team coordinator, when it is still in the room. */
  private coordinatorOf(t: Tracked): Tracked | null {
    if (t.agent.kind === "coordinator") return null;
    for (const c of this.tracked.values())
      if (c !== t && c.agent.teamId === t.agent.teamId && c.agent.kind === "coordinator" && c.phase === "present" && c.inSnapshot)
        return c;
    return null;
  }

  private remove(t: Tracked) {
    t.rig.dispose();
    t.blob.removeFromParent();
    t.ring.removeFromParent();
    (t.ring.material as THREE.Material).dispose();
    this.tracked.delete(t.agent.id);
  }

  private teleport(t: Tracked, at: Vec2, facing: number) {
    t.pos.set(at[0], 0, at[1]);
    t.route = [];
    t.yaw = facing;
    t.rig.group.rotation.y = facing;
  }

  /**
   * World points along an A* path to `goal`, or null when there is none.
   * `stopShort` ends one cell before the goal, to stand next to someone.
   */
  private route(t: Tracked, goal: Vec2, stopShort = false): Vec2[] | null {
    if (!this.env) return [goal];
    const grid = this.env.manifest.grid;
    const from = worldToCell(grid, t.pos.x, t.pos.z);
    const to = worldToCell(grid, goal[0], goal[1]);
    const path = findPath(this.env.walk, from, to);
    if (!path) {
      if (!this.warned.has(t.agent.id)) console.warn(`No walkable path for ${t.agent.name}; moving directly.`);
      this.warned.add(t.agent.id);
      return null;
    }
    if (stopShort) {
      if (path.length <= 2) return [];
      return simplifyPath(path.slice(0, -1)).slice(1).map(([c, r]) => cellToWorld(grid, c, r));
    }
    const points = simplifyPath(path).slice(1, -1).map(([c, r]) => cellToWorld(grid, c, r));
    return [...points, goal];
  }

  update(dt: number, time: number) {
    for (const t of [...this.tracked.values()]) {
      if (t.route.length) {
        this.moveToward(t, t.route[0], WALK_SPEED * dt, () => t.route.shift());
        t.rig.setPose({ stance: "walk", gesture: "none", action: t.agent.action, doorBearing: 0, calm: this.calm }, time);
        if (!t.route.length) this.arrive(t);
      } else if (t.phase === "toCoordinator" || t.phase === "toExit") {
        this.arrive(t); // nothing to walk: already there
      }
      if (!this.tracked.has(t.agent.id)) continue; // walked out
      if (!t.route.length && t.phase === "handoff") {
        t.handoffLeft -= dt;
        const c = t.coordinatorId ? this.tracked.get(t.coordinatorId) : undefined;
        if (c) t.yaw = Math.atan2(c.pos.x - t.pos.x, c.pos.z - t.pos.z);
        t.rig.setPose({ stance: "standing", gesture: "wave", action: t.agent.action, doorBearing: 0, calm: this.calm }, time);
        if (t.handoffLeft <= 0) this.exit(t);
        if (!this.tracked.has(t.agent.id)) continue;
      } else if (!t.route.length && t.phase === "present") {
        const p = t.placement;
        if (!p) continue;
        t.rig.setPose(
          {
            stance: p.seated ? "seated" : "standing",
            gesture: GESTURES[p.activity],
            action: t.agent.action,
            doorBearing: t.agent.action === "spawn" ? this.doorBearing(t) : 0,
            calm: this.calm,
          },
          time,
        );
      }
      const lift = t.phase === "present" && !t.route.length && t.placement?.seated ? t.placement.lift : 0;
      t.rig.group.position.set(t.pos.x, lift, t.pos.z);
      const current = t.rig.group.rotation.y;
      t.rig.group.rotation.y = current + wrap(t.yaw - current) * Math.min(1, dt * 10);
      t.blob.position.set(t.pos.x, 0.03, t.pos.z);
      t.ring.position.set(t.pos.x, 0.05, t.pos.z);
      const urgent = t.phase === "present" && (t.agent.status === "issue" || t.agent.status === "review");
      const pulse = urgent ? 1 + Math.sin(time * 4) * 0.12 : 1;
      t.ring.scale.setScalar(pulse * (this.selectedId === t.agent.id ? 1.3 : 1));
      (t.ring.material as THREE.MeshBasicMaterial).opacity = urgent ? 0.75 + Math.sin(time * 4) * 0.25 : t.dimmed ? 0.35 : 0.65;
    }
  }

  /** The end of a route: settle into place, start the hand-off, or leave through the door. */
  private arrive(t: Tracked) {
    switch (t.phase) {
      case "present":
        if (t.placement) t.yaw = t.placement.facing;
        break;
      case "toCoordinator":
        t.phase = "handoff";
        t.handoffLeft = HANDOFF_SECONDS;
        break;
      case "toExit":
        this.remove(t);
        break;
    }
  }

  /** Yaw from the agent's facing to the nearest entrance, in -PI..PI. */
  private doorBearing(t: Tracked): number {
    if (!this.env) return 0;
    const door = nearestEntrance(this.env.manifest, [t.pos.x, t.pos.z]);
    return wrap(Math.atan2(door[0] - t.pos.x, door[1] - t.pos.z) - t.yaw);
  }

  private moveToward(t: Tracked, target: Vec2, maxStep: number, onArrive: () => void) {
    const dx = target[0] - t.pos.x, dz = target[1] - t.pos.z;
    const dist = Math.hypot(dx, dz);
    if (dist <= maxStep || dist < 1e-4) {
      t.pos.set(target[0], 0, target[1]);
      onArrive();
      return;
    }
    t.pos.x += (dx / dist) * maxStep;
    t.pos.z += (dz / dist) * maxStep;
    t.yaw = Math.atan2(dx, dz);
  }

  /** Ground position for camera following. */
  groundOf(id: string): Vec2 | null {
    const t = this.tracked.get(id);
    return t ? [t.pos.x, t.pos.z] : null;
  }

  /** Point above the head for the status badge; null once the agent has left. */
  badgeAnchor(id: string): Vec3 | null {
    const t = this.tracked.get(id);
    if (!t || !t.inSnapshot) return null;
    const lift = t.agent.status === "issue" && t.phase === "present" ? 3.35 : 2.05; // clear the "!" beacon
    return [t.rig.group.position.x, t.rig.group.position.y + lift, t.rig.group.position.z];
  }

  isTravelling(id: string) {
    return (this.tracked.get(id)?.route.length ?? 0) > 0;
  }

  pick(raycaster: THREE.Raycaster): string | null {
    const targets = [...this.tracked.values()].filter((t) => t.inSnapshot).map((t) => t.rig.group);
    const hits = raycaster.intersectObjects(targets, true);
    for (const hit of hits) {
      let o: THREE.Object3D | null = hit.object;
      while (o && o.userData.agentId === undefined) o = o.parent;
      if (o) return o.userData.agentId as string;
    }
    return null;
  }

  dispose() {
    for (const t of [...this.tracked.values()]) this.remove(t);
    this.group.removeFromParent();
  }
}
