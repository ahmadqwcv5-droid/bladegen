# Sprint 02 acceptance matrix

Measured on 2026-10-09 with OpenVSP 3.54.0 and cadquery-ocp/OpenCascade
7.9.3.1. Every value below comes from a fresh final STEP re-import; the
complete machine-readable records are in `docs/sprint02_validation/`.

| Requirement | Case A: 3 sections | Case B: 5 sections | Case C: 8 sections |
|---|---:|---:|---:|
| Root r/R | 0.25 | 0.20 | 0.18 |
| Validation stations | 12 | 11 | 26 |
| Solids / shells | 1 / 1 | 1 / 1 | 1 / 1 |
| Faces | 8 | 8 | 8 |
| Non-degenerate free edges | 0 | 0 | 0 |
| Closed shell / BRepCheck | PASS / PASS | PASS / PASS | PASS / PASS |
| Round-trip solid | PASS | PASS | PASS |
| Volume (mm³) | 28,910.418807 | 38,559.346223 | 35,725.270721 |
| Max chord error (mm) | 0.002337 | 0.004043 | 0.004573 |
| Max twist error (deg) | 0.001784 | 0.001591 | 0.001570 |
| Max reference-axis error (mm) | 0.000102 | 0.004526 | 0.004419 |
| Max TE error (mm) | 0.002046 | 0.016732 | 0.007775 |
| Control contour RMS max (mm) | 0.007393 | 0.014744 | 0.010843 |
| Control contour P95 max (mm) | 0.014322 | 0.029710 | 0.020239 |
| Control contour max (mm) | 0.016796 | 0.033974 | 0.024809 |
| Overall | PASS | PASS | PASS |

The separate NACA 0008 override build also passed. It requested effective
`t/c = 0.10`; measured values at its three explicit sections were 0.100074,
0.100107, and 0.100142. Its maximum TE error was 0.002047 mm, and its final
solid volume was 24,135.299077 mm³.

Acceptance thresholds were 0.05 mm chord, 0.05° twist, 0.05 mm reference
axis, and 0.020 mm TE error. Existing control/intermediate contour thresholds
were unchanged.
