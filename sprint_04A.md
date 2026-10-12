# SPRINT 04A — BladeGen Full Propeller Assembly MVP

## Repository

https://github.com/ahmadqwcv5-droid/bladegen

## Mission

Extend the existing BladeGen application from a validated single-blade CAD generator into a parametric full-propeller generator.

The engineer must be able to design one blade, specify the number of blades and basic hub parameters, generate a complete propeller, inspect it in the existing 3D viewer, and export one validated solid STEP file.

**Continue developing the current React + FastAPI + Python application. Do not create a separate application or a desktop program.**

Design the new engineering modules so they can be reused in a future desktop application without rewriting the geometry engine.

This is the first full-propeller assembly sprint. Manufacturing refinements, aerodynamic performance, and advanced hub features are outside its scope.

---

# PART A — PROJECT PREPARATION

## 1. Inspect the current repository

Inspect the actual workspace, Git status, and current branch.

The last reviewed main commit was:

`f9edf964427e4f25c2b27be93b1fdc754d792ade`

Confirm the current HEAD before proceeding.

Create a branch:

`sprint/04a-full-propeller-assembly`

Preserve any uncommitted changes.

Do not modify `00_research_archive`.

Do not automatically merge into `main`.

## 2. Preserve existing BladeGen functionality

The project already implements:

- BladeSpec v0.2.
- Dynamic radial airfoil stations.
- Canonical NACA and imported coordinate airfoils.
- Chord, Twist, Rake, Skew and Thickness distributions.
- Physical trailing-edge thickness.
- Canonical SciPy PCHIP resolution.
- OpenVSP geometry generation.
- OCP solidification.
- Independent final-STEP validation.
- An expandable Three.js viewer.
- Job progress and artifact downloads.
- Airfoil Library and engineering preview tools.

All of these must remain available.

The existing single-blade generator must continue working.

The single-blade pipeline must not be rewritten to implement the assembly.

## 3. Important source files

Inspect at minimum:

- `backend/bladegen/models/blade_spec.py`
- `backend/bladegen/models/__init__.py`
- `backend/bladegen/pipeline.py`
- `backend/bladegen/solid/ocp_solidify.py`
- `backend/bladegen/validation/expected_geometry.py`
- `backend/bladegen/validation/measure_sections.py`
- `backend/bladegen/cli.py`
- `backend/api/services/jobs.py`
- `backend/api/routes/blades.py`
- `backend/api/schemas/responses.py`
- `frontend/src/App.tsx`
- `frontend/src/components/BladeViewer.tsx`
- `frontend/src/types/bladespec.ts`
- `frontend/src/api/client.ts`
- `docs/GEOMETRY_CONVENTIONS.md`
- `docs/ARCHITECTURE.md`

Document the assembly architecture before making substantial geometry changes.

---

# PART B — ARCHITECTURE FOR FUTURE EXTENSIBILITY

## 4. Keep engineering logic independent of the UI

The application must retain three conceptual layers:

```text
Presentation Layer
    React / TypeScript
          |
          v
Application Layer
    FastAPI / Job Manager
          |
          v
Engineering Layer
    BladeGen / OpenVSP / OCP
```

Rules:

- React never performs authoritative CAD Boolean operations.
- React never calculates blade assembly geometry for STEP export.
- FastAPI handles communication, validation and job execution.
- The Python engine performs all CAD operations.
- The engineering engine must be callable without running React.
- A command-line interface must remain available.
- CAD output must not depend on browser state.

A future desktop application may reuse the current frontend and local API, or use the Python engine through a supported adapter.

**Do not implement desktop packaging now.**

## 5. Preserve BladeSpec v0.2

Do not add hub or blade-count fields directly into the existing BladeSpec.

BladeSpec remains the engineering definition of one blade.

Introduce a new neutral model:

`PropellerSpec v0.1`

It must contain:

- A complete BladeSpec v0.2.
- The number of blades.
- Hub geometry parameters.
- Shaft-bore geometry.
- Assembly orientation parameters.

This separation is important for future product development.

