"""Style C kit: one builder per placement kind.

Every builder composes bevelled boxes on a local frame. Identical size and
material share one mesh, so pipeline A exports GPU instances; pipeline B
joins and bakes the same objects.

Material naming conventions read by the runtime and the bake:
  leaf_leaf_*  foliage from LEAF(); sways in the wind at runtime
  emit_*  emissive; never baked, always blooms
"""

import math
import random

from lib import materials
from lib.blocks import bevel_box

PI = math.pi


# ---------------------------------------------------------------- helpers
def M(key, roughness=0.85, metallic=0.0):
    return materials.get(key, key, roughness=roughness, metallic=metallic)


def LEAF(key):
    return materials.get("leaf_" + key, key, roughness=0.9)


def E(key, strength=2.0, base=None):
    """Emissive material; base colour defaults to the emission colour."""
    return materials.get("emit_%s_%g" % (key, strength), base or key, roughness=0.6, emission=key, emission_strength=strength)


class Frame:
    """A local frame at (x, z) rotated by `yaw` about the up axis."""

    def __init__(self, ctx, x=0.0, z=0.0, yaw=0.0, y=0.0):
        self.ctx, self.x, self.z, self.yaw, self.y = ctx, x, z, yaw, y
        self.c, self.s = math.cos(yaw), math.sin(yaw)

    def world(self, lx, lz):
        return (self.x + lx * self.c + lz * self.s, self.z - lx * self.s + lz * self.c)

    def box(self, size, mat, lx, ly, lz, radius=0.05, yaw=0.0, segments=2):
        wx, wz = self.world(lx, lz)
        return bevel_box(size, mat, (wx, self.y + ly, wz), radius=radius, rotation_y=self.yaw + yaw,
                         collection=self.ctx.collection, segments=segments)

    def sub(self, lx, lz, yaw=0.0, y=0.0):
        wx, wz = self.world(lx, lz)
        return Frame(self.ctx, wx, wz, self.yaw + yaw, self.y + y)


class Context:
    def __init__(self, collection, seed=0):
        self.collection = collection
        self.rng = random.Random(seed)


# ---------------------------------------------------------------- block-letter signs
FONT = {  # pixel glyphs, rows top to bottom; widths vary so diagonals stay legible
    "A": ["0110", "1001", "1111", "1001", "1001"], "B": ["1110", "1001", "1110", "1001", "1110"],
    "C": ["0111", "1000", "1000", "1000", "0111"], "D": ["1110", "1001", "1001", "1001", "1110"],
    "E": ["111", "100", "110", "100", "111"], "F": ["111", "100", "110", "100", "100"],
    "I": ["111", "010", "010", "010", "111"], "K": ["1001", "1010", "1100", "1010", "1001"],
    "L": ["100", "100", "100", "100", "111"], "O": ["0110", "1001", "1001", "1001", "0110"],
    "R": ["1110", "1001", "1110", "1010", "1001"], "S": ["0111", "1000", "0110", "0001", "1110"],
    "W": ["10001", "10001", "10101", "10101", "01010"], "Y": ["10001", "01010", "00100", "00100", "00100"],
    "V": ["10001", "10001", "10001", "01010", "00100"], "N": ["1001", "1101", "1011", "1001", "1001"],
    "H": ["1001", "1001", "1111", "1001", "1001"], " ": ["00", "00", "00", "00", "00"],
}


def sign_text(f, text, lx, ly, lz, px=0.12, letters=None, board=True):
    """Block letters centred at (lx, ly) on a façade plane at depth lz."""
    letters = letters or E("bulb_warm", 2.2)
    glyphs = [FONT.get(ch, FONT[" "]) for ch in text.upper()]
    columns = sum(len(g[0]) for g in glyphs) + len(glyphs) - 1
    width = columns * px
    if board:
        f.box((width + 4 * px, 7 * px, 0.1), M("sign_board"), lx, ly - px, lz, radius=0.04)
    col = 0
    x0 = lx - width / 2
    for glyph in glyphs:
        for r, row in enumerate(glyph):
            for c, bit in enumerate(row):
                if bit == "1":
                    f.box((px * 0.9, px * 0.9, 0.06), letters, x0 + (col + c) * px + px / 2, ly + (4 - r) * px, lz + 0.07,
                          radius=0.015, segments=1)
        col += len(glyph[0]) + 1


# ---------------------------------------------------------------- ground
def cobbles(ctx, x0, z0, x1, z1, seed=0, **_):
    rng = random.Random(seed)
    f = Frame(ctx)
    w, d = x1 - x0, z1 - z0
    f.box((w, 0.1, d), M("cobble_grout"), (x0 + x1) / 2, -0.12, (z0 + z1) / 2, radius=0.01)
    tones = ["cobble_a", "cobble_b", "cobble_c"]
    sizes = [0.40, 0.43, 0.46]
    step = 0.5
    rows = int(round(d / step))
    for r in range(rows):
        z = z0 + step * (r + 0.5)
        offset = 0.25 if r % 2 else 0.0
        n = int(math.floor((w - offset) / step))
        for c in range(n):
            x = x0 + offset + step * (c + 0.5)
            s = rng.choice(sizes)
            lift = rng.choice([-0.012, 0.0, 0.0, 0.01])
            f.box((s, 0.12, s), M(rng.choice(tones), roughness=0.9), x + rng.uniform(-0.02, 0.02), -0.11 + lift,
                  z + rng.uniform(-0.02, 0.02), radius=0.05)


def planks(ctx, x0, z0, x1, z1, **_):
    rng = random.Random(7)
    f = Frame(ctx)
    width = 0.25
    for r in range(int((z1 - z0) / width)):
        z = z0 + width * (r + 0.5)
        x = x0 + (rng.uniform(0, 0.9) if r % 2 else 0)
        f.box((x - x0, 0.1, width - 0.02), M("plank_b"), (x0 + x) / 2, -0.08, z, radius=0.02) if x > x0 + 0.05 else None
        while x < x1 - 0.05:
            length = min(rng.choice([1.2, 1.6, 2.0]), x1 - x)
            f.box((length - 0.02, 0.1, width - 0.02), M(rng.choice(["plank_a", "plank_a", "plank_b"])), x + length / 2,
                  -0.08, z, radius=0.02)
            x += length


def pavement(ctx, x0, z0, x1, z1, **_):
    rng = random.Random(int(x0 * 7 + z0 * 13))
    f = Frame(ctx)
    if x1 - x0 <= 0 or z1 - z0 <= 0:
        return
    nx, nz = max(1, int(round(x1 - x0))), max(1, int(round(z1 - z0)))
    sx, sz = (x1 - x0) / nx, (z1 - z0) / nz
    for i in range(nx):
        for j in range(nz):
            tone = rng.choice(["kerb", "stone_trim", "stone_trim", "cobble_c"])
            f.box((sx - 0.04, 0.16, sz - 0.04), M(tone), x0 + sx * (i + 0.5), -0.12 + rng.choice([0, 0.005]),
                  z0 + sz * (j + 0.5), radius=0.03)


