"""Style C palette. Colours are sRGB hex; materials convert to linear."""

PALETTE = {
    # Ground
    "cobble_a": "#b9a48f", "cobble_b": "#a8927c", "cobble_c": "#c7b39d", "cobble_grout": "#7d6c5e",
    "plank_a": "#c98f5a", "plank_b": "#b77e4b", "tile_a": "#efe5d4", "tile_b": "#d9c9b0",
    "asphalt": "#5b5660", "manhole": "#77747a", "kerb": "#c9c4bb", "grass": "#7fbf5a", "soil": "#7a5a3f",
    # Buildings
    "brick_a": "#b5553c", "brick_b": "#9e4632", "brick_c": "#c4654a", "mortar": "#d9c8b4",
    "plaster_cream": "#efe2c6", "plaster_sage": "#9fc3a5", "plaster_blue": "#9db8d6",
    "plaster_rose": "#e6b3a3", "stone_trim": "#ddd3c4", "roof_slate": "#4f566a", "roof_tile": "#a8543c",
    "window_frame": "#3d4a5c", "window_glass": "#ffb562", "window_dark": "#3a4a66", "roof_gravel": "#9a928b",
    "door_wood": "#6e4227", "awning_red": "#d24b3e", "awning_cream": "#f5ead2",
    "awning_green": "#3f8f6b", "awning_blue": "#3d6fb3",
    # Interior and props
    "wood_light": "#d6a671", "wood_mid": "#b07a48", "wood_dark": "#7a4e2d", "metal_dark": "#3a3f4b",
    "metal_light": "#b8bec9", "counter_white": "#f2efe8", "chalk_black": "#2b3330", "chalk_line": "#eef2ee",
    "cushion_blue": "#4263eb", "cushion_terracotta": "#c8673f", "screen": "#25334d", "screen_glow": "#8fd3ff",
    "pot_terracotta": "#d0794f", "pot_cream": "#efe6d5",
    # Nature
    "leaf_a": "#5fb35a", "leaf_b": "#4a9c4c", "leaf_c": "#7cc764", "leaf_dark": "#357f45", "leaf_autumn": "#e0a43a",
    "sign_board": "#2b2f3a", "parasol_a": "#f2e3c6", "bin_green": "#3f6b55",
    "trunk": "#6b4a32", "water": "#6fc3df", "water_deep": "#3f9cc0",
    # Lights
    "bulb_warm": "#ffcf7a", "lamp_glow": "#ffd28a", "neon_pink": "#ff6fae", "neon_teal": "#4fe3d4",
}


def srgb_to_linear(hex_color):
    hex_color = hex_color.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(hex_color[i : i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (out[0], out[1], out[2], 1.0)
