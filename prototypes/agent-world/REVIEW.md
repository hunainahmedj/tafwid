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

## Round 2

| Criterion | A · kit | B · baked |
| --- | --- | --- |
| Ambience | 7 | 6 |
| Richness | 7 | 7 |
| Readability | 7 | 7 |
| Style | 7.5 | 8 |
| Technical | 6 | 5 |
| Performance | 9 | 9 |
| **Weighted total** | **7.2** | **6.9** |

Both variants were vsync-locked on every tier.

Findings:

- **Defects:** the parasols broke up into shards (overlapping coplanar
  slabs), manholes floated above the road, awnings leaked light between
  their stripes, and windows and shopfronts still blew out.
- **Baked lighting:** the baked runtime was darker than its Cycles
  reference. The cause was Three's basic lighting, which divides light
  maps by π.
- **Readability:** the "working" glyph rendered as a minus sign, Rex's
  beacon was too short, dashboard framing cropped agents, badges showed
  under HUD chips, and a passer-by trailed an agent.

Round-3 changes addressed all of these and added density: a second parasol
cluster, a second string of lights, bar stools and an extra café table.

## Round 3 (final)

| Criterion | A · kit | B · baked |
| --- | --- | --- |
| Ambience | 7 | 7 |
| Richness | 7 | 7 |
| Readability | 7.5 | 7 |
| Style | 7 | 8 |
| Technical | 7 | 7 |
| Performance | 9 | 9 |
| **Weighted total** | **7.3** | **7.4** |

Frame times, p50/p95 in ms:

| Tier | A · kit | B · baked |
| --- | --- | --- |
| High | 17.0 / 18.1 | 16.6 / 17.4 |
| Medium | 17.3 / 18.5 | 16.7 / 17.6 |
| Low | 16.7 / 17.2 | 16.7 / 17.4 |

Packages are 5.4 MB (kit) and 9.8 MB (baked).

**Outcome:** neither pipeline reached 8.0 within the three rounds the user
allowed, so iteration stopped. The 0.1 gap between them is within the
critics' variance. The practical trade-offs are in
[ADR-0006](../../docs/05-decisions/0006-scripted-blender-environment-packages.md),
and choosing between them is [TAF-8](../../docs/01-project/backlog.md).
The user then chose to ship the baked scenes and keep the kit for authoring
and a future scene builder
([ADR-0007](../../docs/05-decisions/0007-ship-baked-scenes-keep-the-kit.md)).

Final screenshots (our own renders, downscaled):

- [Kit, home view](evidence/kit-01-explore-home.jpg)
- [Baked, home view](evidence/baked-01-explore-home.jpg)
- [Kit, close-up](evidence/kit-02-explore-close.jpg)
- [Baked, follow mode](evidence/baked-05-follow-cleo.jpg)
- [Baked, dashboard mode](evidence/baked-06-dashboard.jpg)

## Remaining gaps (from the final critiques)

1. **Agent prominence.** Scale agents about 1.3× relative to props and
   enlarge the badge icons. Keep status rings clear of furniture, and cut
   the café front wall away further so the seated agents are fully visible.
2. **Life.** Add seated patrons at terrace and parasol tables, more
   passers-by, birds on roofs and the fountain rim, and steam from cups and
   the espresso machine. Fill the remaining empty cobbles.
3. **Golden hour.** Use a lower, warmer sun with a stronger key-to-fill
   ratio and longer shadows. Shadows should read cool against warm
   highlights without an overall salmon or purple cast. Add atmospheric
   haze at the edges, and for the bake, warm light pools under the lamps.
4. **Artefacts.** Make the CAFE sign legible and unobstructed. Rebuild the
   lamp heads as boxy lanterns so they stop clipping to white. Keep string
   lights off agent spots, and widen the focus band so the foreground stays
   readable.
5. **Style C consistency.** Use chunkier table legs and lamp posts, bevel the
   remaining flat slabs, and choose one foliage palette per tree. Give faces
   a mouth and brows so they read at the default zoom. In the baked variant,
   light characters from the local baked irradiance (a probe grid) and
   darken their contact shadows.
6. **Measurement.** Measure frame time with vsync off, so tier headroom is
   real data rather than 16.7 ms everywhere.
