import {
  ENTRANCE_MINIMUM,
  LEGACY_MANIFEST_SCHEMA,
  MANIFEST_SCHEMA,
  SEAT_GROUP_KINDS,
  SEAT_MINIMUM,
  ZONE_MINIMUMS,
  type EnvironmentManifest,
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
 * Checks shape first, then the spatial rules: seat and zone minimums, seats,
 * zones and entrances on walkable cells, and everything reachable from the
 * first seat.
 */
export function validateManifest(input: unknown): ValidationResult {
  const errors: string[] = [];
  if (!isObject(input)) return { ok: false, errors: ["manifest: expected an object"] };
  const m = input;

  if (m.schema === LEGACY_MANIFEST_SCHEMA)
    return {
      ok: false,
      errors: [`schema: "${LEGACY_MANIFEST_SCHEMA}" is no longer supported; rebuild the package as "${MANIFEST_SCHEMA}"`],
    };
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

  const seating = m.seating;
  if (!Array.isArray(seating)) errors.push("seating: expected an array of seat groups");
  else {
    let seatCount = 0;
    const seen = new Set<string>();
    seating.forEach((g: any, gi: number) => {
      const group = `seating[${gi}]`;
      if (!isObject(g) || typeof g.id !== "string" || !g.id)
        return errors.push(`${group}: expected a seat group with an id`);
      if (!SEAT_GROUP_KINDS.includes(g.kind))
        errors.push(`${group} (${g.id}): kind must be ${SEAT_GROUP_KINDS.slice(0, -1).join(", ")} or ${SEAT_GROUP_KINDS.at(-1)}`);
      if (!Array.isArray(g.seats) || g.seats.length === 0)
        return errors.push(`${group} (${g.id}): expected at least one seat`);
      g.seats.forEach((z: any, si: number) => {
        const where = `${group}.seats[${si}]`;
        if (!isObject(z) || typeof z.id !== "string" || !z.id) return errors.push(`${where}: expected a seat with an id`);
        seatCount++;
        if (seen.has(z.id)) errors.push(`${where}: duplicate seat id "${z.id}"`);
        seen.add(z.id);
        if (!isVec(z.position, 3)) errors.push(`${where} (${z.id}): position must be [x, y, z]`);
        if (!isNum(z.facing)) errors.push(`${where} (${z.id}): facing must be a number`);
        if (z.pose !== "seated" && z.pose !== "standing")
          errors.push(`${where} (${z.id}): pose must be "seated" or "standing"`);
      });
    });
    if (seatCount < SEAT_MINIMUM) errors.push(`seating: at least ${SEAT_MINIMUM} seats required, found ${seatCount}`);
  }

  const entrances = m.entrances;
  if (!Array.isArray(entrances)) errors.push("entrances: expected an array of [x, z] points");
  else {
    if (entrances.length < ENTRANCE_MINIMUM)
      errors.push(`entrances: at least ${ENTRANCE_MINIMUM} required, found ${entrances.length}`);
    entrances.forEach((p: unknown, i: number) => {
      if (!isVec(p, 2)) errors.push(`entrances[${i}]: expected [x, z]`);
    });
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
  if (!isObject(cam)) errors.push("camera: expected home, bounds and zoom");
  else {
    const home = cam.home;
    if (!isObject(home) || !isVec(home.target, 2) || !isNum(home.yaw) || !isNum(home.distance))
      errors.push("camera.home: expected target [x, z], yaw and distance");
    const b = cam.bounds;
    if (!isObject(b) || !["minX", "maxX", "minZ", "maxZ"].every((k) => isNum(b[k])))
      errors.push("camera.bounds: expected numbers minX, maxX, minZ and maxZ");
    if (!isVec(cam.zoom, 2)) errors.push("camera.zoom: expected [min, max]");
  }

  // Every ambience field the renderer reads, so a bad package fails here with a name.
  const a = m.ambience;
  const isStr = (v: unknown) => typeof v === "string" && v.length > 0;
  if (!isObject(a)) errors.push("ambience: expected sun, hemisphere, fog, exposure, bloom, dof and sky");
  else {
    if (!isObject(a.sun) || !isVec(a.sun.direction, 3) || !isStr(a.sun.color) || !isNum(a.sun.intensity))
      errors.push("ambience.sun: expected direction [x, y, z], color and intensity");
    if (!isObject(a.hemisphere) || !isStr(a.hemisphere.sky) || !isStr(a.hemisphere.ground) || !isNum(a.hemisphere.intensity))
      errors.push("ambience.hemisphere: expected sky, ground and intensity");
    if (!isObject(a.fog) || !isStr(a.fog.color) || !isNum(a.fog.near) || !isNum(a.fog.far))
      errors.push("ambience.fog: expected color, near and far");
    if (!isNum(a.exposure)) errors.push("ambience.exposure: expected a number");
    if (!isObject(a.bloom) || !isNum(a.bloom.strength) || !isNum(a.bloom.radius) || !isNum(a.bloom.threshold))
      errors.push("ambience.bloom: expected strength, radius and threshold");
    if (!isObject(a.dof) || !isNum(a.dof.focusOffset) || !isNum(a.dof.range) || !isNum(a.dof.strength))
      errors.push("ambience.dof: expected focusOffset, range and strength");
    if (!isObject(a.sky) || !isStr(a.sky.top) || !isStr(a.sky.bottom)) errors.push("ambience.sky: expected top and bottom colours");
  }

  // Spatial rules only make sense once the shape is sound.
  if (errors.length === 0 && gridOk) errors.push(...spatialErrors(m as EnvironmentManifest));
  return errors.length ? { ok: false, errors } : { ok: true, manifest: m as EnvironmentManifest };
}

function spatialErrors(m: EnvironmentManifest): string[] {
  const errors: string[] = [];
  const walk = parseWalkable(m.grid);
  const located: { label: string; cell: [number, number] }[] = [];
  const check = (label: string, x: number, z: number) => {
    const cell = worldToCell(m.grid, x, z);
    if (cell[0] < 0 || cell[1] < 0 || cell[0] >= m.grid.width || cell[1] >= m.grid.depth)
      errors.push(`${label} is outside the grid`);
    else if (!walk.walkable(...cell)) errors.push(`${label} is on a blocked cell`);
    else located.push({ label, cell });
  };
  m.seating.forEach((g, gi) =>
    g.seats.forEach((s, si) => check(`seating[${gi}].seats[${si}] (${s.id})`, s.position[0], s.position[2])),
  );
  for (const role of ["review", "lounge"] as const)
    m.zones[role].forEach((z, i) => check(`zones.${role}[${i}] (${z.id})`, z.position[0], z.position[2]));
  m.entrances.forEach((p, i) => check(`entrances[${i}]`, p[0], p[1]));
  const [anchor, ...rest] = located;
  if (anchor)
    for (const other of rest)
      if (!findPath(walk, anchor.cell, other.cell))
        errors.push(`${other.label} is not reachable from ${anchor.label}`);
  return errors;
}
