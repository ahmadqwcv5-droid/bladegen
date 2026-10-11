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

## Final-section production gates

Canonical curve resolver tolerances remain: chord/rake/skew 0.005 mm, twist
0.002°, and thickness ratio 1e-5, verified at at least 5,001 locations. Final
section checks retain the historical chord/twist/reference-axis limits of
0.050 mm, 0.050°, and 0.050 mm respectively, plus a 0.020 mm physical
trailing-edge limit.

Contour policies have distinct names and purposes:

| Policy | RMS | P95 | Maximum | Runtime effect |
|---|---:|---:|---:|---|
| Production control-section gate | 0.030 mm | 0.060 mm | 0.120 mm | Required for each airfoil control station |
| Production intermediate-section gate | 0.050 mm | 0.100 mm | 0.200 mm | Required for planned intermediate stations |
| Imported-profile acceptance target | 0.020 mm | 0.040 mm | 0.050 mm | Additional qualification result for coordinate-profile fixtures; not a universal runtime gate |

The constants are defined once in `bladegen.validation.policy`. Final section
records name their applicable production policy. Coordinate control stations
also report the additional imported-profile acceptance result separately.
Production pass/fail remains governed by the historical production gates; the
stricter target is never presented as the same policy and is not silently
applied to unrelated sections.

Added root/tip caps are topology faces and are not silently mixed into
inherited-surface fidelity metrics.

Section stations are never selected from a historical fixture. The planner
uses every submitted airfoil station, every adjacent airfoil midpoint, and all
independent chord/twist/rake/skew/thickness controls, deduplicated
deterministically. Root and tip values are checked on inward cap-safe planes;
the result records requested radius, sampled radius, and offset. Expected
geometry is evaluated at the sampled radius, while inferred endpoint values are
reported separately from direct measurements.

For NACA sections, the neutral resolver constructs coordinates at the explicit
effective thickness before OpenVSP receives them. Finite TE thickness remains a
physical millimetre requirement and is independently measured from the final
re-imported STEP. A thickness override therefore cannot pass solely because it
was accepted by the schema.

## Coordinate-density advisories

Coordinate profiles are screened before generation using embedded neutral
coordinates. Fewer than 25 points on either surface, maximum adjacent x/c
spacing above 0.10, or fewer than three points at x/c <= 0.10 on either surface
produce a non-blocking warning. These conservative heuristics do not prove CAD
accuracy and do not change, resample, smooth, or reject the supplied profile.
Final OCP section measurements remain authoritative.
