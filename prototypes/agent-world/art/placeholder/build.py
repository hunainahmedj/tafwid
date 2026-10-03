"""Placeholder environment: proves the build plumbing and the package contract."""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import materials, scene  # noqa: E402
from lib.blocks import bevel_box  # noqa: E402
from lib.gridmap import GridMap  # noqa: E402

out = scene.parse_out_dir()
scene.clear_scene()

W, D = 16, 12
grid = GridMap(origin=(-8, -6), width=W, depth=D)

floor = [materials.palette_material("tile_a"), materials.palette_material("tile_b")]
for col in range(W):
    for row in range(D):
        x, z = grid.centre(col, row)
        bevel_box((1, 0.3, 1), floor[(col + row) % 2], (x, -0.3, z), radius=0.05)

wall = materials.palette_material("plaster_cream")
for col in range(W):
    x, z = grid.centre(col, 0)
    bevel_box((1, 2.4, 1), wall, (x, 0, z))
for row in range(1, D):
    x, z = grid.centre(0, row)
    bevel_box((1, 2.4, 1), wall, (x, 0, z))
grid.block_rect(-8, -6, 8, -5.01)
grid.block_rect(-8, -6, -7.01, 6)

desk = materials.palette_material("wood_mid")
screen = materials.get("screen_glow", "screen", emission="screen_glow", emission_strength=2.0)
workstations = []
for i in range(6):
    x, z = -4.5 + (i % 3) * 3, -2.5 + (i // 3) * 3.5
    bevel_box((1.8, 0.1, 0.9), desk, (x, 0.75, z))
    bevel_box((0.8, 0.5, 0.06), screen, (x, 0.85, z - 0.3))
    for dx in (-0.8, 0.8):
        bevel_box((0.1, 0.75, 0.8), desk, (x + dx, 0, z), radius=0.03)
    grid.block_footprint(x, z, 1.8, 0.9)
    workstations.append({"id": "ws-%d" % (i + 1), "position": [x, 0, z + 1.0], "facing": math.pi, "pose": "seated"})

board = materials.palette_material("chalk_black")
bevel_box((2.2, 1.4, 0.1), board, (4.5, 0.6, -4.9))
review = [{"id": "review-1", "position": [4.5, 0, -3.5], "facing": math.pi, "pose": "standing"}]

loop = [[2.5, 2.5], [6.5, 2.5], [6.5, 4.5], [2.5, 4.5]]
lounge = [{"id": "lounge-1", "position": [2.5, 0, 2.5], "facing": 0, "pose": "standing", "loop": loop}]

for z in [w["position"] for w in workstations] + [r["position"] for r in review]:
    scene.add_zone_empty("z", "debug", z)

scene.export_glb(os.path.join(out, "package", "scene.glb"))
scene.write_manifest(
    os.path.join(out, "package", "manifest.json"),
    {
        "schema": "tafwid.environment/1",
        "id": "placeholder",
        "variant": "kit",
        "name": "Placeholder room",
        "scene": "scene.glb",
        "lighting": "realtime",
        "grid": grid.manifest(),
        "zones": {"workstation": workstations, "review": review, "lounge": lounge},
        "ambientPaths": [{"id": "walk-1", "kind": "pedestrian", "points": [[-6.5, 5.5], [7.5, 5.5]], "loop": True}],
        "camera": {
            "home": {"target": [0, 0], "yaw": 0.65, "distance": 32},
            "bounds": {"minX": -8, "maxX": 8, "minZ": -6, "maxZ": 6},
            "zoom": [14, 44],
        },
        "ambience": {
            "sun": {"direction": [-0.5, 0.75, 0.45], "color": "#ffe2bd", "intensity": 3.0},
            "hemisphere": {"sky": "#d6e6ff", "ground": "#8c7b6b", "intensity": 1.1},
            "fog": {"color": "#e9e2d8", "near": 45, "far": 110},
            "exposure": 1.0,
            "bloom": {"strength": 0.5, "radius": 0.4, "threshold": 0.9},
            "dof": {"focusOffset": 0, "range": 14, "strength": 0.6},
            "sky": {"top": "#9cc2ec", "bottom": "#f3e3cf"},
        },
    },
)
scene.preview_camera((0, 0), 0.65, 32)
scene.render_preview(os.path.join(out, "previews", "preview.png"))
print("TAFWID built placeholder")
