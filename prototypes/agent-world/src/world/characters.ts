import * as THREE from "three/webgpu";
import { saturation, vertexColor } from "three/tsl";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import type { Agent } from "../app/types";
import type { Action, Role } from "../live/types";

/** Body placement: walking, sitting on a seat, or standing still. */
export type Stance = "walk" | "seated" | "standing";

/**
 * What the upper body does: the current action, the role's idle
 * personality, the attention alert, a wave (at the review board or a
 * coordinator), or nothing (walking).
 */
export type Gesture = "action" | "idle" | "alert" | "wave" | "none";

export interface PoseState {
  stance: Stance;
  gesture: Gesture;
  action: Action;
  /** Yaw towards the nearest entrance relative to the body, for the spawn gesture. */
  doorBearing: number;
  /** Simpler idle motion (lower quality tiers). */
  calm: boolean;
}

export interface CharacterRig {
  group: THREE.Group;
  role: Role | null;
  setPose(state: PoseState, time: number): void;
  /** Extras only need walking. */
  setWalk(time: number): void;
  setAlert(on: boolean): void;
  setDimmed(on: boolean): void;
  dispose(): void;
}

const geometries = new Map<string, THREE.BufferGeometry>();
const materials = new Map<string, THREE.MeshStandardMaterial>();

const geoKey = (w: number, h: number, d: number) => `${w}|${h}|${d}`;

function geo(w: number, h: number, d: number) {
  const key = geoKey(w, h, d);
  if (!geometries.has(key)) {
    const g = new RoundedBoxGeometry(w, h, d, 2, Math.min(0.06, w / 4, h / 4, d / 4));
    g.translate(0, h / 2, 0);
    geometries.set(key, g);
  }
  return geometries.get(key)!;
}

const grey = new THREE.Color();

/** Shared materials, one per colour; `dim` gives the desaturated twin used for quiet agents. */
function mat(color: string, emissive?: string, dim = false) {
  const key = `${color}|${emissive ?? ""}|${dim ? "dim" : ""}`;
  if (!materials.has(key)) {
    const m = new THREE.MeshStandardMaterial({ color, roughness: 0.8, flatShading: true });
    if (emissive) {
      m.emissive.set(emissive);
      m.emissiveIntensity = dim ? 0.15 : 0.9;
    }
    if (dim) {
      const c = m.color;
      const luma = c.r * 0.3 + c.g * 0.59 + c.b * 0.11;
      grey.setRGB(luma, luma, luma);
      c.lerp(grey, 0.75).multiplyScalar(0.8);
    }
    materials.set(key, m);
  }
  return materials.get(key)!;
}

/**
 * One box of the figure. Only the big blocks cast shadows (`caster`): the
 * shadow pass then draws two meshes per character instead of every part,
 * which keeps a crowd within the frame budget on real-time lighting.
 */
function part(parent: THREE.Object3D, w: number, h: number, d: number, color: string, x: number, y: number, z: number, emissive?: string, caster = false) {
  const mesh = new THREE.Mesh(geo(w, h, d), mat(color, emissive));
  mesh.userData.geo = geoKey(w, h, d);
  mesh.userData.colour = color;
  mesh.userData.emissive = emissive;
  mesh.position.set(x, y, z);
  mesh.castShadow = caster;
  mesh.receiveShadow = true;
  parent.add(mesh);
  return mesh;
}

// The "!" beacon: saturated red, lightly emissive so bloom keeps its colour,
// and drawn through railings and walls so the status stays visible.
const beaconMaterial = new THREE.MeshStandardMaterial({ color: "#e8322f", emissive: "#c81e1e", emissiveIntensity: 0.9, flatShading: true });
beaconMaterial.depthTest = false;

// Baked parts share two vertex-coloured materials: normal, and desaturated for quiet agents.
const bakedMaterial = new THREE.MeshStandardMaterial({ roughness: 0.8, flatShading: true, vertexColors: true });
const bakedDimMaterial = new THREE.MeshStandardNodeMaterial({ roughness: 0.8, flatShading: true });
bakedDimMaterial.colorNode = saturation(vertexColor(), 0.25).mul(0.8);
const bakedGeometries = new Map<string, THREE.BufferGeometry>();

/**
 * Merges the plain (non-emissive) parts under each group into one
 * vertex-coloured mesh, so a character draws as about ten meshes instead of
 * thirty. Merged geometry is cached by its parts, so identical heads, props
 * and outfits share one geometry across characters.
 */