Users must be able to reuse one BladeSpec inside different propeller assemblies.

For example, the same blade could be assembled with two or three blades without changing its airfoil, chord or twist definitions.

---

# PART C — PROPELLERSPEC CONTRACT

## 6. Create a backend-neutral PropellerSpec

Suggested representation:

```json
{
  "schema_version": "0.1",
  "name": "three_blade_propeller",
  "units": "mm",
  "blade_spec": {
    "...": "Existing complete BladeSpec v0.2"
  },
  "assembly": {
    "blade_count": 3,
    "hub_diameter_mm": 90.0,
    "hub_length_mm": 45.0,
    "shaft_bore_diameter_mm": 12.0,
    "initial_azimuth_deg": 0.0
  }
}
```

The nested BladeSpec illustration represents an actual complete BladeSpec document, not a literal placeholder accepted by the product.

The hub dimensions above are only initial test inputs. They must pass actual geometric intersection checks before being considered an acceptable assembly.

Suggested Python models:

- `PropellerSpec`
- `AssemblySpec`
- `HubSpec`, if useful

Suggested location:

`backend/bladegen/models/propeller_spec.py`

Use Pydantic v2.

Do not include OpenVSP-specific or OCP-specific types in these models.

## 7. Dynamic blade count

Support an engineering-controlled blade count.

Target an initial supported range of 2–8 blades, with actual build feasibility determined by geometry validation.

At minimum, execute and qualify two-, three-, and four-blade assemblies.

Include a higher-count feasibility case where practical.

Do not hard-code geometry generation for exactly three blades.

Do not claim support for an arbitrary blade count if the generated blades overlap incompatibly or Boolean operations fail.

The user must be able to change `blade_count` through the UI without changing source code.

## 8. Hub validation

Validate:

- Positive hub diameter.
- Positive hub length.
- Positive bore diameter.
- Bore diameter smaller than hub diameter.
- Hub diameter smaller than overall propeller diameter.
- Finite numeric parameters.
- Valid blade count.
- Consistent units.

Also validate geometric compatibility with the blade root.

Static parameter validation alone is insufficient.

---

# PART D — CRITICAL COORDINATE CONVENTIONS

## 9. Use the correct propeller rotation axis

The existing BladeGen geometry convention defines:

- Blade radial extension: positive Y.
- Blade section plane: XZ.
- Propeller axial direction: X.
- Tangential direction at the reference azimuth: Z.

Therefore:

**The complete propeller must be assembled by rotating blade copies around the global X axis.**

The hub cylinder and shaft bore must also have their longitudinal axes parallel to X.

Do not create a hub whose longitudinal axis is Y.

Do not rotate blade copies around Y.

Verify these conventions from the existing expected-geometry code and actual final STEP.

## 10. Angular placement

For N blades:

\[
\theta_i = \theta_0 + i\frac{360^\circ}{N}
\]

where:

- N is the requested blade count.
- i ranges from 0 to N−1.
- θ₀ is the initial assembly azimuth.

Examples:

```text
2 blades:
0°, 180°

3 blades:
0°, 120°, 240°

4 blades:
0°, 90°, 180°, 270°
```

These examples assume initial azimuth zero.

Use exact geometric transforms in OCP.

For example, a rotation about a global X-axis `gp_Ax1` with an appropriate `gp_Trsf`.

Do not approximate rotation by modifying airfoil coordinates or regenerating the blade separately at each angle.

## 11. Preserve blade geometry

The assembly process must use the final validated single-blade OCP solid.

For each additional blade:

1. Copy or instance the validated solid.
2. Apply the exact rotation around X.
3. Preserve its volume.
4. Preserve all cross-sectional geometry.
5. Preserve the reference blade's engineering definition.

OpenVSP should be called once for the reference blade, not once for every propeller blade.

Use OCP transformations for assembly copies.

Changing the number of blades must not change the original blade's Chord, Twist, Rake, Skew or airfoil coordinates.

---

# PART E — HUB GEOMETRY

## 12. Implement a simple cylindrical hub

