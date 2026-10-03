import {
  MANIFEST_SCHEMA,
  ZONE_MINIMUMS,
  type EnvironmentManifest,
  type Zone,
} from "./manifest";
import { parseWalkable, worldToCell } from "./grid";
import { findPath } from "../world/pathfinding";

export type ValidationResult =
  | { ok: true; manifest: EnvironmentManifest }
  | { ok: false; errors: string[] };

const isObject = (v: unknown): v is Record<string, any> =>
  typeof v === "object" && v !== null && !Array.isArray(v);
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isVec = (v: unknown, n: number) => Array.isArray(v) && v.length === n && v.every(isNum);

/**
 * Checks shape first, then the spatial rules: zone minimums, zones on
 * walkable cells, and every zone reachable from the first workstation.
 */
export function validateManifest(input: unknown): ValidationResult {
  const errors: string[] = [];
  if (!isObject(input)) return { ok: false, errors: ["manifest: expected an object"] };
  const m = input;

  if (m.schema !== MANIFEST_SCHEMA) errors.push(`schema: expected "${MANIFEST_SCHEMA}"`);
  for (const key of ["id", "name", "scene"] as const)
    if (typeof m[key] !== "string" || !m[key]) errors.push(`${key}: expected a non-empty string`);
  if (m.variant !== "kit" && m.variant !== "baked") errors.push('variant: expected "kit" or "baked"');
  if (m.lighting !== "realtime" && m.lighting !== "baked")
    errors.push('lighting: expected "realtime" or "baked"');

  const grid = m.grid;
  let gridOk = isObject(grid);
  if (!gridOk) errors.push("grid: expected an object");
  else {
    if (!isNum(grid.cellSize) || grid.cellSize <= 0) errors.push("grid.cellSize: expected a positive number");
    if (!isVec(grid.origin, 2)) errors.push("grid.origin: expected [x, z]");
    if (!Number.isInteger(grid.width) || !Number.isInteger(grid.depth))
      errors.push("grid.width/depth: expected integers");
    if (!Array.isArray(grid.walkable) || grid.walkable.length !== grid.depth) {
      errors.push(`grid.walkable: expected ${grid.depth} rows`);
      gridOk = false;
    } else {
      grid.walkable.forEach((row: unknown, i: number) => {
        if (typeof row !== "string") return errors.push(`grid.walkable[${i}]: expected a string`);
        if (row.length !== grid.width)
          errors.push(`grid.walkable[${i}]: expected ${grid.width} characters, found ${row.length}`);
        const bad = [...row].find((ch) => ch !== "." && ch !== "#");
        if (bad) errors.push(`grid.walkable[${i}]: unknown character "${bad}"`);
      });
    }
    gridOk = gridOk && errors.length === 0;
  }

  const zones = m.zones;
  if (!isObject(zones)) errors.push("zones: expected an object");
  else {
    for (const [role, min] of Object.entries(ZONE_MINIMUMS)) {
      const list = zones[role];
      if (!Array.isArray(list)) {
        errors.push(`zones.${role}: expected an array`);
        continue;
      }
      if (list.length < min) errors.push(`zones.${role}: at least ${min} required, found ${list.length}`);
      list.forEach((z: any, i: number) => {
        const where = `zones.${role}[${i}]`;
        if (!isObject(z) || typeof z.id !== "string") return errors.push(`${where}: expected a zone with an id`);
        if (!isVec(z.position, 3)) errors.push(`${where} (${z.id}): position must be [x, y, z]`);
        if (!isNum(z.facing)) errors.push(`${where} (${z.id}): facing must be a number`);
        if (z.pose !== "seated" && z.pose !== "standing")
          errors.push(`${where} (${z.id}): pose must be "seated" or "standing"`);
        if (z.loop !== undefined && !(Array.isArray(z.loop) && z.loop.every((p: unknown) => isVec(p, 2))))
          errors.push(`${where} (${z.id}): loop must be a list of [x, z] points`);
      });
    }
  }

  if (!Array.isArray(m.ambientPaths)) errors.push("ambientPaths: expected an array");
  else
    m.ambientPaths.forEach((p: any, i: number) => {
      if (!isObject(p) || !Array.isArray(p.points) || !p.points.every((q: unknown) => isVec(q, 2)))
        errors.push(`ambientPaths[${i}]: expected points as [x, z] pairs`);
      else if (p.kind !== "pedestrian" && p.kind !== "bird")
        errors.push(`ambientPaths[${i}]: kind must be "pedestrian" or "bird"`);
    });

  const cam = m.camera;
  if (!isObject(cam) || !isObject(cam.home) || !isObject(cam.bounds) || !isVec(cam.zoom, 2))
    errors.push("camera: expected home, bounds and zoom");
  if (!isObject(m.ambience) || !isObject(m.ambience.sun) || !isObject(m.ambience.fog))
    errors.push("ambience: expected sun, hemisphere, fog, bloom, dof and sky");

  // Spatial rules only make sense once the shape is sound.
  if (errors.length === 0 && gridOk) errors.push(...spatialErrors(m as EnvironmentManifest));
  return errors.length ? { ok: false, errors } : { ok: true, manifest: m as EnvironmentManifest };
}

function spatialErrors(m: EnvironmentManifest): string[] {
  const errors: string[] = [];
  const walk = parseWalkable(m.grid);
  const located: { label: string; cell: [number, number] }[] = [];
  for (const role of ["workstation", "review", "lounge"] as const) {
    m.zones[role].forEach((z: Zone, i: number) => {
      const label = `zones.${role}[${i}] (${z.id})`;
      const cell = worldToCell(m.grid, z.position[0], z.position[2]);
      if (cell[0] < 0 || cell[1] < 0 || cell[0] >= m.grid.width || cell[1] >= m.grid.depth)
        errors.push(`${label} is outside the grid`);
      else if (!walk.walkable(...cell)) errors.push(`${label} is on a blocked cell`);
      else located.push({ label, cell });
    });
  }
  const [anchor, ...rest] = located;
  if (anchor)
    for (const other of rest)
      if (!findPath(walk, anchor.cell, other.cell))
        errors.push(`${other.label} is not reachable from ${anchor.label}`);
  return errors;
}
