/** The environment package contract, schema `tafwid.environment/1`. */
export const MANIFEST_SCHEMA = "tafwid.environment/1";

export type Vec2 = [number, number];
export type Vec3 = [number, number, number];

export interface Zone {
  id: string;
  position: Vec3;
  /** Yaw in radians; 0 faces +Z. */
  facing: number;
  pose: "seated" | "standing";
  /** Lounge zones may declare a walking loop in world [x, z] points. */
  loop?: Vec2[];
}

export interface Grid {
  cellSize: number;
  /** World [x, z] of the grid's minimum corner. */
  origin: Vec2;
  width: number;
  depth: number;
  /** One string per row; `.` walkable, `#` blocked. */
  walkable: string[];
}

export interface AmbientPath {
  id: string;
  kind: "pedestrian" | "bird";
  points: Vec2[];
  loop: boolean;
}

export interface Ambience {
  sun: { direction: Vec3; color: string; intensity: number };
  hemisphere: { sky: string; ground: string; intensity: number };
  fog: { color: string; near: number; far: number };
  exposure: number;
  bloom: { strength: number; radius: number; threshold: number };
  /** Focus distance offset from the camera target, the in-focus range and blur strength. */
  dof: { focusOffset: number; range: number; strength: number };
  sky: { top: string; bottom: string };
}

export interface EnvironmentManifest {
  schema: typeof MANIFEST_SCHEMA;
  id: string;
  variant: "kit" | "baked";
  name: string;
  scene: string;
  lighting: "realtime" | "baked";
  grid: Grid;
  zones: { workstation: Zone[]; review: Zone[]; lounge: Zone[] };
  ambientPaths: AmbientPath[];
  camera: {
    home: { target: Vec2; yaw: number; distance: number };
    bounds: { minX: number; maxX: number; minZ: number; maxZ: number };
    zoom: [number, number];
  };
  ambience: Ambience;
}

export const ZONE_MINIMUMS = { workstation: 6, review: 1, lounge: 1 } as const;