For Sprint 04A, implement only a basic cylindrical hub.

Parameters:

- Hub diameter in mm.
- Hub axial length in mm.
- Shaft bore diameter in mm.

Initial hub center:

```text
X = 0
Y = 0
Z = 0
```

Longitudinal axis:

`Global X`

Define the axial extent explicitly, for example from `-hub_length/2` to `+hub_length/2`.

Do not add:

- Spinner.
- Fillets.
- Keyway.
- Bolt holes.
- Hub flanges.
- Variable diameter.
- Advanced root fairings.

Those belong to Sprint 04B.

## 13. Positive geometric connection to the blades

This is a critical requirement.

The blade root and hub must have a genuine positive-volume intersection before fusion.

Do not accept:

- Merely touching surfaces.
- Coincident faces without robust volumetric overlap.
- Disconnected blade solids inside a compound.
- Apparent visual connections that are not topologically fused.

Calculate actual blade/hub intersection geometry.

For a blade starting at approximately r/R = 0.20 on a 400 mm diameter design, the nominal radial root is 40 mm.

A nominal hub radius of 45 mm may provide radial overlap, but this must be verified against the actual 3D root geometry, including X/Z placement and axial hub length.

Do not assume a 5 mm nominal radial overlap automatically guarantees a valid Boolean union.

If the selected hub does not intersect the blade sufficiently, return an understandable validation error.

Do not secretly enlarge the hub or alter the blade to force a successful union.

---

# PART F — BOOLEAN ASSEMBLY CONSTRUCTION

## 14. Use OpenCascade Boolean operations

Create an assembly module, for example:

```text
backend/bladegen/assembly/
    __init__.py
    transforms.py
    hub.py
    builder.py
    validation.py
```

Use OCP/OpenCascade for:

- Cylindrical hub creation.
- Exact blade rotations.
- Blade/hub intersection checks.
- Boolean fusion.
- Bore cutting.
- Final shape validation.

Recommended tools include:

- `BRepPrimAPI_MakeCylinder`
- `BRepAlgoAPI_Common`
- `BRepAlgoAPI_Fuse`
- `BRepAlgoAPI_Cut`
- `gp_Trsf`
- `BRepCheck_Analyzer`

Choose robust algorithms based on actual OCP behavior.

Avoid large unexplained fuzzy tolerances.

Do not use STL Boolean operations as the authoritative assembly process.

## 15. Suggested construction sequence

```text
Validated Single Blade STEP
            |
            v
      Reference Solid
            |
            v
  Rotate into N blade copies
            |
            v
   Create cylindrical hub
            |
            v
 Verify positive hub overlap
            |
            v
     Boolean fusion
            |
            v
   Cut coaxial shaft bore
            |
            v
    Validate final solid
            |
            v
    Export assembly STEP
```

It is acceptable to modify operation ordering if a more robust CAD strategy is justified and tested.

Do not add artificial connector geometry without explicitly defining it as an engineering design feature.

## 16. Detect unsupported collisions

Multiple blade copies must not create unexpected blade-to-blade intersections outside the intended hub-root region.

Check for inappropriate interpenetration.

A valid fused solid is not sufficient evidence that independently rotated blades are arranged as intended.

Report genuine geometric conflicts.

If the selected blade count cannot be assembled safely with the current blade and hub geometry, fail with an engineering diagnostic rather than hiding the problem.

---

# PART G — SHAFT BORE

## 17. Construct a true through-hole

The shaft bore must be:

- Cylindrical.
- Coaxial with the global X axis.
- Centered on the hub.
- Through the entire hub axial length.
- Defined by the user-supplied diameter.

The recommended operation is a Boolean cut after all blade and hub material has been fused.

The cutting cylinder should extend sufficiently beyond both hub ends to avoid coincident Boolean end faces.

Do not leave hidden blade-root material obstructing the bore.

## 18. Validate the bore independently

After STEP export and re-import, verify:

- Requested bore diameter.
- Actual bore radius.
- Correct X-axis alignment.
- Through-hole continuity.
- No remaining solid material inside the intended bore region.
- Valid final BRep.

