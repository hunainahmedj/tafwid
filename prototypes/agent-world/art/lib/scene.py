"""Scene setup, glTF export, manifest writing and preview rendering."""

import json
import math
import os
import sys

import bpy

from .space import bl


def parse_out_dir():
    """Reads `--out <dir>` after Blender's `--` separator."""
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    out = argv[argv.index("--out") + 1] if "--out" in argv else os.path.join(os.getcwd(), "out")
    os.makedirs(os.path.join(out, "package"), exist_ok=True)
    os.makedirs(os.path.join(out, "previews"), exist_ok=True)
    return out


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def export_glb(path, gpu_instances=True, draco=False, image_format="AUTO", image_quality=90):
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        export_apply=True,
        export_yup=True,
        export_extras=True,
        export_gpu_instances=gpu_instances,
        export_draco_mesh_compression_enable=draco,
        export_draco_mesh_compression_level=6,
        export_cameras=False,
        export_lights=False,
        export_animations=False,
        export_materials="EXPORT",
        export_image_format=image_format,
        export_image_quality=image_quality,
    )


def write_manifest(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")


def add_zone_empty(zone_id, role, position):
    """Debug marker in the GLB; the runtime reads zones from the manifest only."""
    empty = bpy.data.objects.new("zone:%s:%s" % (role, zone_id), None)
    empty.empty_display_type = "ARROWS"
    empty.location = bl(*position)
    empty["tafwid_zone"] = role
    bpy.context.scene.collection.objects.link(empty)
    return empty


def preview_camera(target, yaw, distance, pitch=0.92, fov_deg=26):
    """A camera matching the runtime's home framing."""
    horizontal = math.cos(pitch) * distance
    pos = (target[0] + math.sin(yaw) * horizontal, math.sin(pitch) * distance, target[1] + math.cos(yaw) * horizontal)
    cam_data = bpy.data.cameras.new("preview")
    cam_data.angle_y = math.radians(fov_deg)
    cam_data.sensor_fit = "VERTICAL"
    cam_data.clip_end = 400
    cam = bpy.data.objects.new("preview", cam_data)
    cam.location = bl(*pos)
    bpy.context.scene.collection.objects.link(cam)
    target_empty = bpy.data.objects.new("preview_target", None)
    target_empty.location = bl(target[0], 0, target[1])
    bpy.context.scene.collection.objects.link(target_empty)
    track = cam.constraints.new("TRACK_TO")
    track.target = target_empty
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    bpy.context.scene.camera = cam
    return cam


def render_preview(path, engine="workbench", width=1600, height=900, samples=64):
    scene = bpy.context.scene
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = path
    if engine == "workbench":
        scene.render.engine = "BLENDER_WORKBENCH"
        scene.display.shading.light = "STUDIO"
        scene.display.shading.color_type = "MATERIAL"
        scene.display.shading.show_shadows = True
        scene.display.shading.show_cavity = True
    else:
        scene.render.engine = "CYCLES"
        scene.cycles.device = "GPU"
        scene.cycles.samples = samples
        scene.cycles.use_denoising = True
    bpy.ops.render.render(write_still=True)


def enable_gpu():
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "OPTIX"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == "OPTIX"
    bpy.context.scene.cycles.device = "GPU"
