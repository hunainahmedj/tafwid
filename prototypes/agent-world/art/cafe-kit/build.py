"""Pipeline A: the café square from the modular kit, lit in real time at runtime."""

import os
import sys

ART = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ART)
sys.path.insert(0, os.path.join(ART, "cafe"))

import bpy  # noqa: E402

import layout  # noqa: E402
from kit import pieces  # noqa: E402
from lib import scene  # noqa: E402

out = scene.parse_out_dir()
scene.clear_scene()
collection = bpy.context.scene.collection
pieces.build_all(layout.placements(), collection)
for role, items in layout.zones().items():
    for z in items:
        scene.add_zone_empty(z["id"], role, z["position"])

objects = [o for o in bpy.data.objects if o.type == "MESH"]
meshes = {o.data.name for o in objects}
print("TAFWID objects=%d unique_meshes=%d" % (len(objects), len(meshes)))

scene.export_glb(os.path.join(out, "package", "scene.glb"), gpu_instances=True, draco=False)
scene.write_manifest(os.path.join(out, "package", "manifest.json"), layout.manifest("kit"))
cam = layout.CAMERA["home"]
scene.preview_camera(cam["target"], cam["yaw"], cam["distance"])
scene.render_preview(os.path.join(out, "previews", "preview.png"))
print("TAFWID built cafe-kit")
