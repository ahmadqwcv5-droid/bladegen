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