def road(ctx, x0, z0, x1, z1, axis="x", **_):
    f = Frame(ctx)
    f.box((x1 - x0, 0.1, z1 - z0), M("asphalt", roughness=0.95), (x0 + x1) / 2, -0.2, (z0 + z1) / 2, radius=0.01)
    if axis == "x":
        mid = (z0 + z1) / 2
        x = x0 + 1
        while x < x1 - 1:
            f.box((1.4, 0.02, 0.14), M("pot_cream"), x + 0.7, -0.1, mid, radius=0.01)
            x += 3.0
        for zz in (z0 + 0.15, z1 - 0.15):
            f.box((x1 - x0, 0.18, 0.3), M("kerb"), (x0 + x1) / 2, -0.2, zz, radius=0.04)
    else:
        mid = (x0 + x1) / 2
        z = z0 + 1
        while z < z1 - 1:
            f.box((0.14, 0.02, 1.4), M("pot_cream"), mid, -0.1, z + 0.7, radius=0.01)
            z += 3.0
        for xx in (x0 + 0.15, x1 - 0.15):
            f.box((0.3, 0.18, z1 - z0), M("kerb"), xx, -0.2, (z0 + z1) / 2, radius=0.04)


def grass(ctx, x0, z0, x1, z1, **_):
    rng = random.Random(3)
    f = Frame(ctx)
    f.box((x1 - x0, 0.2, z1 - z0), M("grass"), (x0 + x1) / 2, -0.2, (z0 + z1) / 2, radius=0.06)
    for _i in range(int((x1 - x0) * (z1 - z0) * 0.8)):
        x, z = rng.uniform(x0 + 0.3, x1 - 0.3), rng.uniform(z0 + 0.3, z1 - 0.3)
        if rng.random() < 0.3:
            f.box((0.12, 0.12, 0.12), M(rng.choice(["neon_pink", "bulb_warm", "pot_cream"])), x, 0.0, z, radius=0.03)
        else:
            f.box((0.22, 0.18, 0.22), LEAF(rng.choice(["leaf_a", "leaf_c"])), x, 0.0, z, radius=0.05)


# ---------------------------------------------------------------- buildings
FLOOR_H = 3.0
GROUND_H = 3.4
STYLE_WALL = {
    "brick": "mortar", "brick_light": "mortar", "plaster_blue": "plaster_blue", "plaster_rose": "plaster_rose",
    "plaster_sage": "plaster_sage", "plaster_cream": "plaster_cream",
}
SHOP_ICON = {"bookshop": "awning_blue", "bakery": "leaf_autumn", "flowers": "neon_pink", "deli": "awning_red"}


def _bricks(f, width, height, y0, z_face, rng, light=False):
    """Brick courses on a façade in the local XY plane at depth z_face."""
    tones = ["brick_c", "brick_a", "brick_c"] if light else ["brick_a", "brick_b", "brick_a", "brick_c"]
    course = 0.3
    rows = int(height / course)
    for r in range(rows):
        y = y0 + r * course + 0.02
        offset = 0.31 if r % 2 else 0.0
        x = -width / 2 + offset
        if offset:
            f.box((0.28, 0.26, 0.12), M(rng.choice(tones)), -width / 2 + 0.15, y, z_face, radius=0.03)
        while x + 0.62 <= width / 2 + 0.01:
            f.box((0.58, 0.26, 0.12), M(rng.choice(tones)), x + 0.31, y, z_face, radius=0.03)
            x += 0.62


def _window(f, lx, ly, lz, rng, lit_chance, shutters=None, w=1.1, h=1.5):
    f.box((w + 0.16, h + 0.16, 0.14), M("window_frame"), lx, ly - 0.08, lz, radius=0.03)
    if rng.random() < lit_chance * 0.7:
        f.box((w, h, 0.06), E("window_glass", rng.choice([0.4, 0.6, 0.85])), lx, ly, lz + 0.06, radius=0.02)
    else:
        f.box((w, h, 0.06), M("window_dark", roughness=0.3), lx, ly, lz + 0.06, radius=0.02)
    f.box((0.08, h, 0.07), M("window_frame"), lx, ly, lz + 0.08, radius=0.01)  # mullion
    f.box((w + 0.36, 0.12, 0.3), M("stone_trim"), lx, ly - 0.2, lz + 0.08, radius=0.03)  # sill
    if shutters:
        for side in (-1, 1):
            f.box((0.42, h + 0.1, 0.08), M(shutters), lx + side * (w / 2 + 0.3), ly - 0.05, lz + 0.04, radius=0.03)
    if rng.random() < 0.35:
        f.box((w + 0.1, 0.22, 0.26), M("pot_terracotta"), lx, ly - 0.1, lz + 0.22, radius=0.04)
        for k in range(4):
            f.box((0.2, 0.2, 0.2), LEAF(rng.choice(["leaf_a", "leaf_b"])), lx - w / 2 + 0.2 + k * 0.28, ly + 0.08,
                  lz + 0.24, radius=0.06)
            if rng.random() < 0.6:
                f.box((0.1, 0.1, 0.1), M(rng.choice(["neon_pink", "bulb_warm", "awning_red"])),
                      lx - w / 2 + 0.25 + k * 0.28, ly + 0.25, lz + 0.3, radius=0.03)


def _awning(f, width, y, lz, color, depth=1.4):
    """A striped awning sloping down and out from the façade."""
    stripes = max(4, int(width / 0.45))
    sw = width / stripes
    steps = 4
    for st in range(steps):
        t = st / steps
        for i in range(stripes):
            col = color if i % 2 == 0 else "awning_cream"
            f.box((sw + 0.005, 0.17, depth / steps + 0.03), M(col), -width / 2 + sw * (i + 0.5), y - t * 0.5, lz + depth * (t + 0.5 / steps),
                  radius=0.02)
    for i in range(stripes):  # scalloped valance
        col = color if i % 2 == 0 else "awning_cream"
        f.box((sw, 0.28, 0.06), M(col), -width / 2 + sw * (i + 0.5), y - 0.5 - 0.22, lz + depth, radius=0.02)


def _shopfront(f, width, lz, shop, rng):
    kind, awning = shop["kind"], shop["awning"]
    win_w = (width - 2.4) / 2
    for side in (-1, 1):
        cx = side * (width / 4 + 0.35)
        f.box((win_w + 0.2, 2.3, 0.16), M("window_frame"), cx, 0.35, lz, radius=0.03)
        f.box((win_w, 2.1, 0.06), E("window_glass", 0.55), cx, 0.45, lz + 0.07, radius=0.02)
        f.box((win_w + 0.4, 0.35, 0.22), M("stone_trim"), cx, 0.0, lz + 0.06, radius=0.04)
        # Goods in the window.
        for k in range(int(win_w / 0.5)):
            f.box((0.3, 0.25, 0.2), M(rng.choice([SHOP_ICON.get(kind, "pot_cream"), "pot_cream", "wood_light"])),
                  cx - win_w / 2 + 0.35 + k * 0.5, 0.7, lz + 0.18, radius=0.05)
    f.box((1.3, 2.5, 0.18), M("window_frame"), 0, 0.0, lz, radius=0.03)
    f.box((1.05, 2.3, 0.08), M("door_wood"), 0, 0.0, lz + 0.08, radius=0.03)
    f.box((0.6, 0.9, 0.04), E("window_glass", 0.5), 0, 1.2, lz + 0.13, radius=0.02)
    f.box((0.08, 0.08, 0.08), M("bulb_warm", metallic=0.6), 0.38, 1.1, lz + 0.16, radius=0.02)
    _awning(f, width - 0.6, 3.05, lz + 0.05, awning)
    # A lit block-letter sign above the awning.
    word = {"bookshop": "BOOKS", "bakery": "BAKERY", "flowers": "FLOWERS", "deli": "DELI"}.get(kind, "SHOP")
    px = min(0.12, (width - 1.0) / (len(word) * 5 + 3))
    sign_text(f, word, 0, 3.3, lz + 0.05, px=px)


