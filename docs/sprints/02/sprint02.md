# SPRINT 02 — Dynamic Stations, Generic CAD Validation & Engineering Workflow Integrity

## Repository

https://github.com/ahmadqwcv5-droid/bladegen

## Objective

Transform BladeGen Level 1 Alpha from a working fixed-example interface into a reliable, user-configurable blade generator.

The primary acceptance requirement is:

**The user can define, add, remove, and edit arbitrary valid airfoil stations and independent spanwise distribution control points, then generate a solid STEP whose geometry is validated against that exact user-defined BladeSpec.**

This sprint addresses confirmed gaps found through source-code inspection.

Do not rebuild the geometry engine.

---

# 1. Start with repository inspection

Review the current implementations, especially:

- `backend/bladegen/models/blade_spec.py`
- `backend/bladegen/adapters/openvsp_adapter.py`
- `backend/bladegen/validation/measure_sections.py`
- `backend/bladegen/validation/expected_geometry.py`
- `backend/bladegen/pipeline.py`
- `backend/bladegen/curves/resolver.py`
- `frontend/src/App.tsx`
- `frontend/src/components/DistributionTable.tsx`
- `frontend/src/components/BladeViewer.tsx`
- `frontend/src/types/bladespec.ts`
- `backend/api/routes/blades.py`
- `backend/api/services/jobs.py`

First verify that the checked-out code matches the repository state described below.

Work in the existing product workspace.

Do not create a new project or another research spike.

Do not move or modify `00_research_archive`.

Preserve the existing directory structure.

Create a focused Git branch for Sprint 02 if Git is available.

---

# 2. Confirmed blocker: hard-coded validation stations

Current file:

`backend/bladegen/validation/measure_sections.py`

contains fixed values:

```python
CONTROL_STATIONS = [0.20, 0.40, 0.60, 0.80, 1.00]
INTERMEDIATE_STATIONS = [0.30, 0.50, 0.70, 0.90]
SAMPLED_STATIONS = {0.20: 0.203, 1.00: 0.9995}
```

These belong to historical Spike 01D test geometry, not a generic product validator.

Current `backend/bladegen/pipeline.py` also explicitly searches for root and tip records at `r/R=0.20` and `1.00`.

This is a P0 engineering defect for arbitrary user-defined blades.

**Fix this first, before implementing UI station insertion.**

---

# 3. Make independent validation fully BladeSpec-driven

Replace hard-coded station arrays with a deterministic validation-station planner.

Create a module or abstraction such as:

`backend/bladegen/validation/station_plan.py`

It must derive the validation stations from the actual BladeSpec.

At minimum it must include:

1. Every explicit user-defined airfoil station.
2. One or more representative interior locations between adjacent airfoil stations.
3. The actual root radius specified by `root_radius_ratio`.
4. The tip radius, `r/R=1.0`.
5. Appropriate diagnostic stations for independent chord/twist/rake/skew interpolation, where practical.

Distinguish:

- explicit airfoil stations,
- intermediate airfoil-morphing stations,
- distribution-control checkpoints.

Do not classify a location as an airfoil control station merely because it appeared in Spike 01D.

Do not assume five sections.

Do not assume root radius 0.20.

Do not assume particular internal airfoil names.

---

# 4. Root and tip cut policy

Exact root and tip cuts may intersect end-cap edges.

The previous validator measured:

- requested 0.20 at actual 0.203,
- requested 1.00 at actual 0.9995.

Replace this fixed mapping with a general endpoint-cut strategy.

The validator must:

- Determine valid inward sample locations based on the actual blade domain and adjacent station spacing.
- Avoid cap-intersection artifacts.
- Record both the requested and sampled radius.
- Evaluate expected geometry at the actual sampled location.
- Avoid reporting an inward cut as a mathematically exact measurement at the requested endpoint.
- Report any inferred endpoint value separately from direct CAD measurements.

Preserve the existing engineering tolerances.

Do not loosen tolerances simply to obtain a PASS.

Ensure that TE thickness comparisons correctly account for variation between the endpoint and its inward sample.

