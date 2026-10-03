"""Coordinate conversion between layout (Three.js, Y-up) and Blender (Z-up)."""


def bl(x, y, z):
    """Layout (x, y, z) with y up -> Blender (x, y, z) with z up."""
    return (x, -z, y)


def bl_size(sx, sy, sz):
    """Layout sizes (width x, height y, depth z) -> Blender dimensions."""
    return (sx, sz, sy)