def building(ctx, x0, z0, x1, z1, floors, style, roof="flat", shop=None, seed=0, facing="z", annex_below=False, **_):
    rng = random.Random(seed)
    if facing == "z":
        f = Frame(ctx, (x0 + x1) / 2, (z0 + z1) / 2, 0.0)
        width, depth = x1 - x0, z1 - z0
    else:  # front faces +x: local +z maps to world +x
        f = Frame(ctx, (x0 + x1) / 2, (z0 + z1) / 2, PI / 2)
        width, depth = z1 - z0, x1 - x0
    height = GROUND_H + FLOOR_H * (floors - 1)
    front = depth / 2
    wall = STYLE_WALL.get(style, style)
    is_brick = style.startswith("brick")
    f.box((width, height, depth), M(wall), 0, 0, 0, radius=0.08)
    shutters = None if is_brick else rng.choice(["awning_green", "window_frame", "pot_cream", "awning_blue"])

    # Ground floor.
    if annex_below:
        # The café's interior back wall: warm plaster with wood panelling.
        f.box((width - 0.2, GROUND_H - 0.2, 0.06), M("plaster_cream"), 0, 0.1, front + 0.02, radius=0.02)
        f.box((width - 0.2, 1.0, 0.1), M("wood_mid"), 0, 0.0, front + 0.05, radius=0.02)
        f.box((width - 0.2, 0.08, 0.14), M("wood_dark"), 0, 1.0, front + 0.06, radius=0.02)
    elif shop:
        _shopfront(f, width, front, shop, rng)
    else:
        for k in range(int(width / 2.6)):
            _window(f, -width / 2 + 1.3 + k * 2.6, 1.0, front, rng, 0.5, shutters, h=1.4)

    # Upper floors.
    if is_brick:
        _bricks(f, width - 0.1, height - GROUND_H, GROUND_H, front + 0.02, rng, light=style == "brick_light")
    columns = max(1, int(width / 2.5))
    spacing = width / columns
    for fl in range(1, floors):
        y = GROUND_H + (fl - 1) * FLOOR_H
        f.box((width + 0.12, 0.16, 0.22), M("stone_trim"), 0, y - 0.08, front + 0.04, radius=0.04)
        for k in range(columns):
            _window(f, -width / 2 + spacing * (k + 0.5), y + 0.9, front + 0.06, rng, 0.45, shutters)
    # Cornice.
    f.box((width + 0.3, 0.35, 0.4), M("stone_trim"), 0, height - 0.35, front + 0.05, radius=0.06)
    f.box((width + 0.1, 0.2, depth + 0.1), M("stone_trim"), 0, height - 0.2, 0, radius=0.05)

    # Roof.
    top = height
    if roof == "flat":
        for (sx, sz, lx, lz) in [(width, 0.3, 0, front - 0.15), (width, 0.3, 0, -front + 0.15),
                                 (0.3, depth, -width / 2 + 0.15, 0), (0.3, depth, width / 2 - 0.15, 0)]:
            f.box((sx, 0.6, sz), M("stone_trim"), lx, top, lz, radius=0.06)
        f.box((width - 0.6, 0.08, depth - 0.6), M("roof_gravel", roughness=0.95), 0, top, 0, radius=0.01)
        for _k in range(rng.randint(2, 4)):
            lx, lz = rng.uniform(-width / 2 + 1.2, width / 2 - 1.2), rng.uniform(-front + 1.2, front - 1.4)
            choice = rng.random()
            if choice < 0.4:
                f.box((1.0, 0.7, 0.8), M("metal_light", roughness=0.5), lx, top, lz, radius=0.06)
                f.box((0.6, 0.06, 0.6), M("metal_dark"), lx, top + 0.7, lz, radius=0.02)
            elif choice < 0.7:
                f.box((0.9, 1.3, 0.9), M("wood_mid"), lx, top, lz, radius=0.12)
                f.box((1.0, 0.12, 1.0), M("wood_dark"), lx, top + 1.3, lz, radius=0.04)
            else:
                f.box((1.4, 0.25, 1.0), E("window_glass", 0.8), lx, top, lz, radius=0.04)
        f.box((0.7, 1.4, 0.7), M("brick_b"), width / 2 - 1.0, top, -front + 0.9, radius=0.05)
        f.box((0.8, 0.15, 0.8), M("stone_trim"), width / 2 - 1.0, top + 1.4, -front + 0.9, radius=0.04)
    else:
        steps = 5
        for st in range(steps):
            sd = depth * (1 - st / steps)
            f.box((width + 0.2, 0.42, sd), M("roof_tile"), 0, top + st * 0.42, 0, radius=0.06)
        f.box((0.7, 2.6, 0.7), M("brick_b"), -width / 2 + 1.2, top, -front * 0.3, radius=0.05)
        for k in range(max(1, int(width / 3))):  # dormers
            lx = -width / 2 + 1.8 + k * 3.0
            if lx > width / 2 - 1.2:
                break
            f.box((1.2, 1.1, 1.0), M(wall), lx, top + 0.2, front - 0.9, radius=0.06)
            f.box((1.4, 0.2, 1.2), M("roof_tile"), lx, top + 1.3, front - 0.9, radius=0.05)
            f.box((0.6, 0.6, 0.05), E("window_glass", 1.5) if rng.random() < 0.5 else M("window_dark"), lx, top + 0.45,
                  front - 0.38, radius=0.02)


