import { describe, expect, it } from "vitest";
import { isFoliage } from "../../src/world/foliage";

describe("isFoliage", () => {
  it("accepts kit foliage and its baked copies", () => {
    expect(isFoliage("leaf_leaf_a")).toBe(true);
    expect(isFoliage("leaf_leaf_dark__a1_2_leaf_lm")).toBe(true);
  });
  it("rejects props that only use a leaf colour", () => {
    expect(isFoliage("leaf_autumn")).toBe(false);
    expect(isFoliage("leaf_c")).toBe(false);
    expect(isFoliage("leaf_autumn__a2_1_lm")).toBe(false);
  });
});
