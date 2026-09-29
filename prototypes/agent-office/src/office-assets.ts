import * as T from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import type { Agent } from "./model";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
export const positions: [number, number][] = [
  [-2.65, -1.05],
  [1.65, -1.05],
  [-2.65, 2.05],
  [1.65, 2.05],
];
const mat = (color: T.ColorRepresentation) =>
  new T.MeshStandardMaterial({ color, roughness: 0.88, flatShading: true });
function box(
  g: T.Group,
  x: number,
  y: number,
  z: number,
  w: number,
  h: number,
  d: number,
  color: T.ColorRepresentation,
  r = 0.035,
) {
  const m = new T.Mesh(
    r ? new RoundedBoxGeometry(w, h, d, 1, r) : new T.BoxGeometry(w, h, d),
    mat(color),
  );
  m.position.set(x, y, z);
  m.castShadow = true;
  m.receiveShadow = true;
  g.add(m);
  return m;
}
function cyl(
  g: T.Group,
  x: number,
  y: number,
  z: number,
  rt: number,
  rb: number,
  h: number,
  color: T.ColorRepresentation,
  segments = 10,
) {
  const m = new T.Mesh(new T.CylinderGeometry(rt, rb, h, segments), mat(color));
  m.position.set(x, y, z);
  m.castShadow = true;
  m.receiveShadow = true;
  g.add(m);
  return m;
}
function sphere(
  g: T.Group,
  x: number,
  y: number,
  z: number,
  r: number,
  color: T.ColorRepresentation,
) {
  const m = new T.Mesh(new T.IcosahedronGeometry(r, 1), mat(color));
  m.position.set(x, y, z);
  m.castShadow = true;
  g.add(m);
  return m;
}
function plant(g: T.Group, x: number, z: number, scale = 1) {
  const p = new T.Group();
  cyl(p, 0, 0.25, 0, 0.27, 0.2, 0.48, "#e7c9a8");
  cyl(p, 0, 0.49, 0, 0.23, 0.23, 0.02, "#685c48");
  cyl(p, 0, 0.95, 0, 0.035, 0.05, 1, "#68806a", 6);
  const leaves = [
    [0, 1.4, 0],
    [0.25, 1.1, 0.06],
    [-0.25, 0.98, 0],
    [0.04, 0.85, 0.22],
  ];
  leaves.forEach(([lx, ly, lz], i) => {
    const m = sphere(p, lx, ly, lz, 0.33, i % 2 ? "#508571" : "#72a389");
    m.scale.set(0.7, 1.5, 0.65);
    m.rotation.z = lx > 0 ? -0.5 : 0.4;
  });
  p.scale.setScalar(scale);
  p.position.set(x, 0.13, z);
  g.add(p);
}
function book(
  g: T.Group,
  x: number,
  y: number,
  z: number,
  color: string,
  rot = 0,
) {
  const b = box(g, x, y, z, 0.35, 0.065, 0.46, color, 0.01);
  b.rotation.y = rot;
}
export function createRoom(): T.Group {
  const g = new T.Group();
  box(g, 0, -0.25, 0, 12.2, 0.55, 10, "#d5d1e2", 0.16);
  box(g, 0, 0.04, 0, 12, 0.14, 9.8, "#e0d3c3", 0.07);
  for (let i = -5; i <= 5; i++)
    box(g, i, 0.116, 0, 0.012, 0.005, 9.5, "#d9d0c9", 0);
  // Tall rear wall, low return wall: an open cutaway rather than a closed box.
  box(g, 0, 1.6, -4.7, 12, 0.0 + 3.2, 0.22, "#c0b7de", 0.05);
  box(g, -5.9, 0.63, 0, 0.22, 1.25, 9.7, "#c0b7de", 0.04);
  box(g, 0, 0.28, -4.52, 11.7, 0.28, 0.12, "#f3f0f6", 0.02);
  box(g, -5.73, 0.28, 0, 0.12, 0.28, 9.4, "#f3f0f6", 0.02);
  // Window alcove with broad white mullions.
  box(g, -2.45, 1.98, -4.51, 4.25, 2.1, 0.16, "#f8f7fc", 0.07);
  box(g, -2.45, 1.98, -4.4, 3.91, 1.77, 0.055, "#95bcd4", 0.025);
  box(g, -2.45, 1.98, -4.35, 0.09, 1.85, 0.075, "#fcfaf9", 0.012);
  box(g, -2.45, 2.04, -4.34, 3.98, 0.07, 0.075, "#fcfaf9", 0.012);
  box(g, -2.45, 0.87, -4.29, 4.43, 0.12, 0.45, "#f6f4f9", 0.025);
  // Pin board and restrained abstract wall artwork.
  box(g, 1.18, 2.04, -4.49, 1.45, 1.61, 0.13, "#f4ede6", 0.025);
  box(g, 1.18, 2.04, -4.4, 1.21, 1.36, 0.02, "#b2a4d7", 0);
  const art = cyl(g, 1.18, 2.13, -4.36, 0.37, 0.37, 0.025, "#f2dac6", 24);
  art.rotation.x = Math.PI / 2;
  box(g, 1.18, 1.77, -4.34, 0.7, 0.17, 0.015, "#8181b2", 0);
  box(g, 3.48, 2.12, -4.49, 1.42, 0.88, 0.12, "#ebe6dd", 0.03);
  for (let i = 0; i < 3; i++)
    box(
      g,
      3.04 + i * 0.4,
      2.15,
      -4.39,
      0.25,
      0.34,
      0.02,
      ["#f2c889", "#aabed9", "#bbabd9"][i],
      0.005,
    );
  // Bookcase and a small break corner.
  box(g, 4.9, 0.85, -3.6, 1.25, 1.45, 0.65, "#eee9e2", 0.05);
  for (const y of [0.26, 0.87, 1.54])
    box(g, 4.9, y, -3.54, 1.25, 0.075, 0.72, "#cbbdab", 0.015);
  for (let i = 0; i < 5; i++)
    box(
      g,
      4.47 + i * 0.18,
      1.16,
      -3.52,
      0.12,
      0.48,
      0.39,
      ["#91acb6", "#d5af8d", "#afa1cd", "#718b82", "#d6c4a9"][i],
      0.01,
    );
  book(g, 4.74, 0.36, -3.52, "#b7aacd");
  book(g, 4.77, 0.43, -3.52, "#d8c0a2");
  plant(g, -5.03, -3.65, 0.9);
  plant(g, 5.08, 3.65, 0.82);
  // Soft lavender rug under workstations.
  box(g, -0.43, 0.135, 0.65, 8.76, 0.028, 6.4, "#aaa8cb", 0.15);
  // A rounded apricot bench beside the desks.
  box(g, 4.8, 0.47, 0.65, 1.22, 0.72, 2.52, "#d89e7a", 0.15);
  box(g, 5.29, 0.96, 0.65, 0.24, 0.83, 2.6, "#e9b894", 0.11);
  for (const z of [-0.2, 1.45])
    box(g, 4.8, 0.83, z, 1.03, 0.14, 0.94, "#edc7a8", 0.07);
  box(g, 4.89, 1.04, -0.22, 0.54, 0.35, 0.48, "#f1dcc6", 0.09);
  const table = cyl(g, 4.57, 0.54, 2.65, 0.45, 0.45, 0.12, "#f0e5d9", 16);
  cyl(g, 4.57, 0.3, 2.65, 0.085, 0.15, 0.5, "#bda994");
  cyl(g, 4.57, 0.69, 2.65, 0.075, 0.065, 0.17, "#7e9aa1");
  batchMaterials(g);
  return g;
}
export function createWorkstation(agent: Agent): T.Group {
  const g = new T.Group();
  const color = agent.color;
  // Broad desk, light wood supports, monitor and personal props.
  box(g, 0, 1.05, 0, 2.58, 0.15, 1.35, "#f3e7d6", 0.09);
  for (const x of [-1.03, 1.03])
    for (const z of [-0.42, 0.42])
      box(g, x, 0.54, z, 0.11, 1.0, 0.11, "#c9b7a3", 0.02);
  box(g, -0.29, 1.5, -0.28, 1.04, 0.65, 0.08, "#535771", 0.04);
  box(g, -0.29, 1.52, -0.225, 0.91, 0.5, 0.018, "#a9c4d6", 0.016);
  for (let i = 0; i < 3; i++)
    box(
      g,
      -0.44 + i * 0.06,
      1.62 - i * 0.12,
      -0.21,
      0.44 + i * 0.13,
      0.026,
      0.006,
      ["#e6eff3", "#c2dada", "#7798b4"][i],
      0,
    );
  cyl(g, -0.29, 1.23, -0.27, 0.055, 0.06, 0.26, "#81849a", 8);
  box(g, -0.29, 1.14, -0.25, 0.43, 0.035, 0.23, "#81849a", 0.01);
  box(g, -0.33, 1.15, 0.3, 0.76, 0.035, 0.26, "#c7cbd6", 0.025);
  for (let i = 0; i < 5; i++)
    box(g, -0.6 + i * 0.13, 1.171, 0.29, 0.07, 0.007, 0.17, "#eef0f4", 0);
  book(g, 0.72, 1.16, -0.3, color, 0.1);
  book(g, 0.75, 1.23, -0.31, "#f5eddf", -0.05);
  cyl(g, 0.83, 1.24, 0.3, 0.09, 0.08, 0.22, color, 10);
  // Ergonomic chair and an approachable geometric character.
  box(g, 0.25, 0.67, 1.07, 0.7, 0.16, 0.68, color, 0.1);
  box(g, 0.25, 1.06, 1.38, 0.7, 0.72, 0.14, color, 0.09);
  cyl(g, 0.25, 0.37, 1.07, 0.06, 0.09, 0.58, "#696b7b", 8);
  for (let i = 0; i < 4; i++) {
    const b = box(g, 0.25, 0.16, 1.07, 0.7, 0.07, 0.07, "#777989", 0.02);
    b.rotation.y = (i * Math.PI) / 2;
  }
  const person = new T.Group();
  person.position.set(0.25, 0, 1.0);
  box(person, 0, 0.98, 0, 0.49, 0.57, 0.36, color, 0.12);
  for (const x of [-0.15, 0.15]) {
    box(person, x, 0.57, -0.18, 0.16, 0.43, 0.19, "#5c6278", 0.05);
    box(person, x, 0.36, -0.29, 0.2, 0.13, 0.34, "#f4f0e9", 0.05);
  }
  cyl(person, 0, 1.32, 0, 0.105, 0.115, 0.17, "#e4b994");
  const skin =
    agent.id === "noor"
      ? "#b98a65"
      : agent.id === "ada"
        ? "#dca780"
        : "#edc7a5";
  box(person, 0, 1.61, 0, 0.47, 0.51, 0.42, skin, 0.12);
  box(
    person,
    0,
    1.84,
    -0.02,
    0.5,
    0.16,
    0.43,
    agent.id === "cleo"
      ? "#b88154"
      : agent.id === "noor"
        ? "#514538"
        : "#484654",
    0.07,
  );
  box(
    person,
    -0.23,
    1.72,
    -0.045,
    0.08,
    0.25,
    0.4,
    agent.id === "cleo" ? "#b88154" : "#484654",
    0.025,
  );
  // Faces look toward the open room; hands rest near the desk.
  for (const x of [-0.09, 0.09])
    sphere(person, x, 1.65, 0.212, 0.023, "#3e4050");
  box(person, 0, 1.53, 0.218, 0.08, 0.017, 0.006, "#aa7867", 0.003);
  for (const x of [-0.31, 0.31]) {
    const arm = box(person, x, 1.1, -0.05, 0.15, 0.42, 0.17, color, 0.06);
    arm.rotation.x = -0.6;
    sphere(person, x, 0.96, -0.21, 0.085, skin);
  }
  if (agent.id === "ada") {
    const hoop = new T.Mesh(
      new T.TorusGeometry(0.29, 0.035, 6, 12, Math.PI),
      mat("#41495f"),
    );
    hoop.position.set(0, 1.73, 0);
    person.add(hoop);
    for (const x of [-0.27, 0.27])
      box(person, x, 1.64, 0, 0.1, 0.22, 0.2, "#41495f", 0.04);
  }
  if (agent.id === "cleo") {
    for (const x of [-0.105, 0.105]) {
      const rim = new T.Mesh(
        new T.TorusGeometry(0.083, 0.013, 4, 12),
        mat("#786549"),
      );
      rim.position.set(x, 1.65, 0.236);
      person.add(rim);
    }
    box(person, 0, 1.66, 0.237, 0.055, 0.016, 0.015, "#786549", 0);
  }
  if (agent.id === "noor") sphere(person, 0, 1.94, -0.09, 0.15, "#514538");
  g.add(person);
  g.traverse((o) => {
    o.userData.agentId = agent.id;
  });
  const ring = new T.Mesh(
    new T.RingGeometry(1.2, 1.26, 48),
    new T.MeshBasicMaterial({
      color: "#6776cf",
      side: T.DoubleSide,
      transparent: true,
      opacity: 0.65,
    }),
  );
  ring.rotation.x = -Math.PI / 2;
  ring.position.set(0, 0.158, 0.32);
  ring.name = "selection-ring";
  g.add(ring);
  batchMaterials(g);
  return g;
}