Do not consider the bore valid merely because a cylindrical surface appears in the 3D preview.

Use actual OCP measurements and intersections.

---

# PART H — FINAL STEP OUTPUT

## 19. Produce one authoritative propeller STEP

Required output:

`propeller_solid.step`

The final STEP must contain one fused, valid solid representing:

- All requested blades.
- The cylindrical hub.
- The through-bore.

Required topology:

```text
Solids: 1
Closed solid: true
BRepCheck: valid
Non-degenerate free edges: 0
```

Do not require a fixed number of faces.

Face count will depend on blade count and Boolean operations.

Do not report a compound of disconnected solids as successful.

## 20. Preserve original single-blade output

The assembly job should retain the reference single-blade STEP as an internal or downloadable engineering artifact.

This is useful for:

- Reproducibility.
- Independent blade inspection.
- Future design variants.
- Debugging.
- Manufacturing workflows.

Do not modify the validated source blade during assembly.

## 21. Round-trip validation

After writing `propeller_solid.step`:

1. Re-import it with OCP.
2. Recheck solid count.
3. Recheck closure.
4. Recheck BRep validity.
5. Recheck bore geometry.
6. Recheck mass properties.
7. Recheck blade placement and geometry where feasible.

Use the established adaptive Gauss–Kronrod mass-properties calculation.

Report:

- Final propeller volume.
- Reference blade volume.
- Hub pre-cut volume.
- Blade/hub overlap diagnostics.
- Final STEP volume after re-import.
- STEP round-trip volume delta.
- Bounding-box differences.

Do not assume that total assembly volume equals:

`blade_count × blade_volume + hub_volume`

because fused components contain overlapping material and the shaft bore removes material.

---

# PART I — BACKEND PIPELINE DESIGN

## 22. Introduce a separate propeller pipeline

Do not overload the existing single-blade `build()` function with many conditional assembly branches.

Keep a clean separation.

Suggested modules:

```text
backend/bladegen/
    pipeline.py
    propeller_pipeline.py

    models/
        blade_spec.py
        propeller_spec.py

    assembly/
        transforms.py
        hub.py
        builder.py
        validation.py
```

The existing blade pipeline should remain available.

The propeller pipeline may reuse the validated blade-generation service and its results.

Avoid duplicating the geometry generation and airfoil resolution algorithms.

## 23. Define a reusable engine interface

The Python engineering layer should expose callable operations conceptually equivalent to:

```python
build_blade(blade_spec, output_dir)
build_propeller(propeller_spec, output_dir)
```

Names can differ according to the existing codebase.

Important:

- Accept validated neutral specifications.
- Return structured results.
- Do not require a React application.
- Do not require a running HTTP server.
- Do not rely on UI state or browser storage.
- Keep filesystem output paths explicit/configurable.

This interface is important for future desktop portability.

Do not implement a desktop adapter now.

---

# PART J — CLI AND API INTEGRATION

## 24. Extend the existing CLI

Preserve:

```text
bladegen build existing_blade.json
```

Add a separate command such as:

```text
bladegen build-propeller propeller.json --output output/propeller_test
```

Both must use the same installed Python engine.

The CLI must generate an actual final propeller STEP without FastAPI or React.

## 25. Extend FastAPI without breaking existing endpoints

Keep existing single-blade endpoints working.

Suggested additions:

```text
POST /api/propellers/validate
POST /api/propellers/build
```

Reuse the existing job-status and artifact workflow where practical:

```text
GET /api/jobs/{job_id}
GET /api/jobs/{job_id}/artifacts
```

Extend job metadata with a neutral build type, such as `blade` or `propeller`.

The existing blade job responses should remain backward-compatible.

Do not create separate uncoordinated OpenVSP worker queues.

The same serialized execution policy must protect both blade and propeller builds.

## 26. Assembly artifacts

For successful propeller builds, provide:

```text
propeller_solid.step
propeller_preview.stl
propeller_spec.json
blade_solid.step
blade_spec.json
validation.json
```

