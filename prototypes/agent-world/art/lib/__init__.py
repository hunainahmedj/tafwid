"""Shared helpers for Tafwid environment builds (run inside Blender 5.1).

Coordinates: layout data uses the runtime's Three.js convention (x right,
y up, z towards the viewer). `space.bl()` converts to Blender's Z-up frame;
the glTF exporter's Y-up conversion maps it back exactly.
"""
