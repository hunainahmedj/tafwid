# Prototype critique and verification

Date: 2026-09-30. Requested loop: at most five build–critique–improve rounds,
stopping at a score strictly greater than 8.5/10. Scores are the builder's
structured design judgment, not an objective quality certification.

## Fixed rubric

| Criterion | Weight | What it measures |
| --- | --- | --- |
| Visual craft | 30% | Intentional composition, role distinction, materials, scene framing |
| Information clarity | 25% | Work and attention are understandable; sample/stale data is honest |
| Interaction | 20% | Consistent selection, filters, scenarios, usable fallback |
| Accessibility and responsiveness | 15% | Keyboard operation, contrast, desktop/mobile fit, reduced motion |
| Lightweight and reliable execution | 10% | Local setup, rendering cost, failure isolation |

Functional failures block signoff regardless of the weighted score.

## Iteration record

| Round | Visual | Clarity | Interaction | Accessibility | Execution | Weighted score |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 7.7 | 8.2 | 8.0 | 7.5 | 8.5 | 7.94 |
| 2 | 8.4 | 8.6 | 8.6 | 8.0 | 8.2 | 8.41 |
| 3 | 8.6 | 9.0 | 9.0 | 8.8 | 9.0 | 8.86 |

Round 1 found washed-out materials, small low-contrast labels, and selected
agent details below the 1440×1000 desktop viewport. Round 2 strengthened
materials and typography and reduced wasted vertical space. It identified
clipping at the top of the room and incomplete failure isolation for scene
loading. Round 3 corrected camera framing, independently loaded the scene,
fixed contrast findings, and reduced unnecessary geometry and draw calls.
The threshold was crossed in round 3; no fourth or fifth design round was needed.

## Evidence

- 23 Playwright checks passed: 3 model checks and 10 browser checks each at
  desktop and mobile sizes. Coverage includes derived metrics, scenario
  transitions, selection/filter reconciliation, direct canvas picking after
  resizing, keyboard focus, unavailable/empty states, and rendering failure.
- Automated axe WCAG A/AA checks reported no violations in active, empty, and
  unavailable states on desktop and mobile. This does not replace a full
  assistive-technology audit.
- Visible Chromium walkthroughs at 1440×1000 and 390×844. The main desktop
  view includes the selected detail panel; mobile scrolls vertically without
  horizontal overflow. The unavailable snapshot and its longer task text
  were inspected separately. No page errors in the ordinary interaction pass.
- WebGL creation failure, context loss, and a failed scene-module download
  leave the roster usable. Reduced-motion preferences retain full usability.
- Production type check/build passed. Initial app JS is about 12.1 kB
  minified / 4.7 kB gzip; the separately loaded scene is about 549.8 kB /
  139.0 kB gzip. Vite reports its standard 500 kB chunk warning for the scene.
- A selection render reported 254 draw calls and 39,768 triangles, including
  the renderer's shadow work, versus 493 calls and 95,880 triangles before
  geometry simplification and batching. Rendering is event-driven, not a
  continuous animation loop. Temporary instrumentation was removed.
- Local dev server startup reported 74 ms. One warm local browser navigation
  reached DOMContentLoaded at approximately 24 ms. These are observations on
  the available machine, not network or low-end-device performance promises.
- The original Python baseline passed all 152 tests. No plugin runtime
  behavior was changed by this prototype.

[Desktop evidence](evidence/desktop.png) · [Mobile evidence](evidence/mobile.png)

## Limitations

Only Chromium was exercised. Four fictional agents and three fixed scenarios
are supported. Character identity, accepted-result state, real worker data,
and invitations are not implemented. Assets are procedural; Blender and
Higgsfield were not needed for this prototype. The room is static between
interactions to keep rendering inexpensive.