If endpoint values cannot be certified directly, document the limitation precisely.

---

# 5. Remove hard-coded station assumptions from pipeline summaries

Update:

`backend/bladegen/pipeline.py`

Specifically review `_geometry_summary()`.

Do not use:

```python
next(row for row in controls if row["requested_r_over_R"] == 0.20)
```

Instead identify the root and tip from the supplied BladeSpec and generated station plan.

All reports must describe the actual user design.

Preserve validation JSON compatibility where reasonable.

If new fields are necessary, add them without unnecessarily removing existing fields.

---

# 6. Keep the existing engineering backend

Do not replace:

- BladeSpec v0.2,
- canonical SciPy PCHIP evaluation,
- adaptive curve resolver,
- canonical NACA generation,
- OpenVSP adapter,
- OCP solidification,
- adaptive Gauss–Kronrod volume integration.

The desired pipeline remains:

```text
User BladeSpec
      ↓
Canonical Curve Resolution
      ↓
Canonical Airfoil Resolution
      ↓
OpenVSP
      ↓
OCP Solidification
      ↓
Solid STEP
      ↓
Independent CAD Validation
```

The existing OpenVSP adapter already adjusts XSec count using `CutXSec` and `InsertXSec`.

Keep this approach, but verify it on multiple station counts.

Do not claim arbitrary station support without executing actual CAD builds.

---

# 7. Add dynamic Airfoil Station controls to React

Current UI file:

`frontend/src/App.tsx`

currently renders the provided list of airfoil sections and supports editing existing rows.

Implement real station management.

Required UI actions:

- Add Airfoil Station.
- Remove Airfoil Station.
- Edit r/R.
- Select or enter NACA 4-digit profile.
- Edit physical trailing-edge thickness.
- View effective thickness ratio.
- Enable or disable explicit thickness override.

Display the actual number of airfoil stations.

For example:

`Airfoil Stations (5)`

The number must update automatically when rows are inserted or removed.

Use stable client-side row identities so inserting or deleting a row does not attach input state to the wrong station.

Do not add client-only row IDs to the public BladeSpec JSON.

---

# 8. Station ordering and domain validation

Keep the existing engineering rules:

- At least two airfoil sections.
- Strictly increasing radii.
- No duplicate r/R.
- Valid root and tip coverage.
- Finite numerical parameters.
- Valid airfoil definitions.

Preserve `BladeSpec v0.2` semantics.

For user convenience, insertion may be sorted automatically, but the UI must clearly show where the new station was inserted.

Prevent or explain invalid operations.

For example:

- Duplicating a station radius must show an error.
- Deleting the only remaining interior station is permitted when the blade still has two valid endpoint sections.
- Deleting an essential root or tip section must not silently invalidate the blade.

---

# 9. Make the global root radius the source of truth

Currently editing `root_radius_ratio` in the UI changes the global value without automatically updating the first point of the independent distributions.

The backend requires each distribution to cover the same root-to-tip radial domain.

Implement a clear root-editing policy.

When the user changes root radius:

- Update the first airfoil-station radius consistently.
- Update the first control radius in chord, twist, rake, skew, and thickness distributions.
- Preserve their engineering values unless the user intentionally changes them.
- Check that the new radius is below every next control point.
- Reject invalid root changes with an understandable message.

Keep the tip radius fixed at 1.0 unless a future schema introduces a different explicit domain.

Do not let the global root radius and the station table silently disagree.

---

# 10. Add and remove independent distribution control points

Current component:

`frontend/src/components/DistributionTable.tsx`

supports editing existing values but not changing point counts.

Add:

- Add Control Point.
- Remove Control Point.
- Edit control-point radius.
- Edit engineering value.
- Choose Linear or PCHIP.

Each distribution must be independent.

For example, allow:

```text
Airfoil stations = 8

Chord control points = 5
Twist control points = 7
Rake control points = 3
Skew control points = 4
Thickness control points = 8
```

Do not force all curves to use the airfoil station grid.

