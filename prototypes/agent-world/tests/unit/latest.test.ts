import { describe, expect, it } from "vitest";
import { createLatestOnly } from "../../src/world/latest";

describe("createLatestOnly", () => {
  it("reports only the most recent request as current", () => {
    const latest = createLatestOnly();
    const first = latest.begin();
    const second = latest.begin();
    expect(latest.isCurrent(first)).toBe(false);
    expect(latest.isCurrent(second)).toBe(true);
  });
});