Retain relevant diagnostic artifacts when useful.

The preview STL must be generated from the final OCP assembly solid.

Do not assemble a separate approximate mesh only for preview and present it as equivalent to STEP.

Update the existing artifact allow-list safely.

Do not accept arbitrary output paths from API clients.

---

# PART K — PROGRESS REPORTING

## 27. Extend the real build progress indicator

The current application has backend-driven progress.

Preserve that architecture.

Provide assembly-specific milestones, for example:

```text
0%   Queued
5%   PropellerSpec validated
15%  BladeSpec resolved
40%  Reference blade generated
55%  Blade copies positioned
70%  Hub and blade fusion completed
80%  Shaft bore cut completed
90%  Final STEP validation completed
95%  Artifacts written
100% Job manager confirmed success
```

These are confirmed stage indicators, not estimates of elapsed time.

Do not advance the percentage merely because time passes.

Do not expose 100% before successful subprocess completion and artifact verification.

Failure messages should identify whether the problem occurred during:

- Blade generation.
- Rotation/positioning.
- Hub intersection.
- Boolean fusion.
- Bore cutting.
- STEP validation.

---

# PART L — FRONTEND INTEGRATION

## 28. Continue using the existing React application

Do not create a second web app.

Introduce a user-facing design mode:

**Single Blade**

**Full Propeller**

The existing blade editing features remain accessible in both modes.

The engineer should not have to re-enter the airfoil stations and spanwise distributions when switching between modes.

## 29. Add Propeller Assembly controls

Suggested user-facing section:

```text
Propeller Assembly

Number of Blades          [ 3 ]
Hub Diameter (mm)         [ 90 ]
Hub Length (mm)           [ 45 ]
Shaft Bore Diameter (mm)  [ 12 ]
Initial Azimuth (deg)     [ 0 ]

[ Validate Assembly ]
[ Generate Propeller ]
```

Use the existing engineering UI styling and numeric input components.

Provide clear labels and units.

Explain the difference between:

- Number of blades.
- Number of radial airfoil sections.

These are different engineering parameters.

Changing blade count must not change the count of airfoil sections.

## 30. Keep the existing blade editor

Continue supporting:

- Airfoil Station editing.
- Airfoil Library.
- DAT/CSV import.
- Chord/Twist/Rake/Skew/Thickness distributions.
- 2D design preview.
- Section comparison.
- Existing 3D blade viewer.

The user should first define one blade and then assemble it into a propeller.

Do not require a separate copy of each blade's engineering parameters.

In Sprint 04A, all blades are geometrically identical and equally spaced.

Independent pitch adjustment per blade is outside scope.

## 31. Full propeller preview

Extend the existing Three.js viewer to display the complete propeller STL.

Provide appropriate camera presets:

- Propeller Front View, looking along the rotation axis X.
- Propeller Side View.
- Isometric View.
- Fit to Model.
- Expand Viewer.

Preserve orbit, pan, zoom, and resize behavior.

The user must be able to inspect all blades and the hub.

Do not let the old selected-station guide appear misleadingly on rotated blades.

For Sprint 04A, it is acceptable to disable radial station guides in full-propeller mode with an explanatory note, while preserving them in single-blade mode.

Future versions may provide per-blade station inspection.

## 32. Preserve result identity

A blade build and a propeller build are different artifacts.

Keep track of:

- Build type.
- Submitted specification.
- Job ID.
- Artifacts.
- Validation report.
- Preview mesh.

If the engineer changes blade count, hub dimensions, or bore diameter after generating the propeller, the displayed CAD must become visibly stale.

Do not reuse the single-blade-only snapshot as the identity of a complete propeller build.

Switching modes must not silently relabel the last successful blade preview as a complete propeller or vice versa.

## 33. Do not expand visual curve editing

The existing curve-editor interaction has known user-reported usability limitations.

Sprint 04A must not spend time rewriting it.

Keep numeric table editing operational.

Preserve the current visual charts.

Do not introduce new curve-dragging behaviors as part of the assembly work.

---

