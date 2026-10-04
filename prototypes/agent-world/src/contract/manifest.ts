/** The environment package contract, schema `tafwid.environment/2`. */
export const MANIFEST_SCHEMA = "tafwid.environment/2";
/** The previous schema, kept only so the validator can name it. */
export const LEGACY_MANIFEST_SCHEMA = "tafwid.environment/1";

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

/** One place for one agent to sit or stand; the shape of a zone without a loop. */
export interface Seat {
  id: string;
  position: Vec3;
  /** Yaw in radians; 0 faces +Z. */
  facing: number;
  pose: "seated" | "standing";
}

export const SEAT_GROUP_KINDS = ["desk", "table", "bar", "bench", "standing", "lounge"] as const;
export type SeatGroupKind = (typeof SEAT_GROUP_KINDS)[number];

/** Seats that belong together, such as the chairs of one table. */
export interface SeatGroup {
  id: string;
  kind: SeatGroupKind;
  seats: Seat[];
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
  seating: SeatGroup[];
  /** World [x, z] points on walkable cells where agents enter the scene. */
  entrances: Vec2[];
  zones: { review: Zone[]; lounge: Zone[] };
  ambientPaths: AmbientPath[];
  camera: {
    home: { target: Vec2; yaw: number; distance: number };
    bounds: { minX: number; maxX: number; minZ: number; maxZ: number };
    zoom: [number, number];
  };
  ambience: Ambience;
}

export const ZONE_MINIMUMS = { review: 1, lounge: 1 } as const;
export const SEAT_MINIMUM = 12;
export const ENTRANCE_MINIMUM = 1;
