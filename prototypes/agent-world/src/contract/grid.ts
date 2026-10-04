import type { Grid, Vec2 } from "./manifest";
import { gridFromRows, type Cell, type WalkGrid } from "../world/pathfinding";

export function worldToCell(grid: Grid, x: number, z: number): Cell {
  return [
    Math.floor((x - grid.origin[0]) / grid.cellSize),
    Math.floor((z - grid.origin[1]) / grid.cellSize),
  ];
}

/** World [x, z] of a cell's centre. */
export function cellToWorld(grid: Grid, col: number, row: number): Vec2 {
  return [
    grid.origin[0] + (col + 0.5) * grid.cellSize,
    grid.origin[1] + (row + 0.5) * grid.cellSize,
  ];
}

export function parseWalkable(grid: Grid): WalkGrid {
  return gridFromRows(grid.walkable);
}
