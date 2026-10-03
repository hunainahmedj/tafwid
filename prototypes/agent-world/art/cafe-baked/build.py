"""Pipeline B: the café square as one scene with Cycles-baked lighting.

Same builders and layout as pipeline A, then:
  1. light the scene for golden hour (sun, sky, lamps and bulbs as real lights);
  2. join static geometry per area and unwrap a lightmap UV set;
  3. bake diffuse direct + indirect *irradiance* (no surface colour) per area on the GPU,
     at LIGHTMAP_ENERGY of full strength so 8-bit maps keep highlight headroom;
  4. give each area per-material `<material>__<area>_lm` copies that keep their palette
     colour and carry the lightmap in the emissive slot; the runtime multiplies them.
Emissive pieces (emit_*) stay separate and unbaked so they still bloom.
"""

import math
import os
import sys
import time

ART = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ART)
sys.path.insert(0, os.path.join(ART, "cafe"))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import layout  # noqa: E402
from kit import pieces  # noqa: E402
from lib import scene  # noqa: E402
from lib.palette import PALETTE, srgb_to_linear  # noqa: E402
from lib.space import bl  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def arg(name, default):
    return type(default)(ARGS[ARGS.index(name) + 1]) if name in ARGS else default


TEXELS_PER_METRE = arg("--texels", 18.0)
SAMPLES = arg("--samples", 384)
TILE = 11.0  # metres per bake area inside the grid

started = time.time()
out = scene.parse_out_dir()
scene.clear_scene()
scene.enable_gpu()
sc = bpy.context.scene
collection = sc.collection
placements = layout.placements()
pieces.build_all(placements, collection)


def log(msg):
    print("TAFWID [%5.1fs] %s" % (time.time() - started, msg), flush=True)


log("built %d objects" % len([o for o in bpy.data.objects if o.type == "MESH"]))

# ---------------------------------------------------------------- lighting
def rgb(key):
    return srgb_to_linear(PALETTE.get(key, key))[:3]


amb = layout.AMBIENCE
sun_dir = Vector(bl(*amb["sun"]["direction"])).normalized()
sun_data = bpy.data.lights.new("sun", "SUN")
E = layout.LIGHTMAP_ENERGY
sun_data.energy = 2.2 * E
sun_data.angle = math.radians(2.5)
sun_data.color = rgb(amb["sun"]["color"])
sun = bpy.data.objects.new("sun", sun_data)
sun.rotation_euler = sun_dir.to_track_quat("Z", "Y").to_euler()
collection.objects.link(sun)

world = bpy.data.worlds.new("sky")
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (*rgb(amb["hemisphere"]["sky"]), 1.0)
bg.inputs["Strength"].default_value = 0.42 * E
sc.world = world


def point(name, location, power, color, radius=0.1):
    data = bpy.data.lights.new(name, "POINT")
    data.energy = power * E
    data.color = rgb(color)
    data.shadow_soft_size = radius
    obj = bpy.data.objects.new(name, data)
    obj.location = bl(*location)
    collection.objects.link(obj)


for p in placements:
    k = p["kind"]
    if k == "lamp_post":
        point("lamp", (p["x"], 3.5, p["z"]), 140, "lamp_glow", 0.2)
    elif k == "wall_lamp":
        point("wall", (p["x"], 2.0, p["z"] + 0.45), 70, "lamp_glow", 0.15)
    elif k == "string_lights":
        pts = p["points"]
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            for t in (0.25, 0.5, 0.75):
                sag = 0.45 * 4 * t * (1 - t)
                point("bulb", (ax + (bx - ax) * t, p["height"] - sag - 0.15, az + (bz - az) * t), 18, "bulb_warm", 0.08)
# A warm fill over the café interior so the room glows.
area_data = bpy.data.lights.new("cafe_fill", "AREA")
area_data.energy = 260 * E
area_data.size = 8.0
area_data.size_y = 4.0
area_data.shape = "RECTANGLE"
area_data.color = rgb("lamp_glow")
area = bpy.data.objects.new("cafe_fill", area_data)
area.location = bl(-3.5, 3.2, -8.0)
collection.objects.link(area)

# Reference render of the lit scene before baking (what the bake should match), at full energy.
cam = layout.CAMERA["home"]
scene.preview_camera(cam["target"], cam["yaw"], cam["distance"])
sc.view_settings.exposure = math.log2(1 / E)
scene.render_preview(os.path.join(out, "previews", "reference.png"), engine="cycles", samples=96)
sc.view_settings.exposure = 0.0
log("reference render done")

# ---------------------------------------------------------------- group and join
GX0, GZ0 = layout.GRID["origin"]
GX1, GZ1 = GX0 + layout.GRID["width"], GZ0 + layout.GRID["depth"]


