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
    expect(errorsOf(m)).toContain('schema: expected "tafwid.environment/2"');
  });

  it("rejects schema 1 with a named error", () => {
    const m = clone();
    m.schema = "tafwid.environment/1";
    expect(errorsOf(m)).toEqual([
      'schema: "tafwid.environment/1" is no longer supported; rebuild the package as "tafwid.environment/2"',
    ]);
  });

  it("rejects a non-object", () => {
    expect(errorsOf(null)).toContain("manifest: expected an object");
  });

  it("requires twelve seats", () => {
    const m = clone();
    m.seating[3].seats.pop();
    expect(errorsOf(m)).toContain("seating: at least 12 seats required, found 11");
  });

  it("requires an entrance", () => {
    const m = clone();
    m.entrances = [];
    expect(errorsOf(m)).toContain("entrances: at least 1 required, found 0");
  });

  it("rejects an entrance on a blocked cell", () => {
    const m = clone();
    m.entrances = [[-3.5, -1.5]];
    expect(errorsOf(m)).toContain("entrances[0] is on a blocked cell");
  });

  it("rejects duplicate seat ids", () => {
    const m = clone();
    m.seating[1].seats[1].id = "bar-1";
    expect(errorsOf(m)).toContain('seating[1].seats[1]: duplicate seat id "bar-1"');
  });

  it("rejects an unknown seat group kind", () => {
    const m = clone();
    m.seating[0].kind = "sofa";
    expect(errorsOf(m)).toContain("seating[0] (desk-1): kind must be desk, table, bar, bench, standing or lounge");
  });

  it("requires a review spot", () => {
    const m = clone();
    m.zones.review = [];
    expect(errorsOf(m)).toContain("zones.review: at least 1 required, found 0");
  });

  it("rejects a seat on a blocked cell", () => {
    const m = clone();
    m.seating[1].seats[0].position = [-3.5, 0, -1.5]; // col 2, row 2 is '#'
    expect(errorsOf(m)).toContain("seating[1].seats[0] (bar-1) is on a blocked cell");
  });

  it("rejects an unreachable zone", () => {
    const m = clone();
    // Wall off the top-right corner that holds the review spot (col 10, row 0).
    m.grid.walkable[0] = "........#...";
    m.grid.walkable[1] = "........####";
    expect(errorsOf(m)).toContain(
      "zones.review[0] (review-1) is not reachable from seating[0].seats[0] (desk-1-a)",
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

it("names a missing ambience field instead of failing later", () => {
  const m = clone();
  delete m.ambience.sky;
  expect(errorsOf(m)).toContain("ambience.sky: expected top and bottom colours");
});

it("names missing camera bounds", () => {
  const m = clone();
  delete m.camera.bounds.minX;
  expect(errorsOf(m)).toContain("camera.bounds: expected numbers minX, maxX, minZ and maxZ");
});

it("names a malformed camera home", () => {
  const m = clone();
  m.camera.home.distance = "far";
  expect(errorsOf(m)).toContain("camera.home: expected target [x, z], yaw and distance");
});

describe("grid conversion", () => {
  it("round-trips worldToCell and cellToWorld", () => {
    const grid = clone().grid;
    expect(cellToWorld(grid, 3, 2)).toEqual([-2.5, -1.5]);
    expect(worldToCell(grid, -2.5, -1.5)).toEqual([3, 2]);
    expect(worldToCell(grid, -2.01, -1.99)).toEqual([3, 2]);
  });
});
