import { describe, expect, it } from "vitest";
import * as THREE from "three";
import { collectDisposables } from "../../src/world/dispose";

describe("collectDisposables", () => {
  it("finds every texture slot, material and geometry under a root", () => {
    const map = new THREE.Texture(), emissive = new THREE.Texture(), light = new THREE.Texture();
    const source = new THREE.MeshStandardMaterial({ map, emissiveMap: emissive });
    const replacement = new THREE.MeshBasicMaterial({ lightMap: light });
    const root = new THREE.Group();
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(), replacement);
    const instanced = new THREE.InstancedMesh(new THREE.BoxGeometry(), replacement, 2);
    root.add(mesh, instanced);
    const found = collectDisposables(root, [source]);
    expect(found.textures).toEqual(new Set([map, emissive, light]));
    expect(found.materials).toEqual(new Set([source, replacement]));
    expect(found.geometries.size).toBe(2);
    expect(found.instanced).toEqual([instanced]);
  });
});
