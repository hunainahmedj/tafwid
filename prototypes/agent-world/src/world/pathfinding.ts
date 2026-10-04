export type Cell = [col: number, row: number];

export interface WalkGrid {
  width: number;
  depth: number;
  walkable(col: number, row: number): boolean;
}

/** Builds a grid from rows where `.` is walkable and anything else is blocked. */
export function gridFromRows(rows: string[]): WalkGrid {
  const depth = rows.length;
  const width = rows[0]?.length ?? 0;
  return {
    width,
    depth,
    walkable: (c, r) => r >= 0 && r < depth && c >= 0 && c < width && rows[r][c] === ".",
  };
}

const STEPS: [number, number, number][] = [
  [1, 0, 1], [-1, 0, 1], [0, 1, 1], [0, -1, 1],
  [1, 1, Math.SQRT2], [1, -1, Math.SQRT2], [-1, 1, Math.SQRT2], [-1, -1, Math.SQRT2],
];

function octile(a: Cell, b: Cell): number {
  const dx = Math.abs(a[0] - b[0]);
  const dy = Math.abs(a[1] - b[1]);
  return Math.max(dx, dy) + (Math.SQRT2 - 1) * Math.min(dx, dy);
}

/** A* over the grid with 8-way moves; diagonals never cut a blocked corner. */
export function findPath(grid: WalkGrid, from: Cell, to: Cell): Cell[] | null {
  if (!grid.walkable(...from) || !grid.walkable(...to)) return null;
  const key = (c: number, r: number) => r * grid.width + c;
  const goal = key(...to);
  const g = new Map<number, number>([[key(...from), 0]]);
  const parent = new Map<number, number>();
  const closed = new Set<number>();
  // Binary heap of [f, key].
  const heap: [number, number][] = [[octile(from, to), key(...from)]];
  const push = (item: [number, number]) => {
    heap.push(item);
    let i = heap.length - 1;
    while (i > 0) {
      const p = (i - 1) >> 1;
      if (heap[p][0] <= heap[i][0]) break;
      [heap[p], heap[i]] = [heap[i], heap[p]];
      i = p;
    }
  };
  const pop = () => {
    const top = heap[0];
    const last = heap.pop()!;
    if (heap.length) {
      heap[0] = last;
      let i = 0;
      for (;;) {
        const l = 2 * i + 1, r = l + 1;
        let m = i;
        if (l < heap.length && heap[l][0] < heap[m][0]) m = l;
        if (r < heap.length && heap[r][0] < heap[m][0]) m = r;
        if (m === i) break;
        [heap[m], heap[i]] = [heap[i], heap[m]];
        i = m;
      }
    }
    return top;
  };

  while (heap.length) {
    const [, current] = pop();
    if (current === goal) {
      const path: Cell[] = [];
      for (let k: number | undefined = current; k !== undefined; k = parent.get(k))
        path.push([k % grid.width, Math.floor(k / grid.width)]);
      return path.reverse();
    }
    if (closed.has(current)) continue;
    closed.add(current);
    const c = current % grid.width, r = Math.floor(current / grid.width);
    for (const [dc, dr, cost] of STEPS) {
      const nc = c + dc, nr = r + dr;
      if (!grid.walkable(nc, nr)) continue;
      if (dc && dr && (!grid.walkable(c + dc, r) || !grid.walkable(c, r + dr))) continue;
      const next = key(nc, nr);
      if (closed.has(next)) continue;
      const tentative = g.get(current)! + cost;
      if (tentative >= (g.get(next) ?? Infinity)) continue;
      g.set(next, tentative);
      parent.set(next, current);
      push([tentative + octile([nc, nr], to), next]);
    }
  }
  return null;
}

/** Drops points that continue in the same direction as the previous step. */
export function simplifyPath(path: Cell[]): Cell[] {
  if (path.length < 3) return path.slice();
  const out: Cell[] = [path[0]];
  for (let i = 1; i < path.length - 1; i++) {
    const [a, b, c] = [path[i - 1], path[i], path[i + 1]];
    if (b[0] - a[0] !== c[0] - b[0] || b[1] - a[1] !== c[1] - b[1]) out.push(b);
  }
  out.push(path.at(-1)!);
  return out;
}
