import * as THREE from "three/webgpu";
import { cos, float, instanceIndex, positionLocal, sin, time, vec3 } from "three/tsl";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import type { EnvironmentManifest } from "../contract/manifest";
import { validateManifest } from "../contract/validate";
import { parseWalkable } from "../contract/grid";
import type { WalkGrid } from "./pathfinding";

export interface LoadedEnvironment {
  manifest: EnvironmentManifest;
  root: THREE.Object3D;
  walk: WalkGrid;
  dispose(): void;
}

export class EnvironmentLoadError extends Error {}

const draco = new DRACOLoader().setDecoderPath(`${import.meta.env.BASE_URL}draco/`);
const loader = new GLTFLoader().setDRACOLoader(draco);

/** Foliage materials sway gently; each instance gets its own phase. */
function swayingMaterial(source: THREE.MeshStandardMaterial): THREE.MeshStandardNodeMaterial {
  const m = new THREE.MeshStandardNodeMaterial();
  m.color.copy(source.color);
  m.roughness = source.roughness;
  m.metalness = source.metalness;
  m.map = source.map;
  m.flatShading = true;
  m.name = source.name;
  m.positionNode = swayNode();
  return m;
}

/** Height-weighted sway; the phase varies per instance and by position. */
function swayNode() {
  const phase = float(instanceIndex).mul(1.73).add(positionLocal.x.mul(0.6)).add(positionLocal.z.mul(0.4));
  const height = positionLocal.y.max(0).min(4);
  return positionLocal.add(
    vec3(sin(time.mul(1.4).add(phase)).mul(0.03), 0, cos(time.mul(1.1).add(phase)).mul(0.022)).mul(height),
  );
}

/**
 * Lightmapped surfaces (`*_lm`): the palette colour times a baked irradiance
 * map carried in the emissive slot. The bake stores light at reduced energy
 * for 8-bit headroom; `tafwid_lightmap_scale` restores it. Three's basic
 * lighting divides light maps by π, so the intensity multiplies π back.
 */
function lightmappedMaterial(source: THREE.MeshStandardMaterial): THREE.MeshBasicNodeMaterial {
  const m = new THREE.MeshBasicNodeMaterial({ color: source.color });
  m.lightMap = source.emissiveMap;
  m.lightMapIntensity = Number(source.userData.tafwid_lightmap_scale ?? 2) * Math.PI;
  m.name = source.name;
  if (source.name.includes("leaf_")) m.positionNode = swayNode();
  return m;
}

/** Baked surfaces already contain their lighting, so they render unlit. */
function bakedMaterial(source: THREE.MeshStandardMaterial): THREE.MeshBasicNodeMaterial {
  const m = new THREE.MeshBasicNodeMaterial({ map: source.map, color: source.map ? 0xffffff : source.color });
  m.name = source.name;
  return m;
}

/**
 * Collapses meshes that share geometry and material into one InstancedMesh.
 * GLTFLoader reuses a geometry for every node that references the same glTF
 * mesh, so a kit of repeated pieces becomes a few hundred draw calls.
 */
function instanceRepeats(root: THREE.Object3D) {
  const groups = new Map<string, THREE.Mesh[]>();
  root.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (!mesh.isMesh || (mesh as THREE.InstancedMesh).isInstancedMesh || Array.isArray(mesh.material)) return;
    const key = `${mesh.geometry.uuid}|${(mesh.material as THREE.Material).uuid}`;
    const list = groups.get(key);
    if (list) list.push(mesh);
    else groups.set(key, [mesh]);
  });
  const inverseRoot = root.matrixWorld.clone().invert();
  const m = new THREE.Matrix4();
  for (const meshes of groups.values()) {
    if (meshes.length < 2) continue;
    const first = meshes[0];
    const instanced = new THREE.InstancedMesh(first.geometry, first.material, meshes.length);
    meshes.forEach((mesh, i) => instanced.setMatrixAt(i, m.multiplyMatrices(inverseRoot, mesh.matrixWorld)));
    instanced.instanceMatrix.needsUpdate = true;
    instanced.castShadow = first.castShadow;
    instanced.receiveShadow = first.receiveShadow;
    instanced.computeBoundingSphere();
    root.add(instanced);
    for (const mesh of meshes) mesh.removeFromParent();
  }
}

export async function loadEnvironment(baseUrl: string): Promise<LoadedEnvironment> {
  const response = await fetch(`${baseUrl}/manifest.json`);
  if (!response.ok) throw new EnvironmentLoadError(`Could not load ${baseUrl}/manifest.json (${response.status})`);
  const result = validateManifest(await response.json());
  if (!result.ok) throw new EnvironmentLoadError(`Invalid environment package: ${result.errors.join("; ")}`);
  const manifest = result.manifest;
  let gltf;
  try {
    gltf = await loader.loadAsync(`${baseUrl}/${manifest.scene}`);
  } catch (e) {
    throw new EnvironmentLoadError(`Could not load the scene for ${manifest.name}: ${(e as Error).message}`);
  }
  const root = gltf.scene;
  const realtime = manifest.lighting === "realtime";
  const replaced = new Map<THREE.Material, THREE.Material>();
  root.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (!mesh.isMesh) return;
    const source = mesh.material as THREE.MeshStandardMaterial;
    let next = replaced.get(source);
    if (!next) {
      if (source.name.endsWith("_lm")) next = lightmappedMaterial(source);
      else if (source.name.endsWith("_baked")) next = bakedMaterial(source);
      else if (source.name.startsWith("leaf")) next = swayingMaterial(source);
      else {
        source.flatShading = true;
        next = source;
      }
      replaced.set(source, next);
    }
    mesh.material = next;
    const emissive = !source.name.endsWith("_lm") && source.emissiveIntensity > 0 && source.emissive?.getHex() !== 0;
    mesh.castShadow = realtime && !emissive;
    mesh.receiveShadow = realtime;
  });
  root.updateMatrixWorld(true);
  instanceRepeats(root);

  return {
    manifest,
    root,
    walk: parseWalkable(manifest.grid),
    dispose() {
      root.traverse((obj) => {
        const mesh = obj as THREE.Mesh;
        if (!mesh.isMesh) return;
        mesh.geometry.dispose();
      });
      for (const [src, mat] of replaced) {
        (src as THREE.MeshStandardMaterial).map?.dispose();
        src.dispose();
        mat.dispose();
      }
      root.removeFromParent();
    },
  };
}