# PART M — FUTURE DESKTOP PORTABILITY

## 34. Keep the transport boundary replaceable

We are not developing a desktop application in this sprint.

However, the product must remain easy to adapt later.

Requirements:

- No CAD computations inside React.
- No frontend dependency inside the Python geometry package.
- No FastAPI request objects inside engineering modules.
- Explicit, versioned neutral JSON contracts.
- Stable CLI entrypoints.
- Configurable generated-data directories.
- Configurable OpenVSP runtime location.
- No hard-coded user-specific paths in the engine.
- API-specific job management kept separate from CAD calculations.

Where existing path handling is unnecessarily bound to the repository root, introduce a minimal backward-compatible runtime-data configuration.

Do not turn this into a large configuration refactor.

## 35. Preserve future migration options

A future desktop shell should be able to reuse the current React UI with a local backend, or invoke the engine through a supported application layer.

Do not select or implement Electron, Tauri, Qt, or another desktop framework now.

Document possible integration boundaries without claiming that cross-platform deployment is already solved.

The current OpenVSP installation scripts are Linux-specific; Windows and macOS support would still require separate packaging and qualification.

---

# PART N — REQUIRED GEOMETRY TESTS

## 36. Transform tests

Test blade placement for:

- 2 blades.
- 3 blades.
- 4 blades.

Verify:

- Correct angular spacing.
- Correct X-axis rotation.
- Unchanged reference blade volume.
- Unchanged blade section geometry.
- Unchanged propeller diameter definition.
- Correct initial azimuth behavior.

A wrong-axis rotation must fail the tests.

Test transformed section positions using actual OCP geometry or a mathematically independent reference.

## 37. Hub and bore tests

Test:

- Hub cylinder aligned with X.
- Correct hub diameter.
- Correct axial hub length.
- Correct bore diameter.
- Through-hole clearance.
- Invalid hub/bore dimensions.
- Insufficient hub/blade overlap.
- Tangential contact without positive volume.
- Excessive overlapping blade roots.
- Unsupported high-blade-count collision, where applicable.

Do not rely exclusively on surface rendering.

Use OCP topology and dimensional measurements.

## 38. Assembly acceptance cases

Create at least three successful real CAD test cases.

### Case A — Two-blade propeller

Use the validated single-blade baseline with a compatible hub.

Require:

- Two equally spaced blades.
- One connected assembly solid.
- Correct through-bore.
- Successful STEP re-import.

### Case B — Three-blade propeller

Use the same blade definition, but set blade count to three.

Require:

- 120° spacing.
- Identical copied blade geometry.
- One connected assembly solid.
- Correct through-bore.

### Case C — Four-blade propeller

Use four blades.

Require:

- 90° spacing.
- One connected assembly solid.
- Correct through-bore.
- Valid CAD topology.

Choose hub dimensions that genuinely pass measured overlap checks. Do not silently change the submitted specification during generation.

Additional optional case:

- A six-blade design with appropriate geometry, if feasible.

Document the actually qualified range instead of assuming every blade count will work.

## 39. Negative acceptance cases

Require controlled failures for:

1. Bore diameter greater than or equal to hub diameter.
2. Hub not intersecting the blade roots.
3. A blade count producing unacceptable unintended blade collisions.
4. Invalid input dimensions.
5. Boolean fusion failure.
6. Bore-cut failure.
7. Invalid STEP topology.

These must return understandable diagnostics.

They must not produce a false PASS or downloadable invalid assembly labeled as successful.

---

# PART O — INDEPENDENT VALIDATION

## 40. New assembly validation report

Create structured assembly validation including:

```text
Requested blade count
Actual blade placement count
Azimuth angles
Rotation axis
Reference blade volume
Hub diameter / length
Bore diameter
Hub/blade overlap metrics
Blade-blade collision diagnostics
Boolean fusion status
Bore-cut status
Final solid count
Shell count
Closed-shell status
Free-edge count
BRep validity
Adaptive volume
STEP round-trip metrics
Overall PASS/FAIL
```

