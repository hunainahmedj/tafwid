# Agent world — bake-off critique record

The [spec](../../docs/superpowers/specs/2026-10-03-agent-world-design.md)
defines the rubric: ambience 25 %, richness 20 %, readability 20 %, style 15 %,
technical 10 %, performance 10 %. A pipeline is satisfactory at 8.0 or above,
with at most three critique rounds per pipeline.

Each round, a fresh critique agent reviews one pipeline. It sees six
screenshots (home, close, far, rotated, follow, dashboard), the user's four
reference images, the frame-time readings and the spec. The scores are an
agent's subjective judgement, recorded with their evidence. They are not
objective guarantees.

Frame times come from headless Chromium on the user's Apple M5 Max (WebGPU on
the Metal adapter), at a 1600×1000 viewport with device pixel ratio 2. A value
of 16.7 ms means the frame rate is locked to vsync. Evidence images live in
the gitignored `.critique/` folder because the reference images are not
ours to commit.

## Round 1

| Criterion | A · kit, real-time | B · scene, baked |
| --- | --- | --- |
| Ambience | 5 | 6 |
| Richness | 5 | 6 |
| Readability | 6 | 7 |
| Style | 6 | 7 |
| Technical | 6 | 5 |
| Performance | 3 | 9 |
| **Weighted total** | **5.3** | **6.6** |

The kit's frame times (43 ms at High) came from Blender's exporter leaving
6,230 separate meshes, which meant 10,732 draw calls. Grouping repeated pieces
into instanced meshes at load time brought the kit to a vsync-locked 60 fps.
That fix landed after the round-1 capture.

Shared findings:

- The grade was flat and hazy.
- Lit windows blew out to white.
- Rex's attention marker was a pale cube.
- Passers-by looked like agents.
- The square and pavements had empty stretches, and the trees were thin.
- The square fountain plane poked through the round rim.

The baked critique also found blotchy, low-resolution lightmaps and a runtime
image greyer than the Cycles reference. Both came from baking surface colour
into the lightmaps and then exposing them back up.

Round-2 changes:

- **Lighting:** a golden-hour grade with a lower amber sun and cool fill,
  then display-space contrast and saturation after AgX. Also stronger AO,
  a narrower tilt-shift band, and amber windows at lower intensity.
- **Agents and characters:** status ground rings, a red "!" beacon, muted and
  smaller passers-by, a lower camera pitch, closer follow framing, badge
  decluttering, and a dashboard layout that fills the page.
- **Props and signage:** block-letter signs, a pixel-disc fountain, bushier
  trees with dark undersides, and a parasol café, bins, bollards, a
  crosswalk and flower stall. The review board moved onto open pavement.
- **Pipeline B:** lightmaps now hold irradiance only, at half energy for
  8-bit headroom. The palette colours stay crisp per material, and the
  runtime multiplies the two.