# ---------------------------------------------------------------- café annex
def cafe_annex(ctx, x0, z0, x1, z1, door, side_door=None, **_):
    rng = random.Random(21)
    f = Frame(ctx)
    tones = ["brick_a", "brick_b", "brick_c", "brick_a"]

    def brick_wall(ax0, az0, ax1, az1, height, gaps=()):
        horizontal = abs(ax1 - ax0) >= abs(az1 - az0)
        length = abs(ax1 - ax0) if horizontal else abs(az1 - az0)
        rows = int(height / 0.3)
        for r in range(rows):
            t = 0.31 if r % 2 else 0.0
            pos = t
            while pos < length - 0.05:
                seg = min(0.6, length - pos)
                centre = pos + seg / 2
                cx = ax0 + centre if horizontal else ax0
                cz = az0 if horizontal else az0 + centre
                world_c = cx if horizontal else cz
                if not any(g0 <= world_c <= g1 for g0, g1 in gaps):
                    size = (seg - 0.03, 0.27, 0.42) if horizontal else (0.42, 0.27, seg - 0.03)
                    f.box(size, M(rng.choice(tones)), cx, r * 0.3, cz, radius=0.03)
                pos += seg
        cap_len = length + 0.1
        if horizontal:
            f.box((cap_len, 0.12, 0.52), M("stone_trim"), (ax0 + ax1) / 2, rows * 0.3, (az0 + az1) / 2, radius=0.03)
        else:
            f.box((0.52, 0.12, cap_len), M("stone_trim"), (ax0 + ax1) / 2, rows * 0.3, (az0 + az1) / 2, radius=0.03)

    # Left wall: tall, its inner face visible from the camera.
    brick_wall(x0 + 0.25, z0, x0 + 0.25, z1, 2.7)
    # Front and right walls: cut away to half height so the room stays visible.
    brick_wall(x0, z1 - 0.25, x1, z1 - 0.25, 1.05, gaps=[(door[0] - 0.05, door[1] + 0.05)])
    side = [(-6.6, -5.4)] if side_door else []
    brick_wall(x1 - 0.25, z0, x1 - 0.25, z1, 1.05, gaps=side)
    # Corner piers, broken off at uneven heights (the cut-away look).
    for (px, pz, h) in [(x0 + 0.25, z1 - 0.25, 2.7), (x1 - 0.25, z1 - 0.25, 2.1), (x1 - 0.25, z0 + 0.3, 2.9),
                        (door[0] - 0.35, z1 - 0.25, 1.9), (door[1] + 0.35, z1 - 0.25, 1.6)]:
        f.box((0.6, h, 0.6), M("brick_b"), px, 0, pz, radius=0.05)
        f.box((0.4, 0.3, 0.4), M("brick_c"), px + 0.06, h, pz - 0.05, radius=0.04)
    # Doorstep and a hanging café sign.
    f.box((door[1] - door[0] + 0.4, 0.08, 0.7), M("stone_trim"), (door[0] + door[1]) / 2, 0.0, z1 + 0.1, radius=0.03)
    sx, sz = x1 - 0.25, z1 - 0.25
    f.box((0.08, 0.08, 0.9), M("metal_dark"), sx, 2.0, sz + 0.45, radius=0.02)
    f.box((0.12, 0.8, 0.8), M("wood_dark"), sx, 1.15, sz + 0.65, radius=0.05)
    f.box((0.16, 0.42, 0.36), M("pot_cream"), sx, 1.3, sz + 0.65, radius=0.06)       # cup
    f.box((0.17, 0.08, 0.3), M("wood_dark"), sx, 1.66, sz + 0.65, radius=0.03)       # coffee
    f.box((0.17, 0.2, 0.08), M("pot_cream"), sx, 1.4, sz + 0.88, radius=0.03)        # handle


def counter(ctx, x0, z0, x1, z1, **_):
    f = Frame(ctx)
    w, d = x1 - x0, z1 - z0
    f.box((w, 1.0, d), M("wood_dark"), (x0 + x1) / 2, 0, (z0 + z1) / 2, radius=0.05)
    n = int(w / 0.5)
    for k in range(n):
        f.box((0.38, 0.8, 0.05), M("wood_mid"), x0 + 0.25 + k * (w / n), 0.1, z1 + 0.02, radius=0.02)
    f.box((w + 0.12, 0.08, d + 0.14), M("counter_white", roughness=0.4), (x0 + x1) / 2, 1.0, (z0 + z1) / 2, radius=0.03)
    for k in range(4):  # cups and a tip jar
        f.box((0.12, 0.14, 0.12), M("pot_cream"), x1 - 0.5 - k * 0.25, 1.08, z1 - 0.25, radius=0.04)
    f.box((0.2, 0.26, 0.2), E("screen_glow", 0.6, base="metal_light"), x0 + 1.4, 1.08, z1 - 0.3, radius=0.04)


def espresso(ctx, x, z, **_):
    f = Frame(ctx, x, z)
    f.box((0.8, 0.5, 0.5), M("metal_light", roughness=0.25, metallic=0.8), 0, 1.08, 0, radius=0.06)
    f.box((0.7, 0.1, 0.45), M("metal_dark"), 0, 1.58, 0, radius=0.03)
    f.box((0.12, 0.08, 0.06), E("neon_teal", 3.0), -0.2, 1.4, 0.26, radius=0.02)
    f.box((0.12, 0.08, 0.06), E("awning_red", 3.0), 0.2, 1.4, 0.26, radius=0.02)
    for dx in (-0.18, 0.18):
        f.box((0.1, 0.1, 0.1), M("pot_cream"), dx, 1.12, 0.32, radius=0.03)


def pastry_case(ctx, x, z, **_):
    f = Frame(ctx, x, z)
    f.box((1.4, 0.06, 0.6), M("metal_light", metallic=0.6, roughness=0.3), 0, 1.08, 0, radius=0.02)
    for k in range(5):
        f.box((0.2, 0.12, 0.2), M(["leaf_autumn", "wood_light", "pot_terracotta", "neon_pink", "wood_light"][k]),
              -0.55 + k * 0.27, 1.14, 0.05, radius=0.06)
    f.box((1.4, 0.45, 0.04), E("window_glass", 0.5, base="counter_white"), 0, 1.14, 0.3, radius=0.02)
    f.box((1.4, 0.06, 0.6), M("metal_light", metallic=0.6, roughness=0.3), 0, 1.6, 0, radius=0.02)


def shelves(ctx, x0, x1, z, **_):
    rng = random.Random(5)
    f = Frame(ctx)
    for y in (1.55, 2.15):
        f.box((x1 - x0, 0.06, 0.3), M("wood_mid"), (x0 + x1) / 2, y, z + 0.15, radius=0.02)
        x = x0 + 0.2
        while x < x1 - 0.2:
            c = rng.choice(["pot_cream", "pot_terracotta", "awning_blue", "leaf_autumn", "chalk_line"])
            h = rng.choice([0.18, 0.24, 0.3])
            f.box((0.16, h, 0.16), M(c), x, y + 0.06, z + 0.15, radius=0.04)
            x += rng.uniform(0.22, 0.4)
    # A menu board above the shelves.
    f.box((2.4, 0.7, 0.06), M("chalk_black"), (x0 + x1) / 2, 2.5, z + 0.04, radius=0.03)
    for k in range(3):
        f.box((1.6 - k * 0.3, 0.05, 0.02), M("chalk_line"), (x0 + x1) / 2 - 0.2, 2.95 - k * 0.15, z + 0.08, radius=0.01)


def chalkboard(ctx, x, z, facing=PI / 2, **_):
    f = Frame(ctx, x, z, facing)
    f.box((2.2, 1.6, 0.1), M("wood_dark"), 0, 0.7, 0, radius=0.04)
    f.box((2.0, 1.4, 0.06), M("chalk_black", roughness=0.95), 0, 0.8, 0.05, radius=0.02)
    lines = [(1.4, 1.95, "chalk_line"), (1.1, 1.75, "chalk_line"), (0.8, 1.55, "neon_pink"), (1.3, 1.35, "chalk_line"),
             (0.6, 1.15, "neon_teal")]
    for (w, y, c) in lines:
        f.box((w, 0.06, 0.02), M(c), -0.2, y, 0.09, radius=0.01)
    for k, c in enumerate(["bulb_warm", "neon_teal", "neon_pink"]):  # sticky notes awaiting review
        f.box((0.24, 0.24, 0.02), M(c), 0.65, 1.8 - k * 0.32, 0.09, radius=0.02)


