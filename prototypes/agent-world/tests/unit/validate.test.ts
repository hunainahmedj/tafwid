import { describe, expect, it } from "vitest";
import valid from "./fixtures/manifest.valid.json";
import { validateManifest } from "../../src/contract/validate";
import { cellToWorld, worldToCell } from "../../src/contract/grid";

const clone = () => structuredClone(valid) as any;
const errorsOf = (m: unknown) => {
  const result = validateManifest(m);
  return result.ok ? [] : result.errors;
};

describe("validateManifest", () => {
  it("accepts the valid fixture", () => {
    expect(validateManifest(clone()).ok).toBe(true);
  });

  it("rejects a wrong schema", () => {
    const m = clone();
    m.schema = "tafwid.environment/0";
    expect(errorsOf(m)).toContain('schema: expected "tafwid.environment/1"');
  });

  it("rejects a non-object", () => {
    expect(errorsOf(null)).toContain("manifest: expected an object");
  });

  it("requires six workstations", () => {
    const m = clone();
    m.zones.workstation.pop();
    expect(errorsOf(m)).toContain("zones.workstation: at least 6 required, found 5");
  });

  it("requires a review spot", () => {
    const m = clone();
    m.zones.review = [];
    expect(errorsOf(m)).toContain("zones.review: at least 1 required, found 0");
  });

  it("rejects a zone on a blocked cell", () => {
    const m = clone();
    m.zones.workstation[2].position = [-3.5, 0, -1.5]; // col 2, row 2 is '#'
    expect(errorsOf(m)).toContain("zones.workstation[2] (ws-3) is on a blocked cell");
  });

  it("rejects an unreachable zone", () => {
    const m = clone();
    // Wall off the top-right corner that holds the review spot (col 10, row 0).
    m.grid.walkable[0] = "........#...";
    m.grid.walkable[1] = "........####";
    expect(errorsOf(m)).toContain(
      "zones.review[0] (review-1) is not reachable from zones.workstation[0] (ws-1)",
    );
  });

  it("rejects a malformed walkable row", () => {
    const m = clone();
    m.grid.walkable[4] = "...........";
    m.grid.walkable[5] = ".....x......";
    const errors = errorsOf(m);
    expect(errors).toContain("grid.walkable[4]: expected 12 characters, found 11");
    expect(errors).toContain('grid.walkable[5]: unknown character "x"');
  });

  it("rejects a zone outside the grid", () => {
    const m = clone();
    m.zones.lounge[0].position = [40, 0, 40];
    expect(errorsOf(m)).toContain("zones.lounge[0] (lounge-1) is outside the grid");
  });
});

describe("grid conversion", () => {
  it("round-trips worldToCell and cellToWorld", () => {
    const grid = clone().grid;
    expect(cellToWorld(grid, 3, 2)).toEqual([-2.5, -1.5]);
    expect(worldToCell(grid, -2.5, -1.5)).toEqual([3, 2]);
    expect(worldToCell(grid, -2.01, -1.99)).toEqual([3, 2]);
  });
});
