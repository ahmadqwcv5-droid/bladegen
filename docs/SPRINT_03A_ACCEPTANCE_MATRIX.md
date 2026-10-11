# Sprint 03A acceptance matrix

Measured on 2026-10-11 with OpenVSP 3.54.0 and
cadquery-ocp/OpenCascade 7.9.3.1. CAD values come from fresh final STEP
re-imports during the 76-test backend run.

| Case | Solid / shell / free edges | Closed / BRep valid | Volume mm³ | Chord max mm | Twist max deg | Axis max mm | TE max mm | Contour max mm |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 sections | 1 / 1 / 0 | true / true | 28,910.418807 | 0.002337 | 0.001784 | 0.000102 | 0.002046 | 0.016796 |
| 5-section baseline | 1 / 1 / 0 | true / true | 38,559.346223 | 0.004043 | 0.001591 | 0.004526 | 0.016732 | 0.033974 |
| 8 sections | 1 / 1 / 0 | true / true | 35,725.270721 | 0.004573 | 0.001570 | 0.004419 | 0.007775 | 0.024809 |
| NACA 0008 effective t/c 0.10 | 1 / 1 / 0 | true / true | 24,135.299077 | 0.002337 | 0.001784 | 0.000102 | 0.002047 | 0.016613 |
| Imported analytic profile at r/R 0.60 | 1 / 1 / 0 | true / true | 38,264.318717 | 0.004043 | 0.001593 | 0.004526 | 0.016732 | 0.036200 |

All five cases passed unchanged limits: chord/axis `0.05 mm`, twist `0.05°`,
physical TE `0.020 mm`, control contour RMS `0.020 mm`, P95 `0.040 mm`, and
maximum `0.050 mm`. The largest STEP round-trip volume delta was
`6.985e-9 mm³`.

## Imported station fidelity

The committed profile is an independent analytic coordinate definition—not a
NACA-generated fixture—with 41 points per surface, natural max t/c
`0.1111737412` at x/c `0.3455`, max camber `0.0200000000` at x/c `0.5`, and
source TE gap `0.01 c`. Its source SHA-256 is
`48d1e0707bb40bc8d043fd45407c6746c38d7ce29aebb34dbf9979d347eea3c1`.

At final STEP r/R `0.60`, the imported station measured:

| Measurement | Result |
|---|---:|
| Max t/c | 0.111775820 |
| Max camber/c | 0.020142471 |
| Contour RMS / P95 / max | 0.014267 / 0.031276 / 0.036200 mm |
| Chord error | 0.001115 mm |
| Twist error | 0.000089° |
| Reference-axis error | 0.002432 mm |
| Physical TE error | 0.004368 mm |
| Section wire | valid and closed |

The resolved canonical TE operation produced exactly the requested `0.8 mm`
mathematically. The measured final profile stayed within the existing contour
gate and was not replaced by a NACA section or unexpectedly thickness-scaled.

## Feature verification

| Requirement | Evidence | Result |
|---|---|---:|
| DAT/CSV import and invalid rejection | 14 importer/library tests | PASS |
| Persistent registry and checksums | restart-style library test + real API | PASS |
| NACA canonical preview | NACA 4412/0012 exact-coordinate tests | PASS |
| Linear/PCHIP and physical units | 251-sample canonical comparisons | PASS |
| Source/resolved 2D inspector | RTL component and browser workflow | PASS |
| Search/select/cancel/import UI | RTL selector tests | PASS |
| Debounce/stale response protection | overlapping-response RTL test | PASS |
| Self-contained exported coordinates | browser export/re-import | PASS |
| Real imported-profile STEP | backend integration + Chromium workflow | PASS |
| Prior browser/CAD regressions | full backend and Playwright suites | PASS |
