import { describe, expect, it } from "vitest";
import { createFrameSampler } from "../../src/world/frame-sampler";

describe("frame sampler", () => {
  it("reports p50 and p95 of a known series", () => {
    const s = createFrameSampler(100);
    for (let i = 1; i <= 100; i++) s.push(i);
    expect(s.stats()).toEqual({ p50: 50, p95: 95, count: 100 });
  });

  it("keeps only the rolling window", () => {
    const s = createFrameSampler(10);
    for (let i = 0; i < 50; i++) s.push(i < 40 ? 100 : 5);
    expect(s.stats().p95).toBe(5);
  });

  it("shouldStepDown is false below the window size", () => {
    const s = createFrameSampler(120);
    for (let i = 0; i < 119; i++) s.push(50);
    expect(s.shouldStepDown(16.7)).toBe(false);
    s.push(50);
    expect(s.shouldStepDown(16.7)).toBe(true);
  });

  it("reset clears samples", () => {
    const s = createFrameSampler(10);
    for (let i = 0; i < 10; i++) s.push(50);
    s.reset();
    expect(s.stats().count).toBe(0);
  });
});
