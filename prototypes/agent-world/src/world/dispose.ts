import type { BufferGeometry, InstancedMesh, Material, Mesh, Object3D, Texture } from "three";

/** Everything GPU-backed under a root (plus extra materials) that must be freed on unload. */
export function collectDisposables(root: Object3D, extraMaterials: Iterable<Material> = []) {
  const geometries = new Set<BufferGeometry>();
  const materials = new Set<Material>(extraMaterials);
  const textures = new Set<Texture>();
  const instanced: InstancedMesh[] = [];
  root.traverse((obj) => {
    const mesh = obj as Mesh;
    if (!mesh.isMesh) return;
    geometries.add(mesh.geometry);
    for (const m of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) materials.add(m);
    if ((obj as InstancedMesh).isInstancedMesh) instanced.push(obj as InstancedMesh);
  });
  for (const m of materials)
    for (const value of Object.values(m)) if ((value as Texture | null)?.isTexture) textures.add(value as Texture);
  return { geometries, materials, textures, instanced };
}

export function disposeAll(root: Object3D, extraMaterials: Iterable<Material> = []) {
  const found = collectDisposables(root, extraMaterials);
  found.textures.forEach((t) => t.dispose());
  found.materials.forEach((m) => m.dispose());
  found.geometries.forEach((g) => g.dispose());
  found.instanced.forEach((i) => i.dispose());
  root.removeFromParent();
}