Keep blade geometry-validation results separate from assembly validation results.

A successful assembly must require both:

- A valid reference blade.
- A valid assembled propeller.

## 41. Symmetry and blade preservation

Verify the actual copied blade placements independently from the requested parameters.

Where possible, compare the final geometry against the expected equally spaced rotational pattern.

A blade count of three should exhibit 120° cyclic symmetry around X before considering any optional non-axisymmetric future features.

Do not confuse rotational symmetry with arbitrary bounding-box equality.

Use geometric transformations, CAD comparisons, or meaningful sampling checks.

## 42. Validate the final fused STEP, not only the ingredients

A valid reference blade and a valid hub do not guarantee a valid assembly.

The final assembly itself must be:

- Exported.
- Re-imported.
- Topologically validated.
- Checked for the bore.
- Checked for connectedness.
- Checked for intended blade placement.

Do not declare success based solely on successful execution of a Boolean operator.

---

# PART P — TESTING AND QUALITY

## 43. Backend tests

Preserve the current backend suite.

Add:

- PropellerSpec validation tests.
- OCP rotation tests.
- Hub primitive tests.
- Bore tests.
- Boolean fusion tests.
- Assembly validation tests.
- Real two-/three-/four-blade STEP tests.
- CLI propeller build tests.
- API propeller job tests.
- Invalid-input and failed-build tests.

Do not replace existing single-blade regression cases.

## 44. Frontend tests

Verify:

- Switching between Single Blade and Full Propeller.
- Blade count editing.
- Hub and bore parameter editing.
- Submission of PropellerSpec.
- Assembly validation errors.
- Progress stages.
- Correct artifact links.
- Full propeller preview.
- Stale CAD after assembly parameter changes.
- Preservation of the single-blade editor.
- No automatic CAD generation when editing assembly values.

## 45. Real browser acceptance

Use Playwright against the current application.

Minimum workflow:

```text
Open BladeGen
      ↓
Load existing five-section blade
      ↓
Switch to Full Propeller
      ↓
Set Number of Blades = 3
      ↓
Set Hub Diameter / Length
      ↓
Set Shaft Bore Diameter
      ↓
Validate Assembly
      ↓
Generate Propeller
      ↓
Observe real progress stages
      ↓
View complete 3D assembly
      ↓
Switch Front / Side / Isometric
      ↓
Expand Viewer
      ↓
Download propeller_solid.step
      ↓
Inspect assembly validation
      ↓
Change blade count to 4
      ↓
Verify existing result becomes stale
      ↓
Generate and verify four-blade assembly
```

At least one complete browser workflow must use real OpenVSP/OCP generation rather than mocked responses.

## 46. Regression

Execute all previous engineering regressions:

- Single-blade three-section case.
- Five-section baseline.
- Eight-section case.
- Thickness override.
- Imported coordinate profile.
- Existing 2D preview and station comparison tests.

Do not weaken existing tolerances.

Assembly development must not change the original blade-generation mathematics.

---

# PART Q — DELIVERABLES

## 47. Required source outputs

Implement the engineering model, assembly modules, pipeline, CLI, API integration, UI integration, and tests.

Create:

```text
docs/SPRINT_04A_REPORT.md
docs/SPRINT_04A_ACCEPTANCE_MATRIX.md
docs/PROPELLER_ASSEMBLY_CONVENTIONS.md
```

Update:

```text
README.md
docs/ARCHITECTURE.md
docs/GEOMETRY_CONVENTIONS.md
```

where necessary.

Include a JSON Schema for PropellerSpec v0.1.

Provide reproducible accepted examples for two-, three-, and four-blade configurations.

Keep original BladeSpec examples unchanged.

## 48. Screenshots

Provide actual application screenshots showing:

- Assembly input controls.
- Two-blade assembly.
- Three-blade assembly.
- Four-blade assembly.
- Hub and bore detail.
- Expanded full-propeller viewer.
- Assembly validation results.

Do not fabricate screenshots or CAD results.

## 49. Final report

Report:

- Branch and commit SHA.
- Changed files.
- New API endpoints.
- New CLI commands.
- PropellerSpec JSON example.
- Accepted blade-count range.
- Actual hub-root connection results.
- Boolean operation diagnostics.
- Bore measurements.
- Final STEP topology.
- Independent volume measurements.
- STEP round-trip results.
- Frontend tests.
- Backend tests.
- Playwright results.
- Known limitations.
- Commands for reproducing each accepted case.

Explain any deviations from the original implementation plan.

---

# PART R — ACCEPTANCE CRITERIA

Sprint 04A qualifies as STRONG PASS only when:

1. PropellerSpec is backend-neutral and versioned.
2. Existing BladeSpec v0.2 remains compatible.
3. The reference blade is generated once per full assembly build.
4. Additional blades are created through exact OCP transformations.
5. Copies rotate around the correct global X axis.
6. Angular spacing matches the requested blade count.
7. Hub geometry is coaxial with X.
8. Hub/blade overlap is genuinely volumetric.
9. No unexpected blade-blade intersections are accepted.
10. The shaft bore is a real continuous through-hole.
11. The final assembly is one connected valid solid.
12. Non-degenerate free edges equal zero.
13. Final assembly STEP round-trip passes.
14. Final geometry and bore dimensions are independently measured.
15. Two-, three-, and four-blade acceptance builds pass.
16. Invalid assembly configurations fail safely.
17. Existing single-blade behavior remains unchanged.
18. The current React UI supports full-propeller generation.
19. Assembly parameters are editable and validated.
20. The full-propeller preview uses the actual final OCP solid.
21. Blade and propeller artifacts cannot be confused.
22. Progress reflects real assembly stages.
23. The CLI can generate a propeller without the web interface.
24. The core engine contains no React/FastAPI dependencies.
25. Future desktop integration boundaries are documented.
26. Existing frontend and backend regressions pass.
27. A real browser end-to-end assembly workflow passes.
28. The historical archive remains untouched.

If a required topology, axis, bore, or blade-preservation criterion fails, do not declare STRONG PASS.

Report PASS WITH LIMITATIONS or FAIL, with evidence.

---

# STRICT SCOPE CONTROL

Do not implement in Sprint 04A:

- Advanced root fillets.
- Spinner geometry.
- Keyways or bolt patterns.
- Hub flanges.
- Individual blade pitch adjustment.
- Independent airfoil definitions per blade.
- Aerodynamic optimization.
- Thrust, torque, efficiency or cavitation analysis.
- Structural FEA.
- Manufacturing certification.
- New interpolation algorithms.
- Rewriting visual curve editing.
- A new frontend framework.
- A desktop application.
- New CAD backends.

These belong to future development.

---

# EXECUTION ORDER

Phase 1 — Engineering Contract and Axis Validation

Verify the existing blade coordinate system and implement PropellerSpec v0.1.

Phase 2 — OCP Assembly Core

Implement blade rotations, cylindrical hub, volumetric overlap validation, fusion and coaxial bore.

Phase 3 — Independent Assembly Qualification

Validate topology, dimensions, blade preservation, bore continuity, symmetry and STEP round-trip.

Phase 4 — Product Integration

Integrate the new CLI command, FastAPI job workflow, React assembly controls and full-propeller viewer.

Phase 5 — Full Acceptance

Execute real two-, three-, and four-blade builds, negative tests, frontend regressions, browser acceptance and existing single-blade tests.

Do not bypass a P0 geometry problem merely to make the UI appear functional.

---

# FINAL INSTRUCTION

Implement Sprint 04A directly in the existing BladeGen repository.

Preserve the validated single-blade engine and all existing user-facing functionality.

Keep the current React/FastAPI application.

Create a separate, reusable Python assembly engine with a backend-neutral PropellerSpec contract.

Do not automatically merge into main.

**The desired result is a dynamic BladeGen application in which the engineer designs one blade, chooses the number of blades and hub/bore geometry, generates a physically connected propeller assembly, and exports one independently validated solid STEP file—while keeping the engineering core reusable for a future desktop application.**