def rug(ctx, x0, z0, x1, z1, color="cushion_terracotta", **_):
    f = Frame(ctx)
    f.box((x1 - x0, 0.03, z1 - z0), M("pot_cream"), (x0 + x1) / 2, 0.0, (z0 + z1) / 2, radius=0.01)
    f.box((x1 - x0 - 0.3, 0.035, z1 - z0 - 0.3), M(color), (x0 + x1) / 2, 0.0, (z0 + z1) / 2, radius=0.01)


def laptop_table(ctx, x, z, outdoor=False, **_):
    rng = random.Random(int(x * 10 + z * 100))
    f = Frame(ctx, x, z)
    top = "wood_light" if not outdoor else "metal_dark"
    f.box((1.1, 0.06, 0.8), M(top), 0, 0.72, 0, radius=0.03)
    for (dx, dz) in [(-0.45, -0.3), (0.45, -0.3), (-0.45, 0.3), (0.45, 0.3)]:
        f.box((0.06, 0.72, 0.06), M("metal_dark"), dx, 0, dz, radius=0.02)
    # Laptop facing the seat behind the table (towards -z).
    f.box((0.42, 0.03, 0.3), M("metal_light", metallic=0.7, roughness=0.3), 0, 0.78, -0.12, radius=0.01)
    f.box((0.42, 0.3, 0.03), M("metal_light", metallic=0.7, roughness=0.3), 0, 0.8, 0.04, radius=0.01)
    f.box((0.38, 0.26, 0.012), E("screen_glow", 1.6), 0, 0.82, 0.02, radius=0.005)
    f.box((0.1, 0.12, 0.1), M("pot_cream"), 0.38, 0.78, -0.15, radius=0.03)
    if rng.random() < 0.5:
        f.box((0.12, 0.12, 0.12), M("pot_terracotta"), -0.4, 0.78, 0.2, radius=0.03)
        f.box((0.16, 0.16, 0.16), LEAF("leaf_a"), -0.4, 0.9, 0.2, radius=0.05)


def terrace_table(ctx, x, z, **_):
    laptop_table(ctx, x, z, outdoor=True)


def bar_stools(ctx, x0, x1, z, **_):
    f = Frame(ctx)
    n = int((x1 - x0) / 0.9)
    for k in range(n):
        x = x0 + 0.45 + k * 0.9
        f.box((0.08, 0.7, 0.08), M("metal_dark"), x, 0, z, radius=0.02)
        f.box((0.4, 0.08, 0.4), M("cushion_terracotta"), x, 0.7, z, radius=0.04)
        f.box((0.3, 0.04, 0.3), M("metal_dark"), x, 0.0, z, radius=0.01)


def chair(ctx, x, z, facing=0.0, empty=False, **_):
    f = Frame(ctx, x, z, facing)
    f.box((0.46, 0.06, 0.44), M("wood_mid"), 0, 0.38, 0, radius=0.02)
    for (dx, dz) in [(-0.18, -0.17), (0.18, -0.17), (-0.18, 0.17), (0.18, 0.17)]:
        f.box((0.05, 0.38, 0.05), M("metal_dark"), dx, 0, dz, radius=0.01)
    f.box((0.46, 0.5, 0.05), M("wood_mid"), 0, 0.44, -0.2, radius=0.02)


def armchair(ctx, x, z, facing=0.0, **_):
    f = Frame(ctx, x, z, facing)
    f.box((1.0, 0.45, 0.9), M("cushion_blue"), 0, 0, 0, radius=0.12)
    f.box((1.0, 0.6, 0.25), M("cushion_blue"), 0, 0.45, -0.32, radius=0.1)
    for side in (-1, 1):
        f.box((0.2, 0.35, 0.9), M("cushion_blue"), side * 0.45, 0.45, 0, radius=0.08)


def plant(ctx, x, z, size=1.0, **_):
    rng = random.Random(int(x * 31 + z * 17))
    f = Frame(ctx, x, z)
    f.box((0.55 * size, 0.5 * size, 0.55 * size), M("pot_terracotta"), 0, 0, 0, radius=0.06)
    for k in range(5):
        s = rng.uniform(0.35, 0.55) * size
        f.box((s, s, s), LEAF(rng.choice(["leaf_a", "leaf_b", "leaf_c"])), rng.uniform(-0.2, 0.2) * size,
              (0.5 + k * 0.22) * size, rng.uniform(-0.2, 0.2) * size, radius=0.08)


def wall_lamp(ctx, x, z, **_):
    f = Frame(ctx, x, z)
    f.box((0.1, 0.1, 0.3), M("metal_dark"), 0, 2.4, 0.15, radius=0.02)
    f.box((0.3, 0.25, 0.3), M("metal_dark"), 0, 2.15, 0.35, radius=0.05)
    f.box((0.2, 0.12, 0.2), E("lamp_glow", 6.0), 0, 2.06, 0.35, radius=0.04)


# ---------------------------------------------------------------- terrace
def string_lights(ctx, points, height=2.9, **_):
    f = Frame(ctx)
    for (ax, az), (bx, bz) in zip(points, points[1:]):
        length = math.hypot(bx - ax, bz - az)
        n = max(4, int(length / 0.45))
        for i in range(n + 1):
            t = i / n
            sag = 0.45 * 4 * t * (1 - t)
            x, z, y = ax + (bx - ax) * t, az + (bz - az) * t, height - sag
            f.box((0.05, 0.05, 0.05), M("metal_dark"), x, y + 0.02, z, radius=0.01)
            if 0 < i < n:
                f.box((0.11, 0.13, 0.11), E("bulb_warm", 5.0), x, y - 0.13, z, radius=0.04)


def light_post(ctx, x, z, height=3.0, **_):
    f = Frame(ctx, x, z)
    f.box((0.12, height, 0.12), M("metal_dark"), 0, 0, 0, radius=0.03)
    f.box((0.3, 0.1, 0.3), M("metal_dark"), 0, 0, 0, radius=0.03)


def flower_box(ctx, x, z, length=1.6, **_):
    rng = random.Random(int(x * 13 + z * 7))
    f = Frame(ctx, x, z)
    f.box((length, 0.5, 0.5), M("wood_mid"), 0, 0, 0, radius=0.05)
    f.box((length - 0.1, 0.06, 0.4), M("soil"), 0, 0.46, 0, radius=0.02)
    n = int(length / 0.22)
    for k in range(n):
        lx = -length / 2 + 0.15 + k * (length - 0.3) / max(1, n - 1)
        f.box((0.22, 0.24, 0.22), LEAF(rng.choice(["leaf_a", "leaf_b", "leaf_c"])), lx, 0.5, rng.uniform(-0.08, 0.08), radius=0.06)
        if rng.random() < 0.65:
            f.box((0.12, 0.12, 0.12), M(rng.choice(["neon_pink", "bulb_warm", "pot_cream", "awning_red"])), lx,
                  0.74, rng.uniform(-0.1, 0.1), radius=0.04)


