"""The café square, shared by both pipelines (pure data; no bpy).

Coordinates are layout/runtime units: x right, z towards the viewer, metres.
The camera looks from +x/+z, so tall buildings stand at the back (-z) and
left (-x); the foreground stays low.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.gridmap import GridMap  # noqa: E402

PI = math.pi

# The walkable/navigable footprint; the context ring extends beyond it.
GRID = dict(origin=(-22, -18), width=44, depth=36)

# Café annex: a single-storey cut-away room under the tall brick building.
ANNEX = dict(x0=-11, z0=-12, x1=4, z1=-4, door=(-1.5, 0.5), side_door=(-9.5, -7.5))
TERRACE = dict(x0=-11, z0=-4, x1=4, z1=0)
SQUARE = dict(x0=-16, z0=-4, x1=15, z1=9)

FOUNTAIN = (4.5, 4.0)

# Seats face the camera (+z) so faces stay readable from the default view.
INSIDE_TABLES = [(-7.5, -5.5), (-4.5, -5.5), (-1.5, -9.5), (1.5, -5.5)]
TERRACE_TABLES = [(-8.5, -1.5), (-5.5, -1.5), (-2.5, -1.5), (0.5, -1.5)]
# Desks are assigned in roster order; the most visible ones come first.
WORKSTATIONS = [(-4.5, -5.5), (1.5, -5.5), (-5.5, -1.5), (-2.5, -1.5), (0.5, -1.5), (-8.5, -1.5), (-7.5, -5.5), (-1.5, -9.5)]
REVIEW_BOARD = (6.5, -9.0)
BAKERY_TABLES = [(9.5, -9.5), (12.0, -7.0)]
SEAT_OFFSET = 0.85  # seats sit behind each table, facing the camera


def placements():
    p = []
    add = lambda kind, **kw: p.append(dict(kind=kind, **kw))  # noqa: E731

    # ---------------- Ground ----------------
    add("cobbles", x0=SQUARE["x0"], z0=SQUARE["z0"], x1=SQUARE["x1"], z1=SQUARE["z1"], seed=1)
    add("cobbles", x0=TERRACE["x0"], z0=TERRACE["z0"], x1=TERRACE["x1"], z1=TERRACE["z1"], seed=2)
    add("planks", x0=ANNEX["x0"] + 0.5, z0=ANNEX["z0"], x1=ANNEX["x1"] - 0.5, z1=ANNEX["z1"] - 0.5)
    add("cobbles", x0=-16, z0=-12, x1=-11, z1=-4, seed=3)     # alley left of the café
    add("pavement", x0=4, z0=-12, x1=15, z1=-4)               # shop fronts right of the café
    add("pavement", x0=-22, z0=9, x1=22, z1=11)          # near pavement
    add("road", x0=-30, z0=11, x1=30, z1=16)               # street across the front
    add("pavement", x0=-22, z0=16, x1=22, z1=18)           # far kerb (foreground)
    add("pavement", x0=15, z0=-12, x1=17, z1=9)            # right-hand pavement
    add("road", x0=17, z0=-30, x1=23, z1=11, axis="z")    # side street
    add("grass", x0=-22, z0=4, x1=-16, z1=9)

    # ---------------- Buildings (back row, facing +z) ----------------
    add("building", x0=-22, z0=-18, x1=-12, z1=-12, floors=3, style="plaster_blue", roof="flat",
        shop=dict(kind="bookshop", awning="awning_blue"), seed=3)
    add("building", x0=-12, z0=-18, x1=5, z1=-12, floors=4, style="brick", roof="flat", shop=None, seed=4,
        annex_below=True)
    add("building", x0=5, z0=-18, x1=13, z1=-12, floors=3, style="plaster_rose", roof="pitched",
        shop=dict(kind="bakery", awning="awning_red"), seed=5)
    add("building", x0=13, z0=-18, x1=17, z1=-12, floors=4, style="plaster_sage", roof="flat",
        shop=dict(kind="flowers", awning="awning_green"), seed=6)
    # Left row (facing +x)
    add("building", x0=-22, z0=-12, x1=-16, z1=-4, floors=3, style="brick_light", roof="pitched", facing="x",
        shop=dict(kind="deli", awning="awning_cream"), seed=7)
    add("building", x0=-22, z0=-4, x1=-17, z1=4, floors=2, style="plaster_cream", roof="flat", facing="x",
        shop=None, seed=8)

    # ---------------- Café annex ----------------
    add("cafe_annex", **ANNEX)
    add("counter", x0=-8.5, z0=-11.6, x1=-3.0, z1=-10.6)
    add("espresso", x=-7.6, z=-11.1)
    add("pastry_case", x=-5.2, z=-11.1)
    add("shelves", x0=-8.5, x1=-3.0, z=-11.9)
    add("chalkboard", x=-10.5, z=-8.5, facing=PI / 2)
    add("rug", x0=-6.5, z0=-10.2, x1=-2.5, z1=-8.0, color="cushion_terracotta")
    for (x, z) in INSIDE_TABLES:
        add("laptop_table", x=x, z=z)
        add("chair", x=x, z=z - SEAT_OFFSET, facing=0.0)
    add("armchair", x=2.6, z=-10.8, facing=PI * 0.75)
    add("plant", x=3.3, z=-4.7, size=1.0)
    add("plant", x=-10.4, z=-11.4, size=0.9)
    add("wall_lamp", x=-6.0, z=-11.95)
    add("wall_lamp", x=-1.0, z=-11.95)
    add("wall_lamp", x=2.5, z=-11.95)

    # ---------------- Terrace ----------------
    for (x, z) in TERRACE_TABLES:
        add("terrace_table", x=x, z=z)
        add("chair", x=x, z=z - SEAT_OFFSET, facing=0.0)
        add("chair", x=x + 0.75, z=z, facing=-PI / 2, empty=True)
    posts = [(-10.8, -3.8), (-7.0, -0.2), (-4.0, -3.8), (-1.0, -0.2), (2.0, -3.8), (3.8, -0.2)]
    add("string_lights", points=posts, height=2.9)
    for (x, z) in posts:
        add("light_post", x=x, z=z, height=3.0)
    for (x0, x1) in [(-11, -10), (-9, -5), (-4, 1), (2, 4)]:
        add("flower_box", x=(x0 + x1) / 2, z=0.5, length=x1 - x0 - 0.1)
    add("a_frame", x=-2.2, z=0.9, facing=0.5)

    # ---------------- Square ----------------
    add("fountain", x=FOUNTAIN[0], z=FOUNTAIN[1])
    for (x, z, s, v) in [(-13.5, 6.0, 1.3, 0), (12.5, -1.0, 1.2, 1), (-13.0, -2.0, 1.0, 2), (12.0, 7.0, 1.1, 0),
                         (-5.0, 7.6, 0.9, 1), (8.5, 8.2, 0.8, 2)]:
        add("tree", x=x, z=z, size=s, variant=v)
    for (x, z, f) in [(0.5, 4.0, PI / 2), (8.5, 4.0, -PI / 2), (-9.0, 5.5, 0.0), (-6.5, 5.5, 0.0)]:
        add("bench", x=x, z=z, facing=f)
    for (x, z) in [(-14.5, 1.5), (-1.5, 8.4), (10.5, 2.0), (14.4, 8.4), (6.0, -3.2)]:
        add("lamp_post", x=x, z=z)
    for (x, z) in [(-14.5, -3.4), (14.0, -3.4), (-10.5, 8.3), (1.5, 8.3)]:
        add("planter", x=x, z=z)
    # Shop fronts and kerbside life.
    add("cafe_sign", x=-3.5, z=-11.85)
    add("review_board", x=REVIEW_BOARD[0], z=REVIEW_BOARD[1], facing=0.0)
    for (x, z) in BAKERY_TABLES:
        add("parasol_table", x=x, z=z, color="awning_red")
    add("flower_buckets", x=14.6, z=-10.6)
    for (x, z) in [(4.6, -4.6), (14.6, 8.6), (-15.4, 8.6), (-15.4, -4.6)]:
        add("bin", x=x, z=z)
    add("bollards", x0=-14.0, x1=14.0, z=10.85, step=3.5)
    add("crosswalk", x0=2.0, x1=6.0, z0=11.3, z1=15.7)
    for (x, z) in [(-8.0, 13.5), (12.0, 13.0), (20.0, -2.0)]:
        add("manhole", x=x, z=z)
    for (x, z) in [(-12.5, -6.5), (-14.0, -10.0), (8.0, -5.0)]:
        add("plant", x=x, z=z, size=1.2)
    add("bike_rack", x=10.0, z=-2.6, count=3)
    add("market_stall", x=-10.0, z=2.2, facing=0.0, color="awning_green")
    add("crates", x=-12.0, z=2.0)
    add("phone_box", x=14.2, z=4.0)

    # ---------------- Street life (static) ----------------
    add("car", x=-15.0, z=12.3, facing=PI / 2, color="awning_blue")
    add("car", x=-6.0, z=12.3, facing=PI / 2, color="pot_cream")
    add("car", x=8.0, z=14.7, facing=-PI / 2, color="awning_red")
    add("car", x=19.0, z=-6.0, facing=0.0, color="leaf_autumn")
    for x in (-18, -10, -2, 6, 14):
        add("street_tree", x=x, z=17.2)

    # ---------------- Context ring (beyond the navigable area) ----------------
    add("context_ring", seed=11)
    return p


def build_grid():
    g = GridMap(origin=GRID["origin"], width=GRID["width"], depth=GRID["depth"])
    # Everything starts walkable; block buildings, the street edge and furniture.
    g.block_rect(-22, -18, 17, -12.01)                 # back row
    g.block_rect(-22, -12, -16.01, 4)                  # left row
    g.block_rect(-22, 4, -16.01, 9)                    # grass verge
    g.block_rect(-22, 11, 22, 18)                      # road and far pavement
    g.block_rect(17, -18, 22, 18)                      # side street
    # Annex walls, leaving the doors open.
    # Walls fill whole cells along the annex edges.
    g.block_rect(ANNEX["x0"], ANNEX["z0"], ANNEX["x0"] + 0.5, ANNEX["z1"])      # left wall
    g.block_rect(ANNEX["x1"] - 0.5, ANNEX["z0"], ANNEX["x1"], ANNEX["z1"])      # right wall
    g.block_rect(ANNEX["x0"], ANNEX["z1"] - 0.5, ANNEX["x1"], ANNEX["z1"])      # front wall
    g.open_rect(ANNEX["door"][0], ANNEX["z1"] - 0.5, ANNEX["door"][1], ANNEX["z1"])
    g.open_rect(ANNEX["x1"] - 0.5, -6.5, ANNEX["x1"], -5.5)                     # side door to the square
    # Furniture.
    g.block_rect(-8.5, -12, -3.0, -10.6)               # counter
    for (x, z) in INSIDE_TABLES + TERRACE_TABLES:
        g.block_footprint(x, z, 1.2, 0.9)
    g.block_footprint(REVIEW_BOARD[0], REVIEW_BOARD[1], 2.6, 0.6)
    for (x, z) in BAKERY_TABLES:
        g.block_footprint(x, z, 1.8, 1.8)
    g.block_footprint(14.6, -10.6, 2.4, 0.5)
    g.block_footprint(FOUNTAIN[0], FOUNTAIN[1], 4.2, 4.2)
    for (x, z) in [(-13.5, 6.0), (12.5, -1.0), (-13.0, -2.0), (12.0, 7.0), (-5.0, 7.6), (8.5, 8.2)]:
        g.block_footprint(x, z, 0.8, 0.8)
    g.block_footprint(-10.0, 2.2, 3.0, 1.6)            # market stall
    for (x0, x1) in [(-11, -10), (-9, -5), (-4, 1), (2, 4)]:   # flower boxes; gaps at -9.5, -4.5, 1.5
        g.block_rect(x0, 0.0, x1, 1.0)
    return g


def zones():
    ws = []
    for i, (x, z) in enumerate(WORKSTATIONS):
        ws.append({"id": "ws-%d" % (i + 1), "position": [x, 0.0, z - SEAT_OFFSET], "facing": 0.0, "pose": "seated"})
    review = [{"id": "review-board", "position": [REVIEW_BOARD[0], 0.0, REVIEW_BOARD[1] + 1.5], "facing": 0.0, "pose": "standing"}]
    fx, fz = FOUNTAIN
    loop = [[fx - 3.2, fz - 3.0], [fx + 3.2, fz - 3.0], [fx + 3.2, fz + 3.1], [fx - 3.2, fz + 3.1]]
    lounge = [{"id": "fountain", "position": [loop[0][0], 0.0, loop[0][1]], "facing": 0.0, "pose": "standing", "loop": loop}]
    return {"workstation": ws, "review": review, "lounge": lounge}


AMBIENT_PATHS = [
    {"id": "near-pavement", "kind": "pedestrian", "points": [[-21, 10], [21, 10]], "loop": False},
    {"id": "right-pavement", "kind": "pedestrian", "points": [[16, -11], [16, 8.5]], "loop": False},
    {"id": "across-square", "kind": "pedestrian", "points": [[-14.5, 8.5], [-2, 2], [9, -3.4], [14.5, -3.4]], "loop": False},
    {"id": "far-pavement", "kind": "pedestrian", "points": [[21, 17], [-21, 17]], "loop": False},
    {"id": "pigeons", "kind": "bird", "points": [[-6, 2], [6, -2], [12, 6], [0, 9], [-10, 6]], "loop": True},
    {"id": "swifts", "kind": "bird", "points": [[-18, -8], [10, -14], [20, 4], [-4, 14]], "loop": True},
]

CAMERA = {
    "home": {"target": [0.0, -2.5], "yaw": 0.62, "distance": 50},
    "bounds": {"minX": -16, "maxX": 16, "minZ": -13, "maxZ": 13},
    "zoom": [18, 78],
}

AMBIENCE = {
    # Golden hour: a low (~17°), amber sun from the front right; cool blue-violet fill so shadows read.
    "sun": {"direction": [0.82, 0.3, 0.48], "color": "#ffb37a", "intensity": 4.2},
    "hemisphere": {"sky": "#97aae0", "ground": "#7a6458", "intensity": 1.0},
    "fog": {"color": "#b8b6d4", "near": 75, "far": 190},
    "exposure": 1.0,
    "bloom": {"strength": 0.6, "radius": 0.45, "threshold": 0.0},
    "dof": {"focusOffset": 0.0, "range": 8.0, "strength": 2.4},
    "sky": {"top": "#6c90cf", "bottom": "#ffc48c"},
}


# Pipeline B bakes irradiance at this fraction of full energy for 8-bit headroom; the
# runtime multiplies it back via the material's tafwid_lightmap_scale.
LIGHTMAP_ENERGY = 0.5


def manifest(variant):
    g = build_grid()
    ambience = dict(AMBIENCE)
    return {
        "schema": "tafwid.environment/1",
        "id": "cafe",
        "variant": variant,
        "name": "Café on the square",
        "scene": "scene.glb",
        "lighting": "realtime" if variant == "kit" else "baked",
        "grid": g.manifest(),
        "zones": zones(),
        "ambientPaths": AMBIENT_PATHS,
        "camera": CAMERA,
        "ambience": ambience,
    }


if __name__ == "__main__":
    import json

    m = manifest("kit")
    print(json.dumps({"rows": m["grid"]["walkable"]}, indent=0)[:4000])