// Group static meshes by color within each independently selectable object.
// Selection rings remain separate, so their visibility can change cheaply.
function batchMaterials(group: T.Group) {
  group.updateMatrixWorld(true);
  const inverse = group.matrixWorld.clone().invert();
  const batches = new Map<
    string,
    {
      geometries: T.BufferGeometry[];
      material: T.MeshStandardMaterial;
      agentId?: string;
    }
  >();
  const originals: T.Mesh[] = [];
  group.traverse((object) => {
    if (
      !(object instanceof T.Mesh) ||
      !(object.material instanceof T.MeshStandardMaterial)
    )
      return;
    const key = object.material.color.getHexString();
    let batch = batches.get(key);
    if (!batch) {
      batch = {
        geometries: [],
        material: object.material.clone(),
        agentId: object.userData.agentId,
      };
      batches.set(key, batch);
    }
    const geometry = object.geometry.index
      ? object.geometry.toNonIndexed()
      : object.geometry.clone();
    geometry.applyMatrix4(inverse.clone().multiply(object.matrixWorld));
    batch.geometries.push(geometry);
    originals.push(object);
  });
  originals.forEach((object) => {
    object.removeFromParent();
    object.geometry.dispose();
    (object.material as T.Material).dispose();
  });
  batches.forEach((batch) => {
    const geometry = mergeGeometries(batch.geometries);
    batch.geometries.forEach((part) => part.dispose());
    if (!geometry) {
      batch.material.dispose();
      return;
    }
    const mesh = new T.Mesh(geometry, batch.material);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    if (batch.agentId) mesh.userData.agentId = batch.agentId;
    group.add(mesh);
  });
}
