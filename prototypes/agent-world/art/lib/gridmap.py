"""Walk-grid authoring: start fully walkable, then block world-space rectangles.

Pure Python (no bpy) so layouts can be checked outside Blender.
"""

import math


class GridMap:
    def __init__(self, origin, width, depth, cell=1.0):
        self.origin = origin  # world (x, z) of the minimum corner
        self.width = width
        self.depth = depth
        self.cell = cell
        self.cells = [[True] * width for _ in range(depth)]

    def to_cell(self, x, z):
        return (int(math.floor((x - self.origin[0]) / self.cell)), int(math.floor((z - self.origin[1]) / self.cell)))

    def centre(self, col, row):
        return (self.origin[0] + (col + 0.5) * self.cell, self.origin[1] + (row + 0.5) * self.cell)

    def block_rect(self, x0, z0, x1, z1):
        """Blocks every cell whose centre lies inside the world rectangle."""
        for row in range(self.depth):
            for col in range(self.width):
                cx, cz = self.centre(col, row)
                if min(x0, x1) <= cx <= max(x0, x1) and min(z0, z1) <= cz <= max(z0, z1):
                    self.cells[row][col] = False

    def block_footprint(self, x, z, sx, sz, rot=0.0, pad=0.0):
        """Blocks the axis-aligned footprint of an object centred at (x, z)."""
        if abs(math.sin(rot)) > 0.7:
            sx, sz = sz, sx
        self.block_rect(x - sx / 2 - pad, z - sz / 2 - pad, x + sx / 2 + pad, z + sz / 2 + pad)

    def open_rect(self, x0, z0, x1, z1):
        for row in range(self.depth):
            for col in range(self.width):
                cx, cz = self.centre(col, row)
                if min(x0, x1) <= cx <= max(x0, x1) and min(z0, z1) <= cz <= max(z0, z1):
                    self.cells[row][col] = True

    def walkable(self, x, z):
        col, row = self.to_cell(x, z)
        return 0 <= col < self.width and 0 <= row < self.depth and self.cells[row][col]

    def rows(self):
        return ["".join("." if c else "#" for c in row) for row in self.cells]

    def manifest(self):
        return {
            "cellSize": self.cell,
            "origin": list(self.origin),
            "width": self.width,
            "depth": self.depth,
            "walkable": self.rows(),
        }
