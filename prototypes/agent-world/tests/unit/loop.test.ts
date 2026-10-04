import { describe, expect, it, vi } from "vitest";
import { finite, loopDriver, warnOnce } from "../../src/world/loop";

describe("loop driver", () => {
  it("runs on animation frames when the page reports itself hidden", () => {
    // Some hosts report hidden while they keep painting; the browser pauses frames for a truly hidden tab.
    expect(loopDriver(true, false)).toBe("frames");
  });

  it("runs on animation frames when visible", () => {
    expect(loopDriver(false, false)).toBe("frames");
    expect(loopDriver(false, true)).toBe("frames");
  });

  it("uses a timer only for the hidden-render debug mode", () => {
    expect(loopDriver(true, true)).toBe("timer");
  });
});

describe("finite", () => {
  it("accepts finite vectors and rejects NaN or infinite components", () => {
    expect(finite([1, 0, -3.5])).toBe(true);
    expect(finite([1, NaN, 0])).toBe(false);
    expect(finite([Infinity, 0])).toBe(false);
  });
});

describe("warnOnce", () => {
  it("logs a key once", () => {
    const spy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const warn = warnOnce();
    warn("camera", "bad camera");
    warn("camera", "bad camera");
    warn("agent:a", "bad agent");
    expect(spy).toHaveBeenCalledTimes(2);
    spy.mockRestore();
  });
});
