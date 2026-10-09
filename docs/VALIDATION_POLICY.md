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