def a_frame(ctx, x, z, facing=0.0, **_):
    f = Frame(ctx, x, z, facing)
    f.box((0.6, 0.9, 0.06), M("wood_dark"), 0, 0, 0.12, radius=0.02)
    f.box((0.5, 0.7, 0.03), M("chalk_black"), 0, 0.12, 0.16, radius=0.01)
    f.box((0.3, 0.04, 0.02), M("chalk_line"), 0, 0.6, 0.18, radius=0.01)
    f.box((0.2, 0.2, 0.02), M("leaf_autumn"), 0, 0.3, 0.18, radius=0.03)
    f.box((0.6, 0.9, 0.06), M("wood_dark"), 0, 0, -0.12, radius=0.02)


# ---------------------------------------------------------------- square
def _disc(f, r, h, mat, y, step=0.3):
    """A circle built from strips, a stepped pixel disc in the block style."""
    n = int(r * 2 / step)
    for i in range(n):
        zc = -r + step * (i + 0.5)
        w = 2 * math.sqrt(max(0.0, r * r - zc * zc))
        if w > 0.1:
            f.box((w, h, step + 0.01), mat, 0, y, zc, radius=0.01, segments=1)


def fountain(ctx, x, z, **_):
    f = Frame(ctx, x, z)
    r = 1.8
    n = 16
    for i in range(n):
        a = 2 * PI * i / n
        f.box((0.75, 0.6, 0.4), M("stone_trim"), math.sin(a) * r, 0, math.cos(a) * r, radius=0.06, yaw=a)
    _disc(f, 1.55, 0.06, M("water_deep", roughness=0.1), 0.4)
    _disc(f, 1.25, 0.04, M("water", roughness=0.05), 0.45)
    f.box((0.6, 1.1, 0.6), M("stone_trim"), 0, 0, 0, radius=0.08)
    f.box((1.3, 0.22, 1.3), M("stone_trim"), 0, 1.1, 0, radius=0.08)
    _disc(f, 0.5, 0.05, M("water"), 1.3, step=0.2)
    f.box((0.3, 0.6, 0.3), M("stone_trim"), 0, 1.3, 0, radius=0.05)
    f.box((0.18, 0.5, 0.18), E("water", 0.6), 0, 1.9, 0, radius=0.06)
    for i in range(4):
        a = PI / 4 + i * PI / 2
        f.box((0.12, 0.12, 0.12), E("water", 0.5), math.sin(a) * 0.75, 0.9, math.cos(a) * 0.75, radius=0.04)


def tree(ctx, x, z, size=1.0, variant=0, **_):
    rng = random.Random(int(x * 100 + z * 10 + variant))
    f = Frame(ctx, x, z)
    f.box((1.3 * size, 0.2, 1.3 * size), M("stone_trim"), 0, 0.0, 0, radius=0.05)
    f.box((1.0 * size, 0.06, 1.0 * size), M("soil"), 0, 0.12, 0, radius=0.02)
    trunk_h = 2.0 * size
    f.box((0.32 * size, trunk_h, 0.32 * size), M("trunk"), 0, 0, 0, radius=0.06)
    f.box((0.18 * size, 0.6 * size, 0.18 * size), M("trunk"), 0.3 * size, trunk_h * 0.7, 0, radius=0.04)
    greens = [["leaf_a", "leaf_b", "leaf_c"], ["leaf_b", "leaf_a", "leaf_c"], ["leaf_c", "leaf_autumn", "leaf_a"]][variant % 3]
    # A dark underside layer, then a bushy crown of overlapping lobes, lighter towards the top.
    for _k in range(6):
        s = rng.uniform(0.8, 1.1) * size
        f.box((s, s * 0.7, s), LEAF("leaf_dark"), rng.uniform(-0.9, 0.9) * size, trunk_h - 0.2 * size,
              rng.uniform(-0.9, 0.9) * size, radius=0.12, yaw=rng.uniform(0, PI / 2))
    for k in range(18):
        s = rng.uniform(0.6, 1.1) * size
        t = k / 17
        spread = (1.25 - 0.6 * t) * size
        ly = trunk_h + (0.1 + t * 1.9) * size
        tone = greens[2] if t > 0.7 else rng.choice(greens[:2])
        f.box((s, s * 0.85, s), LEAF(tone), rng.uniform(-spread, spread), ly, rng.uniform(-spread, spread), radius=0.12,
              yaw=rng.uniform(0, PI / 2))


def street_tree(ctx, x, z, **_):
    tree(ctx, x, z, size=0.9, variant=1)


def bench(ctx, x, z, facing=0.0, **_):
    f = Frame(ctx, x, z, facing)
    for k in range(3):
        f.box((1.7, 0.06, 0.13), M("wood_light"), 0, 0.42, -0.16 + k * 0.16, radius=0.02)
    for k in range(2):
        f.box((1.7, 0.13, 0.06), M("wood_light"), 0, 0.62 + k * 0.18, -0.26, radius=0.02)
    for side in (-0.7, 0.7):
        f.box((0.08, 0.42, 0.46), M("metal_dark"), side, 0, 0, radius=0.02)
        f.box((0.08, 0.5, 0.06), M("metal_dark"), side, 0.42, -0.26, radius=0.02)


def lamp_post(ctx, x, z, **_):
    f = Frame(ctx, x, z)
    f.box((0.4, 0.3, 0.4), M("metal_dark"), 0, 0, 0, radius=0.05)
    f.box((0.14, 3.4, 0.14), M("metal_dark"), 0, 0, 0, radius=0.04)
    f.box((0.5, 0.12, 0.5), M("metal_dark"), 0, 3.4, 0, radius=0.04)
    f.box((0.34, 0.45, 0.34), E("lamp_glow", 7.0), 0, 3.52, 0, radius=0.05)
    f.box((0.56, 0.14, 0.56), M("metal_dark"), 0, 3.97, 0, radius=0.06)
    f.box((0.2, 0.18, 0.2), M("metal_dark"), 0, 4.1, 0, radius=0.05)


def planter(ctx, x, z, **_):
    rng = random.Random(int(x * 9 + z * 3))
    f = Frame(ctx, x, z)
    f.box((1.2, 0.6, 1.2), M("stone_trim"), 0, 0, 0, radius=0.08)
    f.box((1.0, 0.05, 1.0), M("soil"), 0, 0.58, 0, radius=0.02)
    for _k in range(6):
        s = rng.uniform(0.35, 0.55)
        f.box((s, s, s), LEAF(rng.choice(["leaf_a", "leaf_b", "leaf_c"])), rng.uniform(-0.3, 0.3), 0.62, rng.uniform(-0.3, 0.3), radius=0.08)
    for _k in range(5):
        f.box((0.14, 0.14, 0.14), M(rng.choice(["neon_pink", "bulb_warm", "pot_cream"])), rng.uniform(-0.4, 0.4), 0.95,
              rng.uniform(-0.4, 0.4), radius=0.04)


