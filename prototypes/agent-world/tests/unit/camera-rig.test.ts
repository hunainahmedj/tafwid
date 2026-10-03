import { describe, expect, it } from "vitest";
import { cameraPose, createRig, follow, goHome, PITCH, pan, rotate, step, zoom } from "../../src/world/camera-rig";

const home = { target: [0, 0] as [number, number], yaw: 0.6, distance: 30 };
const bounds = { minX: -10, maxX: 10, minZ: -8, maxZ: 8 };

describe("camera rig", () => {
  it("rotate snaps yawGoal by quarter turns", () => {
    const r = rotate(rotate(createRig(home), 1), 1);
    expect(r.yawGoal).toBeCloseTo(0.6 + Math.PI);
    expect(rotate(createRig(home), -1).yawGoal).toBeCloseTo(0.6 - Math.PI / 2);
  });

  it("zoom clamps to range", () => {
    expect(zoom(createRig(home), 100, [14, 44]).distanceGoal).toBe(44);
    expect(zoom(createRig(home), -100, [14, 44]).distanceGoal).toBe(14);
  });

  it("pan clamps target to bounds and stops following", () => {
    const r = pan(follow(createRig(home), "ada"), -100000, -100000, 800, bounds);
    expect(r.followId).toBeNull();
    expect(r.target[0]).toBeGreaterThanOrEqual(bounds.minX);
    expect(r.target[0]).toBeLessThanOrEqual(bounds.maxX);
    expect(r.target[1]).toBeGreaterThanOrEqual(bounds.minZ);
    expect(r.target[1]).toBeLessThanOrEqual(bounds.maxZ);
  });

  it("step converges on the follow target", () => {
    let r = follow(createRig(home), "ada");
    for (let i = 0; i < 200; i++) r = step(r, 1 / 60, [5, -3], false);
    expect(r.target[0]).toBeCloseTo(5, 2);
    expect(r.target[1]).toBeCloseTo(-3, 2);
  });

  it("reduced motion jumps straight to goals", () => {
    const r = step(zoom(rotate(createRig(home), 1), 10, [14, 44]), 1 / 60, null, true);
    expect(r.yaw).toBe(r.yawGoal);
    expect(r.distance).toBe(r.distanceGoal);
  });

  it("cameraPose sits distance away at the fixed pitch", () => {
    const { position, lookAt } = cameraPose(createRig(home));
    const d = Math.hypot(position[0] - lookAt[0], position[1] - lookAt[1], position[2] - lookAt[2]);
    expect(d).toBeCloseTo(30);
    expect(Math.asin((position[1] - lookAt[1]) / d)).toBeCloseTo(PITCH);
  });

  it("goHome glides back without spinning a full turn", () => {
    let r = pan(rotate(rotate(rotate(rotate(rotate(createRig(home), 1), 1), 1), 1), 1), 300, 0, 800, bounds);
    for (let i = 0; i < 300; i++) r = step(r, 1 / 60, null, false);
    r = goHome(r, home);
    expect(Math.abs(r.yawGoal - r.yaw)).toBeLessThanOrEqual(Math.PI);
    for (let i = 0; i < 400; i++) r = step(r, 1 / 60, null, false);
    expect(r.target[0]).toBeCloseTo(0, 1);
    expect(r.glideTo).toBeNull();
  });
});