When inserting a new curve point, initialize its value by evaluating the current canonical distribution at the new radius.

Preserve the intended curve as much as possible and identify changes where inserting a control point alters interpolation behavior.

Never introduce OpenVSP-native interpolation semantics.

---

# 11. Fix NACA / thickness coordination

Current source behavior:

`frontend/src/App.tsx` updates the thickness curve automatically only when an existing thickness control point has exactly the same radius as the edited NACA section.

This becomes inadequate when users add new airfoil stations at radii not present in the thickness distribution.

The backend also validates that the thickness curve matches the nominal NACA thickness unless an explicit override is declared.

Implement a clear engineering interaction.

Required semantics:

- NACA code determines nominal profile thickness.
- An override must be explicit.
- The effective thickness must be visible to the user.
- Any mismatch between NACA and thickness distribution must be explained before generation.
- The program must not silently change unrelated distribution-control points.

For a non-coincident station, if the current thickness distribution is inconsistent with the selected profile, provide an appropriate user-facing resolution.

Possible resolution: insert a thickness control point at that radius using the selected nominal ratio.

Do not force the user to understand hidden OpenVSP thickness behavior.

Do not make all station grids coincident merely to simplify the frontend.

---

# 12. Verify actual thickness overrides geometrically

Existing `test_product_semantics.py` checks that an explicit thickness override is accepted by the resolver.

That alone does not prove the final CAD has the overridden physical section thickness.

Add a real CAD regression:

Example:

```text
Airfoil = NACA 0008
Nominal t/c = 0.08
Explicit effective t/c = 0.10
```

Build the blade through the real OpenVSP/OCP pipeline.

Measure the final STEP section.

Verify that the measured section reflects the explicitly requested effective thickness.

If this currently fails, diagnose the interaction among:

- canonical NACA coordinates,
- thickness distribution,
- OpenVSP PROP_THICK,
- independent expected geometry.

Do not claim thickness override support based only on schema acceptance.

Make the smallest appropriate correction while preserving existing compatibility.

---

# 13. Implement reliable frontend editing state

Currently several numeric fields directly convert input text using `Number(...)`.

This can turn a temporarily empty field into zero while the user is editing.

Improve numeric-field behavior so users can:

- Clear a field temporarily.
- Type a new value.
- Correct an invalid input without unexpected state changes.
- See validation feedback near the relevant field.

Validate before building.

Do not introduce silent numeric coercions that alter engineering intent.

Preserve NACA code strings including leading zeroes:

```text
0012
0010
0008
```

These are identifiers, not numbers.

---

# 14. Prevent stale CAD preview and result confusion

Current frontend stores:

- editable BladeSpec,
- job status,
- artifacts,
- validation result.

But it does not explicitly bind the successful preview to a frozen version of the user inputs.

Implement a generation-state model.

At build submission:

1. Capture an immutable snapshot of the submitted BladeSpec.
2. Associate the snapshot with the returned job ID.
3. Track whether current editor inputs still match that submitted snapshot.

If the user modifies inputs after a successful build, show:

**Inputs changed — regenerate to update CAD.**

The old preview may remain visible, but it must be clearly labeled as belonging to the previous successful build.

Never imply the old STEP matches modified inputs.

Prevent old asynchronous job responses from overwriting the artifacts or state of a newer active job.

Disable conflicting build actions while a job is being submitted or clearly manage queued jobs.

---

# 15. Add Save / Open BladeSpec

Users must be able to save their engineering definitions independently from STEP.

Implement:

- Export BladeSpec JSON.
- Import BladeSpec JSON.
- New Blade project.
- Load Example.
- Reset changes with confirmation.

The exported JSON must conform to the existing backend-neutral schema.

No user-facing OpenVSP fields.

An exported project must be re-importable without losing:

- airfoil station count,
- individual airfoil definitions,
- trailing-edge thicknesses,
- distribution point counts,
- interpolation methods,
- reference axis,
- global geometry settings.

Coordinate-based airfoils must not be discarded or silently transformed into NACA selections when importing.

