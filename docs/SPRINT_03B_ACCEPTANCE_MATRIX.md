# Sprint 03B acceptance matrix

Measured on 2026-10-12 with OpenVSP 3.54.0 and
cadquery-ocp/OpenCascade 7.9.3.1. CAD values are from fresh final STEP re-imports
during the passing 92-test backend run.

## CAD non-regression

| Case | Solid / shell / free edges | Closed / BRep valid | Volume mm³ | Chord max mm | Twist max deg | Axis max mm | TE max mm | Contour RMS / P95 / max mm |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 sections | 1 / 1 / 0 | true / true | 28,910.418807 | 0.002337 | 0.001784 | 0.000102 | 0.002046 | 0.007393 / 0.014322 / 0.016796 |
| 5-section baseline | 1 / 1 / 0 | true / true | 38,559.346223 | 0.004043 | 0.001591 | 0.004526 | 0.016732 | 0.014744 / 0.029710 / 0.033974 |
| 8 sections | 1 / 1 / 0 | true / true | 35,725.270721 | 0.004573 | 0.001570 | 0.004419 | 0.007775 | 0.010843 / 0.020239 / 0.024809 |
| NACA 0008 effective t/c 0.10 | 1 / 1 / 0 | true / true | 24,135.299077 | 0.002337 | 0.001784 | 0.000102 | 0.002047 | 0.007248 / 0.014119 / 0.016613 |
| Imported analytic profile at r/R 0.60 | 1 / 1 / 0 | true / true | 38,264.318717 | 0.004043 | 0.001593 | 0.004526 | 0.016732 | 0.014744 / 0.031276 / 0.036200 |

All cases passed STEP round trip. The largest volume delta was
`6.985e-9 mm³`. Existing production gates were unchanged: chord/axis
`0.050 mm`, twist `0.050°`, physical TE `0.020 mm`, control-station contour
RMS/P95/max `0.030/0.060/0.120 mm`, and intermediate-station contour
`0.050/0.100/0.200 mm`. The imported profile also passed its separate
`0.020/0.040/0.050 mm` acceptance target.

## Feature acceptance

| # | Requirement | Evidence | Result |
|---:|---|---|---:|
| 1 | Every station selectable | Station-table RTL + Chromium station 3 | PASS |
| 2 | Stable insertion/deletion/edit identity | ID-preservation and deterministic-fallback RTL tests | PASS |
| 3 | Correct physical 3D Y | Pure D/r/R matrix + browser 120/40/160 mm assertions | PASS |
| 4 | No bounds-derived station position | Two radically different Box3 inputs retain Y=120 mm | PASS |
| 5 | Camera operations preserve guide | Face/Edge/Isometric/orbit/zoom/Fit/expand/resize Chromium sequence | PASS |
| 6 | Selection does not reload STL | Request counter remains 1 through all first-artifact interactions | PASS |
| 7 | 2D inspector follows selection | Stable ID/index and current-preview RTL assertions | PASS |
| 8 | Canonical two-station overlay | Real design-preview data path + source/resolved tests | PASS |
| 9 | Source/resolved remain distinct | Exact fixture polyline assertions and browser mode checks | PASS |
| 10 | Equal comparison scale | SVG `data-coordinate-scale=1:1` + meet aspect policy | PASS |
| 11 | Comparison does not edit BladeSpec | Snapshot/API-call RTL assertion | PASS |
| 12 | Imported coordinate comparison | Embedded-coordinate import and comparison RTL test | PASS |
| 13 | No current guide on stale CAD | RTL success/edit and Chromium stale assertions | PASS |
| 14 | Successful matching CAD activates guide | Distinct revised job + second STL + restored dual coordinates | PASS |
| 15 | Failed build cannot relabel old CAD | Failed-B RTL job identity/disabled-guide test | PASS |
| 16 | Existing CAD regressions | 92 backend tests; five measured cases above | PASS |
| 17 | Frontend tests/build | 67/67; TypeScript/Vite build | PASS |
| 18 | Real Chromium acceptance | Focused two-build workflow 1/1; complete suite 7/7 in 11.9 min | PASS |
| 19 | Historical research unchanged | Git scope audit; no `00_research_archive` changes | PASS |

## Three.js lifecycle evidence

| Check | Evidence | Result |
|---|---|---:|
| Exact guide world coordinates | helper tests + DOM `data-world-y-mm` in Chromium | PASS |
| XZ plane / Y normal | buffer-normal assertions | PASS |
| Guide replacement disposal | spies on all six geometries/materials for two guides | PASS |
| No duplicate canvas/context proxy | one canvas before/after guide/view/expand changes | PASS |
| No STL reload on guide changes | network request counter | PASS |
| New artifact replaces old guide layer | second job, second STL request, restored guide coordinates | PASS |

## Evidence files

All screenshots were captured by the passing real-browser workflow:

- `docs/screenshots/sprint03b/single_station_3d.png`
- `docs/screenshots/sprint03b/two_comparison_stations_3d.png`
- `docs/screenshots/sprint03b/source_profile_comparison.png`
- `docs/screenshots/sprint03b/resolved_profile_comparison.png`
- `docs/screenshots/sprint03b/stale_cad_guides_hidden.png`
- `docs/screenshots/sprint03b/matching_new_cad_guides_restored.png`