def area_of(obj):
    x, z = obj.location.x, -obj.location.y
    leafy = any(s.material and s.material.name.startswith("leaf_") for s in obj.material_slots)
    if not (GX0 <= x <= GX1 and GZ0 <= z <= GZ1) or max(obj.dimensions) > 60:
        return "context" + ("_leaf" if leafy else "")
    key = "a%d_%d" % (int((x - GX0) // TILE), int((z - GZ0) // TILE))
    return key + ("_leaf" if leafy else "")


groups = {}
for obj in list(bpy.data.objects):
    if obj.type != "MESH" or obj.name.startswith("zone:"):
        continue
    if any(pieces.is_emissive(s.material) for s in obj.material_slots):
        continue
    groups.setdefault(area_of(obj), []).append(obj)

baked_objects = []
for name, objs in sorted(groups.items()):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.make_single_user(type="SELECTED_OBJECTS", object=True, obdata=True)
    if len(objs) > 1:
        bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    joined.name = name
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    baked_objects.append(joined)
log("joined into %d areas" % len(baked_objects))

# ---------------------------------------------------------------- lightmap UVs
def surface_area(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    a = sum(f.calc_area() for f in bm.faces)
    bm.free()
    return a


images = {}
for obj in baked_objects:
    mesh = obj.data
    uv = mesh.uv_layers.new(name="Lightmap")
    mesh.uv_layers.active = uv
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004, area_weight=0.0, correct_aspect=True,
                             scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    texels = math.sqrt(surface_area(obj)) * TEXELS_PER_METRE * 1.5
    size = 256
    while size < texels and size < 4096:
        size *= 2
    img = bpy.data.images.new("lm_" + obj.name, size, size, alpha=False, float_buffer=False)
    img.colorspace_settings.name = "sRGB"
    images[obj.name] = img
log("unwrapped; lightmap sizes: %s" % ", ".join("%s=%d" % (k, v.size[0]) for k, v in images.items()))

# ---------------------------------------------------------------- bake
sc.render.engine = "CYCLES"
sc.cycles.device = "GPU"
sc.cycles.samples = SAMPLES
sc.cycles.use_adaptive_sampling = True
sc.render.bake.margin = 8
sc.render.bake.use_pass_direct = True
sc.render.bake.use_pass_indirect = True
sc.render.bake.use_pass_color = False

for obj in baked_objects:
    img = images[obj.name]
    # Point every material on this object at its lightmap as the active bake target.
    for slot in obj.material_slots:
        mat = slot.material
        nodes = mat.node_tree.nodes
        node = nodes.get("tafwid_bake") or nodes.new("ShaderNodeTexImage")
        node.name = "tafwid_bake"
        node.image = img
        nodes.active = node
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"DIRECT", "INDIRECT"}, margin=8, use_clear=True)
    log("baked %s (%d px)" % (obj.name, img.size[0]))

# Denoise each lightmap with the compositor's OpenImageDenoise (Blender 5 node-group compositor).
tree = bpy.data.node_groups.new("tafwid_denoise", "CompositorNodeTree")
tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
src = tree.nodes.new("CompositorNodeImage")
den = tree.nodes.new("CompositorNodeDenoise")
group_out = tree.nodes.new("NodeGroupOutput")
tree.links.new(src.outputs["Image"], den.inputs["Image"])
tree.links.new(den.outputs["Image"], group_out.inputs[0])
sc.compositing_node_group = tree
sc.render.use_compositing = True
sc.render.engine = "BLENDER_WORKBENCH"  # nothing to render; the compositor reads the image
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_depth = "8"
sc.view_settings.view_transform = "Standard"
lm_dir = os.path.join(out, "lightmaps")
os.makedirs(lm_dir, exist_ok=True)
for obj in baked_objects:
    img = images[obj.name]
    img.filepath_raw = os.path.join(lm_dir, "%s_raw.png" % obj.name)
    img.file_format = "PNG"
    img.save()
    src.image = img
    sc.render.resolution_x, sc.render.resolution_y = img.size
    sc.render.resolution_percentage = 100
    sc.render.filepath = os.path.join(lm_dir, "%s.png" % obj.name)
    try:
        bpy.ops.render.render(write_still=True)
        clean = bpy.data.images.load(sc.render.filepath)
        clean.colorspace_settings.name = "sRGB"
        images[obj.name] = clean
    except Exception as exc:  # keep the raw bake if denoising is unavailable
        log("denoise skipped for %s: %s" % (obj.name, exc))
log("denoised")

# ---------------------------------------------------------------- lightmapped materials and export
def lightmapped(source, area, image):
    """A copy of `source` that keeps its colour and carries the area lightmap as emission."""
    mat = bpy.data.materials.new("%s__%s_lm" % (source.name, area))
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    src_bsdf = source.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = src_bsdf.inputs["Base Color"].default_value if src_bsdf else source.diffuse_color
    bsdf.inputs["Roughness"].default_value = 1.0
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = image
    mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 1.0
    mat["tafwid_lightmap_scale"] = 1.0 / layout.LIGHTMAP_ENERGY
    return mat


for obj in baked_objects:
    mesh = obj.data
    for layer in [l for l in mesh.uv_layers if l.name != "Lightmap"]:
        mesh.uv_layers.remove(layer)
    image = images[obj.name]
    image.file_format = "WEBP"
    for slot in obj.material_slots:
        slot.material = lightmapped(slot.material, obj.name, image)

for o in [o for o in bpy.data.objects if o.type in ("LIGHT",)]:
    bpy.data.objects.remove(o)
for role, items in layout.zones().items():
    for z in items:
        scene.add_zone_empty(z["id"], role, z["position"])

scene.export_glb(os.path.join(out, "package", "scene.glb"), gpu_instances=True, draco=True, image_format="WEBP", image_quality=88)
scene.write_manifest(os.path.join(out, "package", "manifest.json"), layout.manifest("baked"))
log("built cafe-baked")
