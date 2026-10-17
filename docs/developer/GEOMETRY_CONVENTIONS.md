# Geometry conventions

- Units are millimetres and degrees. `R = diameter/2`; radial position is `+Y`.
- The local airfoil chord runs leading edge to trailing edge. `x/c=0` is LE and
  `x/c=1` is TE; `reference_axis_x_over_c` is the construction/pitch axis.
- Twist is the OpenVSP geometric pitch convention used by the validated engine;
  in the `X-Z` section plane the chord direction is `(sin β, cos β)`.
- Positive rake and skew map through the section transform documented in
  `validation/expected_geometry.py`; rake is axial and skew tangential. Rotation
  direction is `normal` or `reverse` without changing BladeSpec curve semantics.
- Airfoil-station and distribution-control radii are independent grids.
- Requested finite TE thickness is a physical chord-normal endpoint gap. The
  canonical profile is blended only aft of `x/c=0.85`. Validation sections the
  final CAD slightly inboard at the root (`r/R=0.203`) and tip (`0.9995`) to
  avoid caps; the inward cut measures the realised profile and may differ by up
  to 0.020 mm from the exact mathematical endpoint request.

## Full-propeller assembly

- Propeller axial rotation, hub-cylinder, and shaft-bore axes are global `X`.
- The reference blade is radial along `+Y`; at zero azimuth, `+Z` is tangential.
- Copy `i` is rotated by `initial_azimuth_deg + i * 360 / blade_count` with an
  exact OCP `gp_Trsf` about global X. Blade coordinates and distributions are
  not regenerated or altered for copies.
- The hub is centered at the origin and spans
  `X=-hub_length/2 ... +hub_length/2`. The bore cutter extends 2 mm beyond both
  hub ends to ensure a true through-cut without coincident end faces.
- A root connection requires measured common volume greater than `1e-5 mm³`.
  Pairwise blade common volume outside the hub must be at most `1e-5 mm³`.
  OCP Boolean fuzzy tolerance is explicitly `1e-7 mm`.
- The authoritative result is the re-imported assembly STEP: exactly one solid
  and shell, closed, BRep-valid, and zero non-degenerate free edges. The bore is
  independently checked by circular X-axis edges and zero common volume with
  an extended requested-diameter cutter.

See [Propeller assembly conventions](PROPELLER_ASSEMBLY_CONVENTIONS.md) for the
complete assembly contract and portability boundary.
