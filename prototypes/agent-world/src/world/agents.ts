import * as THREE from "three/webgpu";
import type { Agent } from "../app/types";
import type { Assignment } from "../app/behaviour";
import type { Vec2, Vec3 } from "../contract/manifest";
import { cellToWorld, worldToCell } from "../contract/grid";
import { findPath, simplifyPath } from "./pathfinding";
import { createCharacter, type CharacterRig } from "./characters";
import type { LoadedEnvironment } from "./environment";

const WALK_SPEED = 1.7; // metres per second when changing zone
const WANDER_SPEED = 0.9;

const RING_COLOURS: Record<Agent["status"], string> = {
  working: "#2fbf86",
  review: "#ff9f2e",
  ready: "#4f7cff",
  issue: "#ff3b3b",
  done: "#4f7cff",
  uncertain: "#9aa3b2",
};

interface Tracked {
  agent: Agent;
  rig: CharacterRig;
  blob: THREE.Mesh;
  ring: THREE.Mesh;
  pos: THREE.Vector3;
  yaw: number;
  assignment: Assignment | null;
  route: Vec2[]; // remaining world points while travelling
  loopIndex: number;
}

const assignmentKey = (a: Assignment) => `${a.zone.id}|${a.pose}|${a.offset.join(",")}`;

function blobShadow(): THREE.Mesh {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 64;
  const ctx = canvas.getContext("2d")!;
  const g = ctx.createRadialGradient(32, 32, 4, 32, 32, 30);
  g.addColorStop(0, "rgba(28,18,30,0.75)");
  g.addColorStop(0.6, "rgba(28,18,30,0.35)");
  g.addColorStop(1, "rgba(28,18,30,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 64, 64);
  const mesh = new THREE.Mesh(
    new THREE.PlaneGeometry(1.5, 1.5),
    new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(canvas), transparent: true, depthWrite: false }),
  );
  mesh.rotation.x = -Math.PI / 2;
  mesh.position.y = 0.02;
  mesh.renderOrder = 1;
  return mesh;
}

let ringTexture: THREE.CanvasTexture | null = null;

/** A soft status-coloured ring on the ground under each agent. */
function statusRing(): THREE.Mesh {
  if (!ringTexture) {
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
    ringTexture = new THREE.CanvasTexture(canvas);
  }
  const mesh = new THREE.Mesh(
    new THREE.PlaneGeometry(1.25, 1.25),
    new THREE.MeshBasicMaterial({ map: ringTexture, transparent: true, depthWrite: false, toneMapped: false }),
  );
  mesh.rotation.x = -Math.PI / 2;
  mesh.renderOrder = 2;
  return mesh;
}

/** Places agents in their zones and walks them along A* paths when their zone changes. */
export class AgentLayer {
  readonly group = new THREE.Group();
  private tracked = new Map<string, Tracked>();
  private env: LoadedEnvironment | null = null;
  private blobs = false;
  private warned = new Set<string>();
  selectedId: string | null = null;

  constructor(scene: THREE.Scene) {
    scene.add(this.group);
  }

  setEnvironment(env: LoadedEnvironment) {
    this.env = env;
    this.blobs = env.manifest.lighting === "baked";
    for (const t of this.tracked.values()) {
      t.blob.visible = this.blobs;
      t.assignment = null; // forces a re-seat in the new space
    }
  }

  sync(agents: Agent[], assignments: Map<string, Assignment>) {
    for (const [id, t] of this.tracked)
      if (!agents.some((a) => a.id === id)) {
        t.rig.dispose();
        t.blob.removeFromParent();
        t.ring.removeFromParent();
        this.tracked.delete(id);
      }
    for (const agent of agents) {
      let t = this.tracked.get(agent.id);
      if (!t) {
        const rig = createCharacter(agent.look);
        rig.group.userData.agentId = agent.id;
        const blob = blobShadow();
        blob.visible = this.blobs;
        const ring = statusRing();
        this.group.add(rig.group, blob, ring);
        t = { agent, rig, blob, ring, pos: new THREE.Vector3(), yaw: 0, assignment: null, route: [], loopIndex: 0 };
        this.tracked.set(agent.id, t);
      }
      t.agent = agent;
      (t.ring.material as THREE.MeshBasicMaterial).color.set(RING_COLOURS[agent.status]);
      const next = assignments.get(agent.id) ?? null;
      if (!next) continue;
      const placed = t.assignment !== null;
      if (t.assignment && assignmentKey(t.assignment) === assignmentKey(next)) continue;
      t.assignment = next;
      t.rig.setAlert(agent.status === "issue");
      const goal = this.goalOf(next);
      if (!placed) {
        this.teleport(t, goal);
        continue;
      }
      t.route = this.route(t, goal);
    }
  }