If the UI does not yet provide a coordinate editor, retain the full coordinate data losslessly and offer an appropriate advanced representation.

No database is necessary in this sprint.

---

# 16. Improve validation feedback

Display useful engineering results rather than only a generic PASS indication.

At minimum show:

- Solid validity.
- Closed-shell status.
- Free-edge count.
- Adaptive volume.
- Maximum chord error.
- Maximum twist error.
- Maximum reference-axis error.
- Maximum TE error.
- Contour RMS/P95/maximum.
- Requested versus sampled root/tip measurement radii.

Allow the user to inspect per-station measurement results.

Clearly separate:

- input validation,
- build success,
- STEP topology validation,
- independent geometry validation.

If the build fails, present the actual failure reason.

Do not display a successful CAD status for a different input revision.

---

# 17. Three required acceptance blades

Generate and validate three distinct blades using the real pipeline.

## Case A — Three airfoil sections

Use:

```text
Root r/R = 0.25

Airfoil stations:
0.25
0.625
1.00
```

Use NACA 0012 throughout, with a valid constant thickness distribution and nonzero twist.

Ensure chord and twist control grids do not have to coincide with the airfoil grid.

The final STEP must be independently measured at the actual three airfoil stations and appropriate intermediate locations.

This case primarily tests variable root and minimum practical station count.

## Case B — Five airfoil sections

Reuse the validated Spike 01D multi-airfoil finite-TE example without changing its engineering values.

This is the regression baseline.

Its previous tolerances must remain unchanged.

## Case C — Eight airfoil sections

Use:

```text
Root r/R = 0.18

Airfoil stations:
0.18
0.28
0.40
0.51
0.63
0.76
0.88
1.00
```

Use multiple different NACA profiles, physically valid TE thicknesses, and chord/twist/rake/skew distributions.

Ensure the chord and twist grids differ from the airfoil station grid.

Ensure the thickness distribution is consistent with the selected NACA profiles or documented overrides.

The final STEP must reproduce all eight explicit airfoil stations within the preserved engineering tolerances.

Do not fabricate results.

If OpenVSP or OCP cannot generate one case, record the failure and diagnose it.

---

# 18. CAD acceptance criteria

For each blade require:

```text
1 valid solid
1 closed shell
0 non-degenerate free edges
BRepCheck valid
STEP round-trip successful
```

Preserve final-section tolerances:

```text
Chord error <= 0.05 mm
Twist error <= 0.05°
Reference-axis error <= 0.05 mm
TE error <= 0.020 mm
```

Preserve the existing control/intermediate contour thresholds.

Do not assume that all valid solids have exactly eight faces.

Face count may legitimately change with geometry, cap topology, and TE configuration.

Preserve adaptive Gauss–Kronrod volume reporting.

Measure geometry from the final STEP using OCP, not OpenVSP readback alone.

---

# 19. Frontend testing

The current project has Vitest configuration but no established comprehensive frontend test suite.

Implement component-level tests for:

- Adding an airfoil station.
- Removing an airfoil station.
- Invalid duplicate radius.
- Changing root radius.
- Independent chord/twist point editing.
- NACA selection with leading zeroes.
- Thickness consistency feedback.
- Linear/PCHIP selection preservation.
- BladeSpec JSON import/export.
- Modified inputs marking results stale.
- Correct association of job ID and results.

Add at least one browser-level smoke test using Playwright if the test environment supports it.

If browser automation is unavailable, state that limitation and provide a reproducible manual acceptance checklist.

Do not claim browser tests passed unless executed.

---

# 20. Backend tests

Add tests for:

- Generic station planning from BladeSpec.
- Three-section blade validation.
- Eight-section blade validation.
- Arbitrary valid root radius.
- Root/tip inward-offset accounting.
- Independent distribution grids.
- No duplicate control stations.
- Proper thickness semantics.
- Final STEP section measurement.
- Consistent validation summaries.

Execute all existing backend tests.

Keep historical engineering regressions passing.

Do not replace real CAD integration tests with assertions against saved CSV files.

---

# 21. Preview improvements

