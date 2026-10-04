"""Bevelled block geometry, the basic unit of style C."""

import bmesh
import bpy

from .space import bl, bl_size

_mesh_cache = {}


def bevel_mesh(size, material, radius=0.06, segments=2):
    """A shared mesh datablock for a bevelled box of layout size (sx, sy, sz).

    Identical size and material reuse one mesh, so the glTF exporter can
    emit GPU instances. The box's origin is at its bottom centre.
    """
    sx, sy, sz = size
    r = max(0.0, min(radius, sx / 2.01, sy / 2.01, sz / 2.01))
    key = (round(sx, 4), round(sy, 4), round(sz, 4), round(r, 4), segments, material.name if material else None)
    if key in _mesh_cache:
        return _mesh_cache[key]
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bx, by, bz = bl_size(sx, sy, sz)
    bmesh.ops.scale(bm, vec=(bx, by, bz), verts=bm.verts)
    bmesh.ops.translate(bm, vec=(0, 0, bz / 2), verts=bm.verts)
    if r > 0.001:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=r, segments=segments, profile=0.5, affect="EDGES", clamp_overlap=True)
    mesh = bpy.data.meshes.new("box_%g_%g_%g_%s" % (sx, sy, sz, material.name if material else "none"))
    bm.to_mesh(mesh)
    bm.free()
    if material is not None:
        mesh.materials.append(material)
    _mesh_cache[key] = mesh
    return mesh


def place(mesh, location, rotation_y=0.0, scale=(1, 1, 1), collection=None, name=None):
    """Places an object sharing `mesh`; location is layout (x, y, z), rotation about the up axis."""
    obj = bpy.data.objects.new(name or mesh.name, mesh)
    obj.location = bl(*location)
    obj.rotation_euler = (0, 0, rotation_y)
    obj.scale = (scale[0], scale[2], scale[1])
    (collection or bpy.context.scene.collection).objects.link(obj)
    return obj


def bevel_box(size, material, location, radius=0.06, rotation_y=0.0, collection=None, name=None, segments=2):
    """One bevelled box with its bottom centre at the layout location."""
    return place(bevel_mesh(size, material, radius, segments), location, rotation_y, collection=collection, name=name)


def reset_cache():
    _mesh_cache.clear()