def _bike(f, lx, color):
    for dz in (-0.45, 0.45):
        f.box((0.06, 0.62, 0.62), M("metal_dark"), lx, 0.0, dz, radius=0.28, segments=3)
    f.box((0.06, 0.06, 0.9), M(color), lx, 0.42, 0, radius=0.02)
    f.box((0.06, 0.4, 0.06), M(color), lx, 0.3, -0.15, radius=0.02)
    f.box((0.16, 0.06, 0.22), M("wood_dark"), lx, 0.72, -0.15, radius=0.02)
    f.box((0.4, 0.05, 0.05), M("metal_dark"), lx, 0.8, 0.38, radius=0.02)
    f.box((0.06, 0.4, 0.06), M(color), lx, 0.42, 0.38, radius=0.02)


def bike_rack(ctx, x, z, count=3, **_):
    f = Frame(ctx, x, z)
    f.box((count * 0.7 + 0.4, 0.06, 0.06), M("metal_light", metallic=0.7), 0, 0.5, 0, radius=0.02)
    for k in range(count):
        lx = -count * 0.35 + 0.35 + k * 0.7
        f.box((0.05, 0.5, 0.05), M("metal_light", metallic=0.7), lx, 0, 0, radius=0.02)
        _bike(f, lx, ["awning_red", "leaf_c", "awning_blue"][k % 3])


def market_stall(ctx, x, z, facing=0.0, color="awning_green", **_):
    rng = random.Random(4)
    f = Frame(ctx, x, z, facing)
    f.box((2.6, 0.9, 1.2), M("wood_mid"), 0, 0, 0, radius=0.05)
    for k in range(6):
        c = rng.choice(["awning_red", "leaf_autumn", "leaf_c", "neon_pink"])
        f.box((0.38, 0.22, 0.38), M("wood_light"), -1.0 + k * 0.4, 0.9, 0.1, radius=0.03)
        for j in range(3):
            f.box((0.12, 0.12, 0.12), M(c), -1.1 + k * 0.4 + j * 0.1, 1.12, 0.05 + (j % 2) * 0.1, radius=0.04)
    for (dx, dz) in [(-1.25, -0.55), (1.25, -0.55), (-1.25, 0.55), (1.25, 0.55)]:
        f.box((0.08, 2.3, 0.08), M("wood_dark"), dx, 0, dz, radius=0.02)
    for i in range(7):
        col = color if i % 2 == 0 else "awning_cream"
        f.box((0.42, 0.1, 1.5), M(col), -1.26 + i * 0.42, 2.3, 0, radius=0.03)


