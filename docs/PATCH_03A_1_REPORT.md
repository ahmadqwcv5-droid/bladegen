# Patch 03A.1 — Visual engineering accuracy report

Date: 2026-10-11

Branch: `patch/03a.1-visual-engineering-accuracy`
Base: reviewed Sprint 03A merge `4f52ff1cbf93badc03b3a6317115839e89071a0a`

## Result

**STRONG PASS.** Airfoil contours are legible without changing their engineering
coordinates, chart hover positions map through the rendered SVG into the plot
domain, CAD policies have distinct names and a single numerical source, sparse
coordinate profiles warn before generation, and all prior real CAD regressions
remain successful.

## Airfoil Inspector root cause and correction

The upper/lower polylines combined `vector-effect: non-scaling-stroke` with
`stroke-width: .004`. Non-scaling strokes are interpreted in screen space, so
Chromium rendered approximately `0.004 px`: the SVG elements existed but their
outlines were practically invisible.

Both surfaces now use a `2 px` non-scaling stroke. The chord/reference axis uses
`1 px`, grid lines use `0.75 px`, and LE/TE marker borders use `1 px`. Upper and
lower colors remain distinct. The SVG still uses the unmodified normalized
coordinates and `preserveAspectRatio="xMidYMid meet"`; Chromium checks confirmed
equal x/y CTM scale at desktop and 520 px viewport widths. There is no vertical
exaggeration, and the UI explicitly labels the plot `equal x/y scale`.

- [Before: ineffective 0.004 px contour](screenshots/patch03a1/before_invisible_contour.png)
- [After: visible NACA 4412 contour](screenshots/patch03a1/after_visible_naca_4412.png)
- [Narrow viewport](screenshots/patch03a1/narrow_visible_inspector.png)

Actual canonical NACA 0012, 2412, and 4412 profiles were exercised in Chromium.
Each source and resolved view had nonzero path length, computed `2 px` strokes,
and equal geometric axis scale. The 41-point imported finite-TE profile was also
checked in source and resolved form before its real build.

## Corrected hover mathematics

The prior handler normalized `clientX` against the complete rendered SVG width.
That incorrectly treated the left and right margins as data and did not account
for viewBox letterboxing.

The corrected handler performs:

1. Transform `(clientX, clientY)` through `getScreenCTM().inverse()` into SVG
   viewBox coordinates. A mathematically equivalent meet-letterbox fallback is
   used only where CTM APIs are unavailable.
2. Normalize only across the plot: `(svgX - 58) / (640 - 58 - 18)`.
3. Clamp the fraction to `[0, 1]` and map it into the backend sample domain
   `[first r/R, last r/R]`.
4. Select the nearest backend-provided canonical sample. JavaScript does not
   recalculate Linear or PCHIP engineering values.

Measured Chromium results:

| Case | Pointer position | Displayed result |
|---|---:|---:|
| PCHIP chord, desktop | left plot boundary | r/R 0.2000 |
| PCHIP chord, desktop | plot midpoint | r/R 0.6000 |
| PCHIP chord, desktop | right plot boundary | r/R 1.0000 |
| Linear chord, desktop | left / right boundaries | r/R 0.2000 / 1.0000 |
| Linear chord, 520 px viewport | left / right boundaries | r/R 0.2000 / 1.0000 |

Intermediate nearest-sample unit tests enforce at most half the local sample
spacing. Browser checks also confirmed physical units: Chord/Rake/Skew in mm,
Twist in degrees, and Thickness in `% t/c`.

- [Corrected canonical hover readout](screenshots/patch03a1/correct_hover_readout.png)

## CAD policy reconciliation

Production tolerances were not changed. `bladegen.validation.policy` is now the
single numerical source, and section result records identify the applied policy.