function bake(root: THREE.Object3D) {
  const parents: THREE.Object3D[] = [];
  root.traverse((o) => parents.push(o));
  for (const parent of parents) {
    const parts = parent.children.filter(
      (c): c is THREE.Mesh => (c as THREE.Mesh).isMesh && !!c.userData.colour && !c.userData.emissive,
    );
    if (parts.length < 2) continue;
    for (const p of parts) p.updateMatrix();
    const key = parts.map((p) => `${p.userData.geo}|${p.userData.colour}|${p.matrix.elements.map((e) => e.toFixed(4)).join(",")}`).join(";");
    let geometry = bakedGeometries.get(key);
    if (!geometry) {
      const pieces = parts.map((p) => {
        const g = p.geometry.clone().applyMatrix4(p.matrix);
        const c = new THREE.Color(p.userData.colour);
        const colours = new Float32Array(g.attributes.position.count * 3);
        for (let i = 0; i < colours.length; i += 3) colours.set([c.r, c.g, c.b], i);
        g.setAttribute("color", new THREE.BufferAttribute(colours, 3));
        return g;
      });
      geometry = mergeGeometries(pieces)!;
      for (const g of pieces) g.dispose();
      bakedGeometries.set(key, geometry);
    }
    const mesh = new THREE.Mesh(geometry, bakedMaterial);
    mesh.castShadow = parts.some((p) => p.castShadow);
    mesh.receiveShadow = true;
    mesh.userData.baked = true;
    for (const p of parts) parent.remove(p);
    parent.add(mesh);
  }
}

/** A pivot at the top of a limb so it swings from the shoulder or hip. */
function limb(parent: THREE.Object3D, w: number, h: number, d: number, color: string, x: number, y: number, z: number) {
  const pivot = new THREE.Group();
  pivot.position.set(x, y + h, z);
  part(pivot, w, h, d, color, 0, -h, 0);
  parent.add(pivot);
  return pivot;
}

function holder(parent: THREE.Object3D, x: number, y: number, z: number) {
  const g = new THREE.Group();
  g.position.set(x, y, z);
  g.visible = false;
  parent.add(g);
  return g;
}

// Accessory colours per role, kept constant so each role reads at a glance.
const WAISTCOAT = "#3a3350";
const CARDIGAN = "#4f7a86";
const BERET = "#8b1e3f";
const SCARF = "#d1495b";
const HOODIE_POCKET = "#2c3a4a";
const CAP = "#2e86de";
const FRAME = "#262b38";
const PAPER = "#f4efe2";
const INK = "#1d2433";

type Prop = "laptop" | "notepad" | "page" | "book" | "tablet" | "clipboard";

/** The role's own item (shown while idle). */
const ROLE_PROP: Record<Role, Prop | null> = {
  coordinator: "clipboard",
  implementer: "laptop",
  reviewer: null,
  documenter: "notepad",
  researcher: "book",
  tester: "tablet",
};

/** Deterministic 0..1 phase from an id, so a crowd does not move in lockstep. */
export function phaseOf(id: string): number {
  let h = 2166136261;
  for (let i = 0; i < id.length; i++) h = Math.imul(h ^ id.charCodeAt(i), 16777619);
  return ((h >>> 0) % 1000) / 1000;
}

/**
 * A chibi figure (style C): big bevelled head, stubby rigid limbs. Agents
 * wear their role's look (waistcoat, hoodie, glasses and cardigan, beret,
 * scarf, cap) and carry procedural props (laptop, pen and paper, page, book,
 * tablet, clipboard) that are toggled per action. Parts are merged per
 * limb (see `bake`), and geometry and materials are shared across
 * characters. Extras are smaller and muted so they never read as agents.
 */
