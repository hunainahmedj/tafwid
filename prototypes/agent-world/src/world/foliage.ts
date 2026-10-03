/**
 * Foliage materials come from the kit's LEAF() helper: "leaf_" plus a leaf
 * palette key ("leaf_leaf_a"), kept by the bake as "leaf_leaf_a__<area>_lm".
 * Props that merely use a leaf colour (fruit, pastries) must not sway.
 */
export const isFoliage = (name: string) => name.startsWith("leaf_leaf_");
