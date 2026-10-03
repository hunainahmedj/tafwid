"""Material cache. One Principled BSDF material per (name, colour, emission)."""

import bpy

from .palette import PALETTE, srgb_to_linear

_cache = {}


def get(name, color=None, roughness=0.85, emission=None, emission_strength=0.0, metallic=0.0):
    """Returns a material; `color` and `emission` accept palette keys or hex strings."""
    key = (name, color, roughness, emission, emission_strength, metallic)
    if key in _cache:
        return _cache[key]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    rgba = srgb_to_linear(PALETTE.get(color, color or "#cccccc"))
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if emission:
        bsdf.inputs["Emission Color"].default_value = srgb_to_linear(PALETTE.get(emission, emission))
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    mat.diffuse_color = rgba
    _cache[key] = mat
    return mat


def palette_material(key, **kwargs):
    """Shorthand: a material named and coloured after a palette key."""
    return get(key, key, **kwargs)
