# Validation policy

CAD integrity and numerical integration are separate gates. A successful build
requires one OCP solid, one closed shell, zero non-degenerate free edges, and a
valid `BRepCheck_Analyzer` result before and after STEP export/re-import.

Volume is authoritative only from
`BRepGProp.VolumePropertiesGK_s` with adaptive 2-D Gauss–Kronrod integration,
relative tolerance `1e-9`, closed-shell filtering, and BSpline spans enabled.
The returned error estimate is recorded. The default fixed-rule result is kept
as a diagnostic because it overestimates this loft; it is never presented as
the production volume. Round-trip volume and bounding-box deltas are recorded.

Canonical curve resolver tolerances remain: chord/rake/skew 0.005 mm, twist
0.002°, and thickness ratio 1e-5, verified at at least 5,001 locations. Final
section checks use chord/twist/reference-axis 0.05, TE 0.020 mm, and the existing
control/intermediate contour thresholds. Added root/tip caps are topology faces
and are not silently mixed into inherited-surface fidelity metrics.
