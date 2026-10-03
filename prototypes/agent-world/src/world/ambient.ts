import * as THREE from "three/webgpu";
import type { AmbientPath, Vec2 } from "../contract/manifest";
import { createCharacter, type CharacterRig } from "./characters";
import type { LoadedEnvironment } from "./environment";

const EXTRA_LOOKS = [
  { skin: "#e8b48f", shirt: "#8e9aaf", hair: "#4a3b33", accent: "#cbc0d3" },
  { skin: "#a7714f", shirt: "#b8a088", hair: "#2a2a2a", accent: "#dee2e6" },
  { skin: "#f3d2b8", shirt: "#7f9c96", hair: "#a0522d", accent: "#e9ecef" },
  { skin: "#6f4a35", shirt: "#c9b29b", hair: "#1b1b1b", accent: "#adb5bd" },
];

interface Walker {
  path: AmbientPath;
  progress: number; // distance travelled along the path
  speed: number;
  length: number;
  rig?: CharacterRig;
  bird?: THREE.Group;
  wings?: THREE.Mesh[];
}

function pathLength(points: Vec2[], loop: boolean) {
  let total = 0;
  const n = loop ? points.length : points.length - 1;
  for (let i = 0; i < n; i++) {
    const a = points[i], b = points[(i + 1) % points.length];
    total += Math.hypot(b[0] - a[0], b[1] - a[1]);
  }
  return total;
}

/** Position and heading at a distance along a path; open paths ping-pong. */
function sample(points: Vec2[], loop: boolean, distance: number, length: number): { p: Vec2; yaw: number } {
  let d = loop ? distance % length : length - Math.abs((distance % (2 * length)) - length);
  const reverse = !loop && distance % (2 * length) > length;
  const n = loop ? points.length : points.length - 1;
  for (let i = 0; i < n; i++) {
    const a = points[i], b = points[(i + 1) % points.length];
    const seg = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (d <= seg || i === n - 1) {
      const t = seg ? Math.min(1, d / seg) : 0;
      const yaw = Math.atan2(b[0] - a[0], b[1] - a[1]) + (reverse ? Math.PI : 0);
      return { p: [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t], yaw };
    }
    d -= seg;
  }
  return { p: points[0], yaw: 0 };
}

function makeBird(): { group: THREE.Group; wings: THREE.Mesh[] } {
  const group = new THREE.Group();
  const body = new THREE.MeshStandardMaterial({ color: "#3d3a4b", flatShading: true });
  const torso = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.12, 0.3), body);
  group.add(torso);
  const wings = [-1, 1].map((side) => {
    const w = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.03, 0.18), body);
    w.geometry.translate(side * 0.17, 0, 0);
    w.position.x = side * 0.06;
    group.add(w);
    return w;
  });
  return { group, wings };
}

/** Background life: passers-by and birds that never carry status. */
export class AmbientLayer {
  readonly group = new THREE.Group();
  private walkers: Walker[] = [];
  private enabled = true;

  constructor(scene: THREE.Scene) {
    scene.add(this.group);
  }

  setEnvironment(env: LoadedEnvironment) {
    this.clear();
    env.manifest.ambientPaths.forEach((path, i) => {
      const length = pathLength(path.points, path.loop);
      if (length <= 0) return;
      const count = path.kind === "pedestrian" ? Math.max(1, Math.round(length / 18)) : 1;
      for (let k = 0; k < count; k++) {
        const w: Walker = {
          path,
          length,
          progress: (length / count) * k + i * 3.1,
          speed: path.kind === "bird" ? 3.2 : 0.95 + ((i + k) % 3) * 0.12,
        };
        if (path.kind === "pedestrian") {
          w.rig = createCharacter(EXTRA_LOOKS[(i + k) % EXTRA_LOOKS.length], "extra");
          this.group.add(w.rig.group);
        } else {
          const bird = makeBird();
          w.bird = bird.group;
          w.wings = bird.wings;
          this.group.add(bird.group);
        }
        this.walkers.push(w);
      }
    });
    this.update(0, 0);
  }

  setEnabled(on: boolean) {
    this.enabled = on;
    this.group.visible = on;
  }

  get isEnabled() {
    return this.enabled;
  }

  update(dt: number, time: number) {
    if (!this.enabled) return;
    for (const w of this.walkers) {
      w.progress += w.speed * dt;
      const { p, yaw } = sample(w.path.points, w.path.loop, w.progress, w.length);
      if (w.rig) {
        w.rig.group.position.set(p[0], 0, p[1]);
        w.rig.group.rotation.y = yaw;
        w.rig.setPose("walk", time + w.progress);
      } else if (w.bird && w.wings) {
        w.bird.position.set(p[0], 7 + Math.sin(time * 0.8 + w.progress) * 0.6, p[1]);
        w.bird.rotation.y = yaw;
        const flap = Math.sin(time * 14 + w.progress) * 0.7;
        w.wings[0].rotation.z = flap;
        w.wings[1].rotation.z = -flap;
      }
    }
  }

  private clear() {
    for (const w of this.walkers) {
      w.rig?.dispose();
      w.bird?.removeFromParent();
    }
    this.walkers = [];
  }

  dispose() {
    this.clear();
    this.group.removeFromParent();
  }
}