| Policy | RMS | P95 | Maximum | Meaning |
|---|---:|---:|---:|---|
| Production control-section gate | 0.030 mm | 0.060 mm | 0.120 mm | Historical required runtime gate |
| Production intermediate-section gate | 0.050 mm | 0.100 mm | 0.200 mm | Historical required runtime gate |
| Imported-profile acceptance target | 0.020 mm | 0.040 mm | 0.050 mm | Additional coordinate-fixture qualification; not universal |

Chord, twist, reference-axis, and physical-TE production limits remain
`0.050 mm`, `0.050°`, `0.050 mm`, and `0.020 mm`. Boundary tests cover exact
pass and `1e-12` above-threshold failure for every contour metric and policy.
The Sprint 03A matrix and report now state that the stricter imported target was
additional rather than the unchanged production gate.

## Coordinate-profile diagnostics

Diagnostics operate on embedded neutral coordinates, so library profiles and
standalone BladeSpec JSON receive identical treatment. A non-blocking warning
is produced when any of these conservative screening conditions hold:

- fewer than 25 points on either surface;
- maximum adjacent chordwise spacing greater than `0.10 c`;
- fewer than three points at `x/c <= 0.10` on either surface.

The warning reports upper/lower counts and maximum spacing in the selector,
selected-station inspector, and a design-wide summary before Generate. The
five-point fixture reports `5 / 5` and `0.2500 c`; the accepted 41-point fixture
has maximum spacing about `0.03923 c` and receives no warning. Diagnostics do
not insert, remove, reorder, smooth, refit, scale, or replace coordinates.
Final OCP measurements remain authoritative, and point count never guarantees
CAD fidelity.

- [Sparse-profile advisory](screenshots/patch03a1/sparse_profile_warning.png)

## Source changes

- Corrected inspector and chart rendering in `AirfoilInspector.tsx`,
  `DistributionChart.tsx`, and `sprint03a.css`.
- Added `airfoils/diagnostics.py` and surfaced its neutral-coordinate results
  through the registry and design-preview API.
- Added `validation/policy.py` and used it in final section measurement.
- Added unit, React, policy-boundary, Chromium, and real imported-CAD coverage.
- Updated validation, import, acceptance-matrix, historical report, and README
  wording without erasing the original sparse-profile failure evidence.

## Real CAD regression results

All results are from fresh STEP export, OCP solidification, re-import, and
independent section measurement in the 92-test backend run.

| Case | Solid / shell / free | Closed / valid | Volume mm³ | Max contour mm |
|---|---:|---:|---:|---:|
| 3 sections | 1 / 1 / 0 | true / true | 28,910.418807 | 0.016796 |
| 5-section baseline | 1 / 1 / 0 | true / true | 38,559.346223 | 0.033974 |
| 8 sections | 1 / 1 / 0 | true / true | 35,725.270721 | 0.024809 |
| NACA 0008 effective t/c 0.10 | 1 / 1 / 0 | true / true | 24,135.299077 | 0.016613 |
| Imported 41-point analytic profile | 1 / 1 / 0 | true / true | 38,264.318717 | 0.036200 |

The imported control station measured RMS `0.014267 mm`, P95 `0.031276 mm`,
and maximum `0.036200 mm`, passing both its production gate and the separate
stricter imported-profile acceptance target.

- [Accepted imported profile and validated STEP](screenshots/patch03a1/accepted_imported_step_pass.png)

## Verification

```text
./scripts/test_backend.sh
92 passed, 1 existing Starlette/httpx deprecation warning in 452.78 s

cd frontend && npm test -- --reporter=dot
12 files, 49 tests passed

cd frontend && npm run build
TypeScript/Vite passed; 35 modules transformed

cd frontend && npm run test:e2e
6 Chromium tests passed in 11.2 min
```

## Remaining limitations

- Coordinate-density diagnostics are screening heuristics and can produce false
  positives or false negatives; they intentionally do not claim CAD accuracy.
- Very small finite trailing-edge gaps still require sufficient display size or
  zoom to distinguish visually; no exaggeration is applied.
- The existing frontend bundle-size advisory and Starlette/httpx deprecation
  warning remain; neither affects geometry or this patch's acceptance.