  private goalOf(a: Assignment): Vec2 {
    const start = a.pose === "wander" && a.zone.loop?.length ? a.zone.loop[0] : [a.zone.position[0], a.zone.position[2]];
    return [start[0] + a.offset[0], start[1] + a.offset[1]];
  }

  private teleport(t: Tracked, goal: Vec2) {
    t.pos.set(goal[0], 0, goal[1]);
    t.route = [];
    t.loopIndex = 0;
    if (t.assignment) t.yaw = t.assignment.zone.facing;
  }

  private route(t: Tracked, goal: Vec2): Vec2[] {
    if (!this.env) return [goal];
    const grid = this.env.manifest.grid;
    const from = worldToCell(grid, t.pos.x, t.pos.z);
    const to = worldToCell(grid, goal[0], goal[1]);
    const path = findPath(this.env.walk, from, to);
    if (!path) {
      if (!this.warned.has(t.agent.id)) console.warn(`No walkable path for ${t.agent.name}; moving directly.`);
      this.warned.add(t.agent.id);
      this.teleport(t, goal);
      return [];
    }
    const points = simplifyPath(path).slice(1, -1).map(([c, r]) => cellToWorld(grid, c, r));
    return [...points, goal];
  }

  update(dt: number, time: number) {
    for (const t of this.tracked.values()) {
      const a = t.assignment;
      if (!a) continue;
      if (t.route.length) {
        this.moveToward(t, t.route[0], WALK_SPEED * dt, () => t.route.shift());
        t.rig.setPose("walk", time);
        if (!t.route.length) {
          t.loopIndex = 0;
          if (a.pose !== "wander") t.yaw = a.zone.facing;
        }
      } else if (a.pose === "wander" && a.zone.loop && a.zone.loop.length > 1) {
        const loop = a.zone.loop;
        const p = loop[(t.loopIndex + 1) % loop.length];
        this.moveToward(t, [p[0] + a.offset[0], p[1] + a.offset[1]], WANDER_SPEED * dt, () => {
          t.loopIndex = (t.loopIndex + 1) % loop.length;
        });
        t.rig.setPose("wander", time);
      } else {
        t.rig.setPose(a.pose === "wander" ? "standing-wave" : a.pose, time);
      }
      const seatedLift = !t.route.length && a.pose === "seated-typing" ? a.zone.position[1] : 0;
      t.rig.group.position.set(t.pos.x, seatedLift, t.pos.z);
      const current = t.rig.group.rotation.y;
      const delta = ((t.yaw - current + Math.PI * 3) % (Math.PI * 2)) - Math.PI;
      t.rig.group.rotation.y = current + delta * Math.min(1, dt * 10);
      t.blob.position.set(t.pos.x, 0.03, t.pos.z);
      t.ring.position.set(t.pos.x, 0.05, t.pos.z);
      const urgent = t.agent.status === "issue" || t.agent.status === "review";
      const pulse = urgent ? 1 + Math.sin(time * 4) * 0.12 : 1;
      t.ring.scale.setScalar(pulse * (this.selectedId === t.agent.id ? 1.3 : 1));
      (t.ring.material as THREE.MeshBasicMaterial).opacity = urgent ? 0.75 + Math.sin(time * 4) * 0.25 : 0.65;
    }
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

  /** Point above the head for the status badge. */
  badgeAnchor(id: string): Vec3 | null {
    const t = this.tracked.get(id);
    if (!t) return null;
    const lift = t.agent.status === "issue" ? 3.35 : 2.05; // clear the "!" beacon
    return [t.rig.group.position.x, t.rig.group.position.y + lift, t.rig.group.position.z];
  }

  isTravelling(id: string) {
    return (this.tracked.get(id)?.route.length ?? 0) > 0;
  }

  pick(raycaster: THREE.Raycaster): string | null {
    const hits = raycaster.intersectObjects([...this.tracked.values()].map((t) => t.rig.group), true);
    for (const hit of hits) {
      let o: THREE.Object3D | null = hit.object;
      while (o && o.userData.agentId === undefined) o = o.parent;
      if (o) return o.userData.agentId as string;
    }
    return null;
  }

  dispose() {
    for (const t of this.tracked.values()) t.rig.dispose();
    this.tracked.clear();
    this.group.removeFromParent();
  }
}
