import type { EnvironmentManifest, Vec2, Vec3 } from "../contract/manifest";

/** Fixed high pitch (radians above the horizon) and narrow field of view. */
export const PITCH = 0.92;
export const FOV_DEGREES = 26;

type Home = EnvironmentManifest["camera"]["home"];
type Bounds = EnvironmentManifest["camera"]["bounds"];

export interface RigState {
  target: Vec2;
  yaw: number;
  yawGoal: number;
  distance: number;
  distanceGoal: number;
  pitch: number;
  followId: string | null;
  /** A point the target glides to (for example, home); cleared on arrival or pan. */
  glideTo: Vec2 | null;
}

export function createRig(home: Home): RigState {
  return {
    target: [...home.target],
    yaw: home.yaw,
    yawGoal: home.yaw,
    distance: home.distance,
    distanceGoal: home.distance,
    pitch: PITCH,
    followId: null,
    glideTo: null,
  };
}

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/** Grab-style pan: the ground under the pointer moves with it. Stops following. */
export function pan(s: RigState, dxPx: number, dyPx: number, viewportHeightPx: number, b: Bounds): RigState {
  const worldPerPx = (2 * s.distance * Math.tan((FOV_DEGREES * Math.PI) / 360)) / Math.max(1, viewportHeightPx);
  const right: Vec2 = [Math.cos(s.yaw), -Math.sin(s.yaw)];
  const towardCamera: Vec2 = [Math.sin(s.yaw), Math.cos(s.yaw)];
  const depthScale = 1 / Math.sin(s.pitch);
  const x = s.target[0] - right[0] * dxPx * worldPerPx - towardCamera[0] * dyPx * worldPerPx * depthScale;
  const z = s.target[1] - right[1] * dxPx * worldPerPx - towardCamera[1] * dyPx * worldPerPx * depthScale;
  return { ...s, followId: null, glideTo: null, target: [clamp(x, b.minX, b.maxX), clamp(z, b.minZ, b.maxZ)] };
}

export function rotate(s: RigState, dir: 1 | -1): RigState {
  return { ...s, yawGoal: s.yawGoal + (dir * Math.PI) / 2 };
}

export function zoom(s: RigState, delta: number, range: [number, number]): RigState {
  return { ...s, distanceGoal: clamp(s.distanceGoal + delta, range[0], range[1]) };
}

export function follow(s: RigState, id: string | null): RigState {
  return { ...s, followId: id };
}

/** Returns to the home framing, keeping the nearest equivalent yaw so it never spins a full turn. */
export function goHome(s: RigState, home: Home): RigState {
  const turns = Math.round((s.yaw - home.yaw) / (2 * Math.PI));
  return {
    ...s,
    followId: null,
    yawGoal: home.yaw + turns * 2 * Math.PI,
    distanceGoal: home.distance,
    glideTo: [...home.target],
  };
}

const ease = (rate: number, dt: number) => 1 - Math.exp(-rate * dt);

/** Advances easing; `followTarget` is the followed agent's ground position, if any. */
export function step(s: RigState, dt: number, followTarget: Vec2 | null, reducedMotion: boolean): RigState {
  const goal = followTarget ?? s.glideTo;
  if (reducedMotion)
    return { ...s, yaw: s.yawGoal, distance: s.distanceGoal, target: goal ? [...goal] : s.target, glideTo: null };
  const a = ease(5, dt);
  const target: Vec2 = goal
    ? [s.target[0] + (goal[0] - s.target[0]) * a, s.target[1] + (goal[1] - s.target[1]) * a]
    : s.target;
  const arrived = s.glideTo && Math.hypot(s.glideTo[0] - target[0], s.glideTo[1] - target[1]) < 0.01;
  return {
    ...s,
    yaw: s.yaw + (s.yawGoal - s.yaw) * ease(10, dt),
    distance: s.distance + (s.distanceGoal - s.distance) * ease(9, dt),
    target,
    glideTo: arrived || followTarget ? null : s.glideTo,
  };
}

export function cameraPose(s: RigState): { position: Vec3; lookAt: Vec3 } {
  const horizontal = Math.cos(s.pitch) * s.distance;
  return {
    position: [
      s.target[0] + Math.sin(s.yaw) * horizontal,
      Math.sin(s.pitch) * s.distance,
      s.target[1] + Math.cos(s.yaw) * horizontal,
    ],
    lookAt: [s.target[0], 0, s.target[1]],
  };
}
