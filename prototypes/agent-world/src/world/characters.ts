import * as THREE from "three/webgpu";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import type { Agent } from "../app/types";
import type { Pose } from "../app/behaviour";

export type CharacterPose = Pose | "walk";

export interface CharacterRig {
  group: THREE.Group;
  setPose(pose: CharacterPose, time: number): void;
  setAlert(on: boolean): void;
  dispose(): void;
}

const geometries = new Map<string, THREE.BufferGeometry>();
const materials = new Map<string, THREE.MeshStandardMaterial>();

function geo(w: number, h: number, d: number) {
  const key = `${w}|${h}|${d}`;
  if (!geometries.has(key)) {
    const g = new RoundedBoxGeometry(w, h, d, 2, Math.min(0.06, w / 4, h / 4, d / 4));
    g.translate(0, h / 2, 0);
    geometries.set(key, g);
  }
  return geometries.get(key)!;
}

function mat(color: string, emissive?: string) {
  const key = color + (emissive ?? "");
  if (!materials.has(key)) {
    const m = new THREE.MeshStandardMaterial({ color, roughness: 0.8, flatShading: true });
    if (emissive) {
      m.emissive.set(emissive);
      m.emissiveIntensity = 0.9;
    }
    materials.set(key, m);
  }
  return materials.get(key)!;
}

function part(parent: THREE.Object3D, w: number, h: number, d: number, color: string, x: number, y: number, z: number) {
  const mesh = new THREE.Mesh(geo(w, h, d), mat(color));
  mesh.position.set(x, y, z);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  parent.add(mesh);
  return mesh;
}

/** A pivot at the top of a limb so it swings from the shoulder or hip. */
function limb(parent: THREE.Object3D, w: number, h: number, d: number, color: string, x: number, y: number, z: number) {
  const pivot = new THREE.Group();
  pivot.position.set(x, y + h, z);
  part(pivot, w, h, d, color, 0, -h, 0);
  parent.add(pivot);
  return pivot;
}

/**
 * A chibi figure (style C): big bevelled head, stubby rigid limbs. Agents
 * get role colours and a hair block; extras are smaller and muted so they
 * never read as agents.
 */
export function createCharacter(look: Agent["look"], kind: "agent" | "extra" = "agent"): CharacterRig {
  const group = new THREE.Group();
  const body = new THREE.Group();
  group.add(body);
  const pants = kind === "agent" ? "#2b3448" : "#56607a";
  const legL = limb(body, 0.2, 0.36, 0.22, pants, -0.12, 0, 0);
  const legR = limb(body, 0.2, 0.36, 0.22, pants, 0.12, 0, 0);
  part(body, 0.5, 0.5, 0.34, look.shirt, 0, 0.36, 0);
  part(body, 0.52, 0.08, 0.36, look.accent, 0, 0.36, 0); // belt line
  const armL = limb(body, 0.14, 0.42, 0.16, look.shirt, -0.33, 0.4, 0);
  const armR = limb(body, 0.14, 0.42, 0.16, look.shirt, 0.33, 0.4, 0);
  const head = new THREE.Group();
  head.position.set(0, 0.86, 0);
  body.add(head);
  part(head, 0.72, 0.66, 0.66, look.skin, 0, 0, 0);
  part(head, 0.76, 0.22, 0.7, look.hair, 0, 0.56, -0.02);
  part(head, 0.76, 0.34, 0.16, look.hair, 0, 0.3, -0.29);
  part(head, 0.1, 0.12, 0.02, "#1d2433", -0.15, 0.26, 0.335);
  part(head, 0.1, 0.12, 0.02, "#1d2433", 0.15, 0.26, 0.335);
  part(head, 0.12, 0.05, 0.02, "#e58f84", -0.24, 0.16, 0.335);
  part(head, 0.12, 0.05, 0.02, "#e58f84", 0.24, 0.16, 0.335);
  if (kind === "extra") {
    part(head, 0.8, 0.12, 0.8, look.accent, 0, 0.66, 0.02);
    part(head, 0.5, 0.06, 0.3, look.accent, 0, 0.66, 0.5);
    group.scale.setScalar(0.75);
  }

  // A floating "!" beacon for agents that need attention: saturated red, lightly emissive so bloom keeps its colour.
  const marker = new THREE.Group();
  const red = new THREE.MeshStandardMaterial({ color: "#e8322f", emissive: "#c81e1e", emissiveIntensity: 0.9, flatShading: true });
  red.depthTest = false; // a status marker stays visible through railings and walls
  const bar = new THREE.Mesh(geo(0.24, 0.8, 0.24), red);
  bar.position.y = 0.36;
  const dot = new THREE.Mesh(geo(0.24, 0.24, 0.24), red);
  for (const m of [bar, dot]) m.renderOrder = 10;
  marker.add(bar, dot);
  marker.position.set(0, 2.0, 0);
  marker.visible = false;
  group.add(marker);

  group.traverse((o) => (o.userData.characterRoot = group));

  return {
    group,
    setPose(pose, t) {
      body.position.y = 0;
      head.rotation.set(0, 0, 0);
      legL.rotation.set(0, 0, 0);
      legR.rotation.set(0, 0, 0);
      armL.rotation.set(0, 0, 0);
      armR.rotation.set(0, 0, 0);
      switch (pose) {
        case "walk":
        case "wander": {
          const s = Math.sin(t * 8);
          legL.rotation.x = s * 0.6;
          legR.rotation.x = -s * 0.6;
          armL.rotation.x = -s * 0.5;
          armR.rotation.x = s * 0.5;
          body.position.y = Math.abs(Math.cos(t * 8)) * 0.04;
          break;
        }
        case "seated-typing":
          body.position.y = 0.07;
          legL.rotation.x = legR.rotation.x = -1.45;
          armL.rotation.x = -1.15 + Math.sin(t * 14) * 0.08;
          armR.rotation.x = -1.15 + Math.cos(t * 13) * 0.08;
          head.rotation.x = 0.12 + Math.sin(t * 0.7) * 0.03;
          break;
        case "standing-wave":
          armR.rotation.x = -2.7 + Math.sin(t * 3.2) * 0.18;
          armR.rotation.z = -0.25;
          head.rotation.y = Math.sin(t * 0.9) * 0.25;
          break;
        case "standing-alert":
          armL.rotation.z = 0.35;
          armR.rotation.z = -0.35;
          head.rotation.z = Math.sin(t * 2.4) * 0.08;
          marker.position.y = 2.05 + Math.sin(t * 4) * 0.1;
          marker.rotation.y = t * 1.2;
          marker.scale.setScalar(1 + Math.sin(t * 6) * 0.08);
          break;
      }
    },
    setAlert(on) {
      marker.visible = on;
    },
    dispose() {
      group.removeFromParent();
    },
  };
}
