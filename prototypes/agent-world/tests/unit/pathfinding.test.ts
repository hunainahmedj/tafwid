import { describe, expect, it } from "vitest";
import { findPath, gridFromRows, simplifyPath } from "../../src/world/pathfinding";

describe("findPath", () => {
  it("returns [start] when start equals goal", () => {
    const grid = gridFromRows(["...", "...", "..."]);
    expect(findPath(grid, [1, 1], [1, 1])).toEqual([[1, 1]]);
  });

  it("walks a straight corridor", () => {
    const grid = gridFromRows(["......"]);
    const path = findPath(grid, [0, 0], [5, 0]);
    expect(path).toHaveLength(6);
    expect(path?.[0]).toEqual([0, 0]);
    expect(path?.at(-1)).toEqual([5, 0]);
  });

  it("routes around a wall", () => {
    const grid = gridFromRows([
      ".....",
      ".###.",
      ".....",
    ]);
    const path = findPath(grid, [2, 0], [2, 2]);
    expect(path).not.toBeNull();
    for (const [c, r] of path!) expect(grid.walkable(c, r)).toBe(true);
    expect(path?.at(-1)).toEqual([2, 2]);
  });

  it("returns null when the goal is enclosed", () => {
    const grid = gridFromRows([
      ".....",
      ".###.",
      ".#.#.",
      ".###.",
    ]);
    expect(findPath(grid, [0, 0], [2, 2])).toBeNull();
  });

  it("never cuts a blocked corner diagonally", () => {
    const grid = gridFromRows([
      ".#",
      "..",
    ]);
    const path = findPath(grid, [0, 0], [1, 1])!;
    expect(path).toEqual([[0, 0], [0, 1], [1, 1]]);
  });
});

describe("simplifyPath", () => {
  it("keeps only turning points", () => {
    const path: [number, number][] = [[0, 0], [1, 0], [2, 0], [2, 1], [2, 2], [3, 3]];
    expect(simplifyPath(path)).toEqual([[0, 0], [2, 0], [2, 2], [3, 3]]);
  });
});