Preserve Three.js and the existing OCP-derived STL workflow.

Make practical improvements where time permits:

- Fit-to-model action.
- Visible coordinate axes.
- Better default camera framing.
- Loading and failure feedback.
- Proper viewer cleanup when geometry changes.
- Clear indication of the build that produced the displayed preview.

Do not introduce an unrelated mesh-generation engine.

The STEP remains the authoritative geometry.

---

# 22. Example and naming cleanup

The current repository contains:

`examples/custom_multi_airfoil_finite_te.json`

but its BladeSpec name and geometry correspond to the custom 400 mm multi-airfoil test blade.

Avoid misleading users into believing this file represents the official NASA X-57 geometry.

Introduce a correctly named custom example.

Update UI and API references as needed.

Preserve compatibility for existing tests or document any necessary migration.

---

# 23. Scope restrictions

Do not build in this sprint:

- Full multi-blade propeller.
- Hub or bore.
- Aerodynamic simulation.
- Thrust/torque optimization.
- VSPAERO.
- Large airfoil database.
- Cloud deployment.
- User authentication.
- A replacement for OpenVSP.
- A replacement for OCP.

Do not modify `00_research_archive`.

Prioritize engineering correctness and input fidelity over decorative UI improvements.

---

# 24. Required deliverables

Produce:

```text
docs/SPRINT_02_REPORT.md
docs/SPRINT_02_ACCEPTANCE_MATRIX.md
```

Also update:

```text
README.md
docs/ARCHITECTURE.md
docs/VALIDATION_POLICY.md
```

where required.

Create reproducible example specifications for all three acceptance blades.

Save their actual validation results.

Do not commit large generated STEP files unless the project explicitly uses a suitable artifact policy.

Preserve the current production directory layout.

---

# 25. Final report

The final sprint report must answer:

1. Can users add and remove airfoil stations from the UI?
2. Can users independently add and remove chord/twist/rake/skew/thickness control points?
3. Does BladeSpec retain its neutral v0.2 semantics?
4. Are validation stations derived from the submitted BladeSpec?
5. Is a non-0.20 root supported?
6. Did the three-section blade pass?
7. Did the five-section regression pass?
8. Did the eight-section blade pass?
9. Do all final STEP solids pass OCP topology checks?
10. Do chord/twist/TE and contour measurements pass?
11. Can a project be exported and re-imported without losing inputs?
12. Are previews reliably associated with the inputs that generated them?
13. Does explicit NACA thickness override produce the correct measured CAD thickness?
14. Which backend and frontend tests were actually executed?
15. What remains incomplete?

Provide actual commands and results.

Classification:

- STRONG PASS
- PASS WITH LIMITATIONS
- FAIL

Do not classify the sprint as STRONG PASS if variable station counts work only in the UI but generic STEP validation remains hard-coded.

Do not classify it as STRONG PASS if saved input specifications cannot reproduce the geometry displayed to the user.

---

# 26. Execution order

Implement in this order:

**Phase 1 — Generic validation**

Remove hard-coded station assumptions. Add and run tests.

**Phase 2 — Dynamic data editing**

Implement independent airfoil-station and distribution-point management.

**Phase 3 — Engineering input integrity**

Fix root synchronization, NACA/thickness consistency, numeric editing, and input error reporting.

**Phase 4 — Reliable results**

Implement submitted-spec snapshots, stale-preview detection, save/open JSON, and clear validation displays.

**Phase 5 — Full acceptance**

Generate actual 3-, 5-, and 8-section blades. Validate all final STEP files. Run regressions and frontend tests.

Do not advance to a later phase while a P0 correctness blocker remains unresolved.

---

# FINAL INSTRUCTION

This is a product-development sprint, not another isolated research spike.

Use the existing validated geometry engine.

Implement the changes in the current workspace, keep the architecture maintainable, run the real tests, and report failures honestly.

The desired result is a BladeGen application in which the user genuinely controls the number, location, profile, and geometric properties of the blade sections—and receives a STEP solid independently verified against those exact inputs.