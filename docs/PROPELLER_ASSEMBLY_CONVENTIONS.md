# Propeller assembly conventions

Sprint 04A adds a second engineering operation without changing BladeSpec or the
validated single-blade pipeline.

```text
PropellerSpec v0.1
  ├── BladeSpec v0.2 ── existing build() ── validated blade_solid.step
  └── AssemblySpec  ── OCP assembly engine
                               ├── exact blade copies rotated about global X
                               ├── X-axis cylindrical hub
                               ├── measured positive-volume hub intersections
                               ├── blade/hub Boolean union
                               ├── coaxial through-bore cut
                               └── STEP export, re-import, and qualification
```

The Python engineering layer owns every authoritative transform and Boolean.
FastAPI validates transport data, starts the same serialized worker used for
blade builds, and serves allow-listed artifacts. React edits and submits the
neutral JSON contract; it never constructs assembly geometry.

## Axes and placement

- Lengths are millimetres and angles are degrees.
- The propeller rotation and shaft axes are global `+X`.
- The reference blade extends radially along global `+Y`.
- At zero azimuth, global `+Z` is tangential.
- Blade `i` is an exact transformed copy of the validated reference solid at
  `initial_azimuth_deg + i * 360 / blade_count`.
- OCP `gp_Trsf` rotations are applied to the solid; blade airfoil coordinates,
  twist, chord, rake, skew, and thickness are never regenerated per azimuth.

The hub is a cylinder from `X=-hub_length_mm/2` to
`X=+hub_length_mm/2`, centered at `Y=Z=0`. The shaft cutter is coaxial and
extends beyond both hub ends to avoid coincident Boolean end faces.

## Qualification rules

Before any job or reference-blade generation, the shared lightweight runtime
policy requires a blade count in 2, 3, 4. PropellerSpec continues to model the
versioned 2–8 contract range, but 5–8 are explicitly unsupported in this
release. The same capability tuple is used by API validation/submission, the
CLI pipeline, and the assembly builder, and is exposed to the UI.

The conservative nominal preflight computes root radius as diameter / 2 times
root-radius ratio and hub radius as hub diameter / 2, then requires hub radius
to be strictly greater than root radius. Equality is rejected. This is a
dynamic screening rule, not structural certification and not proof of a
successful Boolean. Changing hub length alone cannot close a radial gap. The
downstream measured checks below remain authoritative.

Each blade must have a positive-volume intersection with the uncut hub. Merely
touching is rejected. Pairwise blade intersections outside material already
inside the hub are rejected as unintended collisions. Fusion must yield one
valid solid before and after the bore cut. The final exported and re-imported
STEP must contain one closed, valid solid with zero non-degenerate free edges.

The bore is checked independently with an OCP cylinder slightly longer than the
assembly: common volume with the final solid must be negligible, and circular
bore-edge radii are measured after STEP re-import. Validation records requested
and actual placements, overlap/collision volumes, mass properties, topology,
and STEP round-trip deltas. Reference-blade validation remains a separate
section of the result.

## Reuse boundary

`bladegen.propeller_pipeline.build_propeller()` and the existing
`bladegen.pipeline.build()` accept explicit input/output paths and have no
FastAPI or React dependency. The CLI exposes both operations. A future desktop
shell can call either engine operation directly or retain the local API; no
desktop packaging choice is made in Sprint 04A.