export function createCharacter(look: Agent["look"], kind: "agent" | "extra" = "agent", role: Role | null = null, seed = 0): CharacterRig {
  const group = new THREE.Group();
  const body = new THREE.Group();
  group.add(body);
  const pants = kind === "agent" ? "#2b3448" : "#56607a";
  const legL = limb(body, 0.2, 0.36, 0.22, pants, -0.12, 0, 0);
  const legR = limb(body, 0.2, 0.36, 0.22, pants, 0.12, 0, 0);
  part(body, 0.5, 0.5, 0.34, look.shirt, 0, 0.36, 0, undefined, true);
  part(body, 0.52, 0.08, 0.36, look.accent, 0, 0.36, 0); // belt line
  const armL = limb(body, 0.14, 0.42, 0.16, look.shirt, -0.33, 0.4, 0);
  const armR = limb(body, 0.14, 0.42, 0.16, look.shirt, 0.33, 0.4, 0);
  const head = new THREE.Group();
  head.position.set(0, 0.86, 0);
  body.add(head);
  part(head, 0.72, 0.66, 0.66, look.skin, 0, 0, 0, undefined, true);
  part(head, 0.76, 0.22, 0.7, look.hair, 0, 0.56, -0.02);
  part(head, 0.76, 0.34, 0.16, look.hair, 0, 0.3, -0.29);
  if (role === "reviewer") {
    // Glasses replace the plain eyes: frame, lens, pupil, and a bridge.
    for (const x of [-0.15, 0.15]) {
      part(head, 0.24, 0.2, 0.03, FRAME, x, 0.17, 0.33);
      part(head, 0.18, 0.14, 0.02, "#dcecf5", x, 0.2, 0.355);
      part(head, 0.08, 0.1, 0.02, INK, x, 0.22, 0.37);
    }
    part(head, 0.08, 0.04, 0.03, FRAME, 0, 0.26, 0.33);
  } else {
    part(head, 0.1, 0.12, 0.02, INK, -0.15, 0.26, 0.335);
    part(head, 0.1, 0.12, 0.02, INK, 0.15, 0.26, 0.335);
  }
  part(head, 0.12, 0.05, 0.02, "#e58f84", -0.24, 0.16, 0.335);
  part(head, 0.12, 0.05, 0.02, "#e58f84", 0.24, 0.16, 0.335);
  if (kind === "extra") {
    part(head, 0.8, 0.12, 0.8, look.accent, 0, 0.66, 0.02);
    part(head, 0.5, 0.06, 0.3, look.accent, 0, 0.66, 0.5);
    group.scale.setScalar(0.75);
  }

  // Role looks.
  switch (role) {
    case "coordinator": // waistcoat with a V opening
      part(body, 0.2, 0.44, 0.06, WAISTCOAT, -0.14, 0.42, 0.15);
      part(body, 0.2, 0.44, 0.06, WAISTCOAT, 0.14, 0.42, 0.15);
      part(body, 0.05, 0.05, 0.03, "#d8c27a", 0.1, 0.6, 0.19);
      break;
    case "implementer": // hoodie: hood around the back of the neck, drawstrings, front pocket
      part(body, 0.62, 0.3, 0.2, look.shirt, 0, 0.78, -0.22);
      part(body, 0.1, 0.3, 0.36, look.shirt, -0.33, 0.78, -0.08);
      part(body, 0.1, 0.3, 0.36, look.shirt, 0.33, 0.78, -0.08);
      part(body, 0.04, 0.2, 0.03, "#f4f1ea", -0.08, 0.62, 0.17);
      part(body, 0.04, 0.2, 0.03, "#f4f1ea", 0.08, 0.62, 0.17);
      part(body, 0.34, 0.14, 0.04, HOODIE_POCKET, 0, 0.45, 0.165);
      break;
    case "reviewer": // cardigan panels over the shirt
      part(body, 0.17, 0.5, 0.05, CARDIGAN, -0.17, 0.37, 0.155);
      part(body, 0.17, 0.5, 0.05, CARDIGAN, 0.17, 0.37, 0.155);
      break;
    case "documenter": { // beret, tilted
      const beret = part(head, 0.72, 0.1, 0.68, BERET, 0.05, 0.7, 0);
      beret.rotation.z = -0.18;
      part(head, 0.06, 0.08, 0.06, BERET, 0.08, 0.79, 0);
      break;
    }
    case "researcher": // scarf and its tail
      // Chunky, wider than the head so it shows from above; the tail hangs over the shoulder.
      part(body, 0.84, 0.16, 0.5, SCARF, 0, 0.72, 0);
      part(body, 0.14, 0.4, 0.07, SCARF, 0.3, 0.36, 0.2);
      part(body, 0.14, 0.04, 0.075, "#f2d0a4", 0.3, 0.44, 0.2);
      break;
    case "tester": // cap with a forward brim
      part(head, 0.8, 0.2, 0.74, CAP, 0, 0.64, -0.01);
      part(head, 0.56, 0.05, 0.32, CAP, 0, 0.64, 0.48);
      part(head, 0.12, 0.04, 0.12, "#f4f1ea", 0, 0.84, 0);
      break;
  }

  // Props, all built once and toggled. They sit a little closer to the body
  // when standing, so they stay clear of a neighbour in a standing crowd.
  const kit = new THREE.Group();
  body.add(kit);
  const props: Partial<Record<Prop, THREE.Group>> = {};
  let pen: THREE.Group | null = null;
  let flip: THREE.Group | null = null;
  if (kind === "agent") {
    const laptop = holder(kit, 0, 0.62, 0.42);
    part(laptop, 0.5, 0.04, 0.32, "#4a505e", 0, 0, 0);
    const lid = new THREE.Group();
    lid.position.set(0, 0.03, 0.15);
    lid.rotation.x = 0.28;
    part(lid, 0.5, 0.32, 0.03, "#4a505e", 0, 0, 0);
    part(lid, 0.44, 0.26, 0.01, "#9fd6ff", 0, 0.03, -0.02, "#6fb8ff");
    laptop.add(lid);
    props.laptop = laptop;

    const notepad = holder(kit, -0.04, 0.62, 0.4);
    part(notepad, 0.36, 0.03, 0.28, "#5b4636", 0, 0, 0);
    part(notepad, 0.32, 0.01, 0.24, PAPER, 0, 0.03, 0);
    part(notepad, 0.22, 0.012, 0.015, "#b9b2a2", 0, 0.035, 0.05);
    part(notepad, 0.22, 0.012, 0.015, "#b9b2a2", 0, 0.035, -0.02);
    props.notepad = notepad;
    pen = holder(armR, 0, -0.44, 0.06);
    part(pen, 0.04, 0.2, 0.04, INK, 0, -0.06, 0);

    const page = holder(kit, 0, 0.72, 0.42);
    page.rotation.x = -0.45;
    part(page, 0.28, 0.36, 0.015, PAPER, 0, 0, 0);
    part(page, 0.2, 0.02, 0.01, "#b9b2a2", 0, 0.26, 0.012);
    part(page, 0.2, 0.02, 0.01, "#b9b2a2", 0, 0.2, 0.012);
    props.page = page;

    const book = holder(kit, 0, 0.68, 0.4);
    book.rotation.x = -0.55;
    const coverL = part(book, 0.2, 0.03, 0.28, "#2f6f5e", -0.1, 0, 0);
    coverL.rotation.z = 0.2;
    const coverR = part(book, 0.2, 0.03, 0.28, "#2f6f5e", 0.1, 0, 0);
    coverR.rotation.z = -0.2;
    part(book, 0.17, 0.04, 0.25, PAPER, -0.09, 0.03, 0).rotation.z = 0.2;
    part(book, 0.17, 0.04, 0.25, PAPER, 0.09, 0.03, 0).rotation.z = -0.2;
    flip = new THREE.Group();
    flip.position.set(0, 0.07, 0);
    part(flip, 0.17, 0.01, 0.24, "#fffaf0", 0.085, 0, 0);
    book.add(flip);
    props.book = book;

    const tablet = holder(kit, 0, 0.7, 0.4);
    tablet.rotation.x = -0.95;
    part(tablet, 0.3, 0.03, 0.4, "#2b3040", 0, 0, 0);
    part(tablet, 0.26, 0.01, 0.34, "#163a2c", 0, 0.03, 0, "#3ddc84");
    props.tablet = tablet;

    const clipboard = holder(kit, -0.14, 0.6, 0.34);
    clipboard.rotation.set(-1.1, 0.25, 0);
    part(clipboard, 0.3, 0.025, 0.4, "#a0703c", 0, 0, 0);
    part(clipboard, 0.25, 0.01, 0.3, PAPER, 0, 0.025, -0.02);
    part(clipboard, 0.12, 0.035, 0.05, "#c0c4cc", 0, 0.025, 0.17);
    props.clipboard = clipboard;
  }

  // A floating "!" beacon for agents that need attention.
  const marker = new THREE.Group();
  const bar = new THREE.Mesh(geo(0.24, 0.8, 0.24), beaconMaterial);
  bar.position.y = 0.36;
  const dot = new THREE.Mesh(geo(0.24, 0.24, 0.24), beaconMaterial);
  for (const m of [bar, dot]) m.renderOrder = 10;
  marker.add(bar, dot);
  marker.position.set(0, 2.0, 0);
  marker.visible = false;
  group.add(marker);

  bake(group);
  group.traverse((o) => (o.userData.characterRoot = group));
  const tinted: THREE.Mesh[] = [];
  group.traverse((o) => {
    if ((o as THREE.Mesh).isMesh && (o.userData.colour || o.userData.baked)) tinted.push(o as THREE.Mesh);
  });

  let shown: Prop | null = null;
  const show = (prop: Prop | null, withPen: boolean) => {
    if (prop !== shown) {
      if (shown) props[shown]!.visible = false;
      if (prop && props[prop]) props[prop]!.visible = true;
      shown = prop && props[prop] ? prop : null;
    }
    if (pen) pen.visible = withPen;
  };

  const reset = () => {
    body.position.y = 0;
    body.rotation.set(0, 0, 0);
    head.rotation.set(0, 0, 0);
    legL.rotation.set(0, 0, 0);
    legR.rotation.set(0, 0, 0);
    armL.rotation.set(0, 0, 0);
    armR.rotation.set(0, 0, 0);
  };

  const walk = (t: number) => {
    const s = Math.sin(t * 8);
    legL.rotation.x = s * 0.6;
    legR.rotation.x = -s * 0.6;
    armL.rotation.x = -s * 0.5;
    armR.rotation.x = s * 0.5;
    body.position.y = Math.abs(Math.cos(t * 8)) * 0.04;
  };

  /** Both hands on a keyboard in front; `speed` sets the typing pace. */
  const type = (t: number, speed: number) => {
    armL.rotation.x = -1.15 + Math.sin(t * speed) * 0.08;
    armR.rotation.x = -1.15 + Math.cos(t * speed * 0.93) * 0.08;
    armL.rotation.z = 0.12;
    armR.rotation.z = -0.12;
  };

  /** Both hands forward to hold something at chest height. */
  const hold = (lift = 0) => {
    armL.rotation.x = armR.rotation.x = -1.25 - lift;
    armL.rotation.z = 0.32;
    armR.rotation.z = -0.32;
  };

  const crossArms = () => {
    armL.rotation.set(-1.35, 0, 0.75);
    armR.rotation.set(-1.25, 0, -0.75);
  };

  const handOnChin = (t: number) => {
    armR.rotation.set(-2.05, 0, -0.42);
    armL.rotation.set(-1.0, 0, 0.55);
    head.rotation.x = 0.08;
    head.rotation.z = 0.1 + Math.sin(t * 0.6) * 0.04;
  };

  const action = (a: Action, t: number, doorBearing: number) => {
    switch (a) {
      case "edit-code":
      case "other":
        type(t, a === "other" ? 9 : 14);
        head.rotation.x = 0.14 + Math.sin(t * 0.7) * 0.03;
        return show("laptop", false);
      case "web":
        type(t, 7);
        head.rotation.z = Math.sin(t * 0.9) * 0.16;
        head.rotation.x = 0.06;
        return show("laptop", false);
      case "edit-docs":
        armL.rotation.set(-1.0, 0, 0.35);
        armR.rotation.set(-1.05 + Math.sin(t * 9) * 0.06, Math.sin(t * 4.5) * 0.15, -0.28);
        head.rotation.x = 0.3;
        return show("notepad", true);
      case "read":
        hold(0.45);
        head.rotation.x = 0.12 + Math.sin(t * 0.4) * 0.04;
        body.rotation.z = Math.sin(t * 0.5) * 0.02;
        return show("page", false);
      case "search": {
        hold(0.15);
        head.rotation.y = Math.sin(t * 1.3) * 0.12;
        head.rotation.x = 0.22;
        if (flip) flip.rotation.z = flipAngle(t * 1.6);
        return show("book", false);
      }
      case "run-tests":
      case "run-command":
        hold(0.25);
        armR.rotation.x += Math.max(0, Math.sin(t * 3)) * 0.08; // slow taps
        head.rotation.x = 0.28;
        return show("tablet", false);
      case "spawn": {
        // Gesture towards the door on that side, head turned to look at it.
        const bearing = Math.max(-1.3, Math.min(1.3, doorBearing));
        const arm = bearing >= 0 ? armR : armL; // armR is on the body's +x side
        const side = bearing >= 0 ? 1 : -1;
        arm.rotation.set(-1.3 + Math.sin(t * 3) * 0.1, 0, side * (0.7 + Math.abs(bearing) * 0.4));
        head.rotation.y = bearing * 0.8;
        return show(null, false);
      }
      case "thinking":
        handOnChin(t);
        return show(null, false);
    }
  };

  const idle = (r: Role | null, t: number, calm: boolean) => {
    const prop = r ? ROLE_PROP[r] : null;
    // Calm (lower tiers): a slow look around, the role's item kept in view.
    if (calm) {
      head.rotation.y = Math.sin(t * 0.4) * 0.25;
      if (prop === "laptop") type(t, 3);
      else if (prop) hold(0.1);
      return show(prop, prop === "notepad");
    }
    // A repeating 8-second loop with a short "moment" so the idle reads.
    const cycle = (t / 8) % 1;
    const moment = cycle > 0.62 && cycle < 0.85 ? Math.sin(((cycle - 0.62) / 0.23) * Math.PI) : 0;
    switch (r) {
      case "coordinator":
        head.rotation.y = Math.sin(t * 0.7) * 0.45;
        armL.rotation.set(-1.0, 0, 0.5); // clipboard at the chest
        armR.rotation.set(-2.4 * moment, 0, -0.15 * moment); // points at the board now and then
        if (moment > 0) head.rotation.y = 0.2;
        return show("clipboard", false);
      case "implementer":
        type(t, 3);
        if (moment > 0) {
          // A V-shaped stretch, arms up and out so it shows beside the big head.
          armL.rotation.set(-2.7 * moment, 0, -0.55 * moment);
          armR.rotation.set(-2.7 * moment, 0, 0.55 * moment);
          head.rotation.x = -0.25 * moment;
          body.rotation.x = -0.05 * moment;
        }
        return show("laptop", false);
      case "reviewer":
        crossArms();
        head.rotation.x = 0.06 + Math.max(0, Math.sin(t * 1.1)) * 0.16; // slow nods
        return show(null, false);
      case "documenter":
        armL.rotation.set(-1.0, 0, 0.35);
        armR.rotation.set(-1.0 - (cycle < 0.5 ? Math.abs(Math.sin(t * 6)) * 0.12 : 0), 0, -0.28); // taps the pen
        head.rotation.x = 0.2;
        head.rotation.y = Math.sin(t * 0.5) * 0.2;
        return show("notepad", true);
      case "researcher":
        hold(0.15);
        head.rotation.x = 0.2;
        if (flip) flip.rotation.z = flipAngle(t * 0.5);
        return show("book", false);
      case "tester": // the foot tap is added by setPose, which knows the stance
        hold(0.2);
        head.rotation.x = 0.22;
        return show("tablet", false);
      default:
        head.rotation.y = Math.sin(t * 0.5) * 0.3;
        return show(prop, false);
    }
  };

  return {
    group,
    role,
    setPose(state, time) {
      const t = time + seed * 10;
      reset();
      if (state.stance === "walk") {
        walk(t);
        show(null, false);
        return;
      }
      kit.position.z = state.stance === "standing" ? -0.1 : 0;
      if (state.stance === "seated") {
        body.position.y = 0.07;
        legL.rotation.x = legR.rotation.x = -1.45;
      }
      switch (state.gesture) {
        case "action":
          action(state.action, t, state.doorBearing);
          break;
        case "idle":
          idle(role, t, state.calm);
          // Taps a foot: the leg's resting angle plus a small bob.
          if (role === "tester" && !state.calm) {
            const tap = Math.max(0, Math.sin(t * 7)) * 0.2;
            legR.rotation.x += state.stance === "seated" ? tap : -tap;
          }
          break;
        case "wave":
          armR.rotation.x = -2.7 + Math.sin(t * 3.2) * 0.18;
          armR.rotation.z = -0.25;
          head.rotation.y = Math.sin(t * 0.9) * 0.25;
          show(null, false);
          break;
        case "alert":
          armL.rotation.z = 0.35;
          armR.rotation.z = -0.35;
          head.rotation.z = Math.sin(t * 2.4) * 0.08;
          marker.position.y = 2.05 + Math.sin(t * 4) * 0.1;
          marker.rotation.y = t * 1.2;
          marker.scale.setScalar(1 + Math.sin(t * 6) * 0.08);
          show(null, false);
          break;
        case "none":
          show(null, false);
          break;
      }
    },
    setWalk(time) {
      reset();
      walk(time);
    },
    setAlert(on) {
      marker.visible = on;
    },
    setDimmed(on) {
      for (const m of tinted)
        m.material = m.userData.baked ? (on ? bakedDimMaterial : bakedMaterial) : mat(m.userData.colour, m.userData.emissive, on);
    },
    dispose() {
      group.removeFromParent();
    },
  };
}

/** A page turning over and over: lies right, lifts over the spine, lies left, then snaps back. */
function flipAngle(t: number) {
  const c = t % 1;
  return c < 0.6 ? 0 : Math.min(1, (c - 0.6) / 0.3) * Math.PI;
}