def crates(ctx, x, z, **_):
    f = Frame(ctx, x, z)
    for (lx, ly, lz, c) in [(0, 0, 0, "leaf_autumn"), (0.55, 0, 0.1, "awning_red"), (0.25, 0.45, 0.05, "leaf_c")]:
        f.box((0.5, 0.42, 0.42), M("wood_light"), lx, ly, lz, radius=0.03)
        for j in range(4):
            f.box((0.12, 0.12, 0.12), M(c), lx - 0.15 + (j % 2) * 0.3, ly + 0.4, lz - 0.08 + (j // 2) * 0.16, radius=0.04)


def phone_box(ctx, x, z, **_):
    f = Frame(ctx, x, z, -PI / 2)
    f.box((1.0, 2.5, 1.0), M("awning_red"), 0, 0, 0, radius=0.06)
    f.box((1.06, 0.3, 1.06), M("awning_red"), 0, 2.5, 0, radius=0.08)
    f.box((0.7, 1.4, 0.04), E("window_glass", 0.9), 0, 0.8, 0.51, radius=0.02)
    f.box((0.6, 0.12, 0.04), E("pot_cream", 1.2), 0, 2.3, 0.52, radius=0.02)


def car(ctx, x, z, facing=0.0, color="awning_blue", **_):
    f = Frame(ctx, x, z, facing)
    f.box((1.7, 0.6, 3.6), M(color, roughness=0.4), 0, 0.3, 0, radius=0.15)
    f.box((1.5, 0.55, 1.9), M(color, roughness=0.4), 0, 0.9, -0.2, radius=0.14)
    f.box((1.52, 0.4, 1.6), M("window_dark", roughness=0.15), 0, 0.98, -0.2, radius=0.08)
    for (dx, dz) in [(-0.78, 1.1), (0.78, 1.1), (-0.78, -1.1), (0.78, -1.1)]:
        f.box((0.26, 0.62, 0.62), M("metal_dark"), dx, 0.0, dz, radius=0.24, segments=3)
    for dx in (-0.55, 0.55):
        f.box((0.32, 0.16, 0.06), E("pot_cream", 2.5), dx, 0.62, 1.8, radius=0.03)
        f.box((0.32, 0.14, 0.06), E("awning_red", 2.0), dx, 0.62, -1.8, radius=0.03)
    f.box((1.74, 0.16, 0.12), M("metal_light", metallic=0.7), 0, 0.3, 1.8, radius=0.04)
    f.box((1.74, 0.16, 0.12), M("metal_light", metallic=0.7), 0, 0.3, -1.8, radius=0.04)


def cafe_sign(ctx, x, z, word="CAFE", y=3.75, **_):
    f = Frame(ctx, x, z, y=y)
    sign_text(f, word, 0, 0.0, 0.0, px=0.16, letters=E("bulb_warm", 2.6))
    for dx in (-1.6, 1.6):  # little lamps over the sign
        f.box((0.08, 0.3, 0.3), M("metal_dark"), dx, 1.15, 0.18, radius=0.02)
        f.box((0.22, 0.12, 0.2), E("lamp_glow", 4.0), dx, 1.05, 0.36, radius=0.03)


def review_board(ctx, x, z, facing=0.0, **_):
    """A standing pinboard where agents wait for your review."""
    rng = random.Random(9)
    f = Frame(ctx, x, z, facing)
    for dx in (-1.2, 1.2):
        f.box((0.12, 2.3, 0.12), M("wood_dark"), dx, 0, 0, radius=0.03)
        f.box((0.5, 0.08, 0.5), M("wood_dark"), dx, 0, 0, radius=0.02)
    f.box((2.3, 1.4, 0.1), M("wood_mid"), 0, 0.8, 0, radius=0.04)
    f.box((2.1, 1.2, 0.05), M("pot_cream"), 0, 0.9, 0.05, radius=0.02)
    for i in range(9):
        c = rng.choice(["bulb_warm", "neon_teal", "neon_pink", "awning_cream", "leaf_c"])
        f.box((0.32, 0.3, 0.02), M(c), -0.75 + (i % 3) * 0.75, 1.0 + (i // 3) * 0.36, 0.09, radius=0.02)
    sign_text(f, "REVIEW", 0, 2.25, 0.0, px=0.07, letters=E("awning_cream", 1.6))


def parasol_table(ctx, x, z, color="awning_red", **_):
    f = Frame(ctx, x, z)
    f.box((0.8, 0.05, 0.8), M("metal_dark"), 0, 0.72, 0, radius=0.02)
    f.box((0.08, 2.3, 0.08), M("metal_light", metallic=0.6), 0, 0, 0, radius=0.02)
    for (dx, dz, yaw) in [(0, -0.7, 0), (0, 0.7, PI), (-0.7, 0, PI / 2), (0.7, 0, -PI / 2)]:
        chair(ctx, x + dx, z + dz, facing=yaw)
    for i, (w, y) in enumerate([(2.2, 2.2), (1.5, 2.36), (0.8, 2.52)]):
        f.box((w, 0.12, w), M(color if i % 2 == 0 else "parasol_a"), 0, y, 0, radius=0.05)
    f.box((0.14, 0.14, 0.14), M("parasol_a"), 0, 2.66, 0, radius=0.04)
    f.box((0.12, 0.12, 0.12), M("pot_cream"), 0.18, 0.77, 0.1, radius=0.03)


def bin_(ctx, x, z, **_):
    f = Frame(ctx, x, z)
    f.box((0.5, 0.9, 0.5), M("bin_green"), 0, 0, 0, radius=0.08)
    f.box((0.56, 0.08, 0.56), M("metal_dark"), 0, 0.9, 0, radius=0.03)


def bollards(ctx, x0, x1, z, step=2.5, **_):
    f = Frame(ctx)
    x = x0
    while x <= x1:
        f.box((0.22, 0.8, 0.22), M("metal_dark"), x, 0, z, radius=0.06)
        f.box((0.24, 0.08, 0.24), M("pot_cream"), x, 0.65, z, radius=0.03)
        x += step


def crosswalk(ctx, x0, x1, z0, z1, **_):
    f = Frame(ctx)
    x = x0
    while x < x1:
        f.box((0.45, 0.02, z1 - z0), M("pot_cream"), x + 0.225, -0.09, (z0 + z1) / 2, radius=0.01)
        x += 0.9


def manhole(ctx, x, z, **_):
    f = Frame(ctx, x, z)
    _disc(f, 0.4, 0.012, M("manhole", roughness=0.7), -0.1, step=0.13)


def flower_buckets(ctx, x, z, **_):
    rng = random.Random(int(x * 3 + z))
    f = Frame(ctx, x, z)
    for k in range(4):
        lx = -0.9 + k * 0.6
        f.box((0.4, 0.45, 0.4), M("metal_light", metallic=0.5), lx, 0, 0, radius=0.06)
        for j in range(5):
            f.box((0.12, 0.12, 0.12), M(rng.choice(["neon_pink", "bulb_warm", "awning_red", "pot_cream"])),
                  lx + rng.uniform(-0.12, 0.12), 0.5 + rng.uniform(0, 0.25), rng.uniform(-0.12, 0.12), radius=0.04)
        f.box((0.3, 0.25, 0.3), LEAF("leaf_b"), lx, 0.42, 0, radius=0.06)


# ---------------------------------------------------------------- context ring
def _block_building(f, width, depth, floors, wall, rng, lit=0.3):
    height = 3.2 * floors
    f.box((width, height, depth), M(wall), 0, 0, 0, radius=0.1)
    cols = max(1, int(width / 2.4))
    for fl in range(floors):
        for k in range(cols):
            lx = -width / 2 + width / cols * (k + 0.5)
            if rng.random() < lit:
                f.box((1.0, 1.3, 0.06), E("window_glass", rng.choice([0.5, 0.8, 1.1])), lx, fl * 3.2 + 1.1, depth / 2 + 0.02, radius=0.02)
            else:
                f.box((1.0, 1.3, 0.06), M("window_dark"), lx, fl * 3.2 + 1.1, depth / 2 + 0.02, radius=0.02)
    f.box((width + 0.2, 0.3, depth + 0.2), M("stone_trim"), 0, height, 0, radius=0.06)
    if rng.random() < 0.5:
        f.box((1.0, 1.0, 1.0), M("metal_light"), rng.uniform(-width / 3, width / 3), height + 0.3, 0, radius=0.08)


def context_ring(ctx, seed=11, **_):
    rng = random.Random(seed)
    walls = ["plaster_cream", "plaster_blue", "plaster_rose", "plaster_sage", "brick_a", "stone_trim", "brick_c"]
    # Behind the back row: taller blocks.
    x = -40.0
    while x < 40:
        w = rng.uniform(6, 10)
        _block_building(Frame(ctx, x + w / 2, -24 - rng.uniform(0, 3)), w - 0.4, 10, rng.randint(4, 7), rng.choice(walls), rng)
        x += w
    # Left of the left row, facing +x.
    z = -18.0
    while z < 18:
        w = rng.uniform(6, 9)
        _block_building(Frame(ctx, -28 - rng.uniform(0, 2), z + w / 2, PI / 2), w - 0.4, 10, rng.randint(3, 5), rng.choice(walls), rng)
        z += w
    # Across the side street, facing -x.
    z = -30.0
    while z < 14:
        w = rng.uniform(6, 9)
        _block_building(Frame(ctx, 29 + rng.uniform(0, 2), z + w / 2, -PI / 2), w - 0.4, 10, rng.randint(2, 4), rng.choice(walls), rng)
        z += w
    # Foreground across the main street: low shops so they never block the square.
    x = -36.0
    while x < 26:
        w = rng.uniform(6, 9)
        _block_building(Frame(ctx, x + w / 2, 23, PI), w - 0.4, 9, 1, rng.choice(walls), rng, lit=0.7)
        x += w
    # Ground beyond the grid so nothing floats in the fog.
    f = Frame(ctx)
    f.box((120, 0.2, 120), M("asphalt", roughness=1.0), 0, -0.45, 0, radius=0.0)


BUILDERS = {
    "cobbles": cobbles, "planks": planks, "pavement": pavement, "road": road, "grass": grass,
    "building": building, "cafe_annex": cafe_annex, "counter": counter, "espresso": espresso,
    "pastry_case": pastry_case, "shelves": shelves, "chalkboard": chalkboard, "rug": rug,
    "laptop_table": laptop_table, "terrace_table": terrace_table, "chair": chair, "armchair": armchair,
    "plant": plant, "wall_lamp": wall_lamp, "string_lights": string_lights, "light_post": light_post,
    "flower_box": flower_box, "a_frame": a_frame, "fountain": fountain, "tree": tree, "street_tree": street_tree,
    "bench": bench, "lamp_post": lamp_post, "planter": planter, "bike_rack": bike_rack,
    "market_stall": market_stall, "crates": crates, "phone_box": phone_box, "car": car, "context_ring": context_ring,
    "cafe_sign": cafe_sign, "review_board": review_board, "parasol_table": parasol_table, "bin": bin_,
    "bollards": bollards, "crosswalk": crosswalk, "manhole": manhole, "flower_buckets": flower_buckets,
    "bar_stools": bar_stools,
}


def build_all(placements, collection):
    ctx = Context(collection)
    for p in placements:
        kind = p["kind"]
        BUILDERS[kind](ctx, **{k: v for k, v in p.items() if k != "kind"})
    return ctx


def is_emissive(material):
    return material is not None and material.name.startswith("emit_")

