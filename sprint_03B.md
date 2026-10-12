# SPRINT 03B — BladeGen Interactive Blade Inspection & Airfoil Comparison

## Repository

https://github.com/ahmadqwcv5-droid/bladegen

## Mission

Extend the existing BladeGen Level 1 Alpha application with an integrated visual engineering inspection workflow.

The application already supports:

- Backend-neutral BladeSpec v0.2.
- Dynamic airfoil stations.
- Independent chord, twist, rake, skew, and thickness distributions.
- Searchable Airfoil Library.
- NACA 4-digit and imported DAT/CSV profiles.
- Canonical source/resolved 2D airfoil previews.
- Real STEP generation through OpenVSP and OCP.
- Independent CAD validation.
- An expandable Three.js viewer.
- Job-specific results and stale-input detection.

**The goal of Sprint 03B is to connect these existing capabilities into one interactive engineering workflow.**

The engineer must be able to:

1. Select any airfoil station in the station table.
2. See the corresponding radial location highlighted on the generated 3D blade.
3. Inspect that station's current 2D airfoil definition.
4. Select two stations for side-by-side and overlaid airfoil comparison.
5. Compare their geometrical properties.
6. Work safely when current editable inputs differ from the last generated CAD model.

Do not replace or redesign the existing geometry engine.

This sprint focuses on inspection, visualization, and reliable state synchronization.

---

# PART 1 — PROJECT PREPARATION

## 1. Inspect the current repository

Review the latest Git branch, commits, and working-tree state.

The last reviewed main branch contained Patch 03A.1, which corrected the 2D Airfoil Inspector, distribution hover accuracy, validation policy reporting, and imported-airfoil diagnostics.

Verify the actual current repository state before implementation.

Create a branch:

`sprint/03b-interactive-blade-inspection`

Preserve uncommitted changes.

Do not modify:

`00_research_archive/`

Do not automatically merge into `main`.

## 2. Existing implementation

Review at minimum:

- `frontend/src/App.tsx`
- `frontend/src/components/BladeViewer.tsx`
- `frontend/src/components/bladeViewerCamera.ts`
- `frontend/src/components/AirfoilInspector.tsx`
- `frontend/src/components/AirfoilSelector.tsx`
- `frontend/src/components/DistributionChart.tsx`
- `frontend/src/editor/bladespecEditor.ts`
- `frontend/src/types/bladespec.ts`
- `backend/api/routes/airfoils.py`
- `backend/bladegen/validation/expected_geometry.py`
- `backend/bladegen/validation/station_plan.py`
- `backend/bladegen/solid/ocp_solidify.py`
- `docs/GEOMETRY_CONVENTIONS.md`

The frontend already has a `selectedStation` state, but it is currently index-based and is not integrated with the 3D viewer.

The existing `BladeViewer` receives an STL URL and displays the final OCP-derived preview.

Preserve this structure and extend it carefully.

---

# PART 2 — CORE ENGINEERING RULES

## 3. Preserve geometry conventions

BladeGen currently defines:

- Units: millimeters.
- Radial blade axis: positive Y.
- Blade radius: R = diameter_mm / 2.
- Radial station position: r/R.
- Local blade section plane: XZ at a given Y coordinate.

Therefore, a station's axial position in the preview is:

```text
station_y_mm = (diameter_mm / 2) * station_r_over_R
```

Use the exact stored BladeSpec radial positions.

Do not infer station locations from the STL bounding-box length or evenly space markers across the blade.

Do not assume root r/R = 0.20.

Support arbitrary valid root positions and arbitrary numbers of airfoil stations.

The STL preview is produced from the final OCP solid, so station guides should use the same millimeter coordinate system.

Verify the STL coordinate frame using actual output files rather than assuming it matches an unrelated display transformation.

## 4. Distinguish visualization from CAD geometry

The 3D station indicator is a **visual radial-location guide**.

It is NOT:

- A measured OCP section.
- A true BRep intersection.
- An independent validation result.
- A manufacturing cross-section.

Label it accordingly in the UI and documentation.

Do not claim that a translucent plane or line overlay is the exact contour of the STEP at that station.

Actual STEP measurements remain the responsibility of the existing OCP validation layer.

---

# PART 3 — STATION SELECTION FOUNDATION

## 5. Implement reliable station identity

Current station selection is based primarily on array indices.

Make station selection robust to:

- Adding stations.
- Removing stations.
- Editing a station's r/R.
- Changing its airfoil.
- Changing its thickness or TE.
- Importing a BladeSpec JSON.
- Loading an example.
- Resetting the editor.

Prefer stable frontend-only station IDs, using or extending the existing transient `rowIds` mechanism.

Never serialize frontend-only row IDs into BladeSpec.

Station selection must follow the intended station after insertion or removal of other rows.

If the selected station itself is removed, switch deterministically to an existing valid station and update the inspector.

Do not allow an out-of-range index to crash the UI.

## 6. Clear visual selection in the table

Enhance the existing Airfoil Stations table.

Required:

- Clearly highlighted selected row.
- A visible selected-state indicator.
- The selected station's index and r/R.
- Existing Inspect action must select the station.
- Appropriate keyboard accessibility.
- Clear focus indication.
- Consistent behavior after changing station count.

Do not remove current profile selection or numeric editing features.

---

# PART 4 — 3D STATION VISUALIZATION

## 7. Add selected-station visualization to BladeViewer

Extend:

`frontend/src/components/BladeViewer.tsx`

Introduce a reusable overlay implementation, for example:

`frontend/src/components/stationGuides.ts`

or another clearly separated Three.js helper.

The guide should visualize a station at the requested radial Y position.

Suggested representation:

- A thin line or transparent plane through the local XZ section.
- A visible selected color.
- A small station marker.
- A label identifying station number and r/R.
- Optional marker legend outside the canvas.

Use a translucent XZ plane or bounded line that is easy to interpret.

Do not use an arbitrarily shaped contour that could be mistaken for an exact CAD section.

## 8. Overlay coordinate correctness

A station at r/R = 0.60 on a 400 mm diameter blade must be placed at:

```text
R = 200 mm
Y = 120 mm
```

For a blade with root r/R = 0.18, the root guide must use the corresponding physical radius rather than an assumed 0.20 root.

The overlay must stay aligned when:

- Orbiting the camera.
- Zooming.
- Panning.
- Switching Face View.
- Switching Edge View.
- Switching Isometric View.
- Using Fit to Model.
- Expanding/restoring the viewer.
- Resizing the browser.

Place guides in the existing scene using the same model coordinates.

Do not modify the STL geometry.

Do not modify the STEP artifact.

## 9. Visual design requirements

Use a clear distinction between:

- Main selected station.
- Secondary comparison station, when active.

Suggested colors:

- Station A: orange.
- Station B: teal.

Also provide textual labels, so identification does not rely on color alone.

The station overlay should not cover the blade excessively.

Prefer adjustable opacity and restrained geometry.

A small toggle such as:

`Show Station Guides`

is desirable.

Do not automatically reset the engineer's current camera position each time a station is selected.

An explicit Focus on Station action is acceptable, but should not override orbit controls unexpectedly.

## 10. Lifecycle and GPU safety

The existing BladeViewer uses one Three.js scene and renderer.

Preserve that.

Ensure station guide objects:

- Update without reloading STL.
- Do not cause a new WebGL context.
- Are disposed when removed.
- Do not leak geometry or material objects.
- Are correctly replaced after a successful new build.
- Do not remain attached to obsolete geometry.
- Remain reliable after expand/restore operations.

Keep existing STL loading failure handling.

---

# PART 5 — CRITICAL CAD / DESIGN SYNCHRONIZATION

## 11. Separate current design from last successful CAD

This is a P0 correctness requirement.

The existing application separates:

- Current editable BladeSpec.
- Active build job.
- Last successful displayed result.
- Submitted BladeSpec snapshot.

Preserve and extend this separation.

The current 2D design preview describes the current editable BladeSpec.

The STL viewer describes the last successfully generated CAD result.

These can be different engineering designs.

**Never show new station guides over an old CAD model as though the geometry matched.**

## 12. Required stale-result behavior

Scenario:

1. User generates Blade A.
2. Blade A succeeds.
3. Station guides appear correctly on Blade A.
4. User changes a chord, station radius, or another engineering parameter.
5. Current design becomes different from the submitted CAD snapshot.

At this point:

- Keep Blade A visible if desired.
- Display the existing stale CAD warning.
- Hide or disable the current-design station guides on Blade A.
- Do not imply that selected stations refer to the old CAD.
- Continue permitting current-design 2D inspection and comparison.

The preferred initial policy is to hide guides when the displayed CAD is stale.

If an optional historical-guide mode is implemented, it must be explicitly labeled as belonging to the old submitted BladeSpec.

Avoid implementing this extra mode unless necessary.

## 13. Build lifecycle behavior

During a new build:

- Previous successful CAD may remain visible.
- Its job identity must remain unchanged.
- New design guides must not appear on it.
- Build progress belongs to the active job.

On successful completion:

- The new CAD replaces the previous result.
- Station guides become active only when the successful result's submitted BladeSpec matches the current editable BladeSpec.
- The correct station positions are restored.

On failure:

- Keep the previous valid CAD.
- Keep stale state truthful.
- Do not reassign old preview geometry to the failed job.
- Do not enable new-design station guides on the old model.

## 14. Preview revision consistency

The current canonical 2D preview is asynchronous.

Maintain an explicit association between each preview response and the BladeSpec revision that produced it.

Do not display a previous preview as though it represents a newly edited design during debounce or validation failure.

For Sprint 03B, comparison data should come only from a successful preview response matching the current editor revision.

If the preview is stale or invalid:

- Display a pending/unavailable state.
- Do not silently compare outdated section data.
- Keep the last valid preview only when clearly labeled as previous.

---

# PART 6 — AIRFOIL COMPARISON TOOL

## 15. Implement a two-station comparison workflow

Create a component such as:

`frontend/src/components/AirfoilComparison.tsx`

The engineer must be able to select:

- Station A.
- Station B.

Use existing airfoil stations from the current BladeSpec.

Provide clear controls for changing either selection.

Do not require changing a station's actual airfoil or editing the BladeSpec to compare it.

Station A and Station B should remain independent selections.

Default to two different valid stations when possible.

If the blade has only two airfoil stations, comparison must still work.

## 16. Comparison visualization

Display two contours overlaid in a shared 2D engineering coordinate system.

Use:

- Normalized chord x/c.
- Normalized normal coordinate y/c.
- Equal x/y geometric scale.
- Distinct colors.
- Clear legend.
- Upper and lower surfaces for each station.
- Leading/trailing edge references.

Do not distort the airfoil shape.

Do not automatically align each profile to its camber line or maximum-thickness point.

The primary comparison should use common LE-to-TE normalized airfoil coordinates.

Allow selection between:

**Source Profiles**

Compare unmodified original airfoil definitions.

**Resolved Design Profiles**

Compare the profiles after effective thickness and physical TE modification.

Use the backend-provided `design-preview` station data.

Do not recreate NACA or physical TE geometry independently in JavaScript.

## 17. Compare engineering measurements

Show at least:

| Measurement | Station A | Station B |
|---|---|---|
| r/R | value | value |
| Airfoil | name/type | name/type |
| Chord (mm) | value | value |
| Effective t/c | value | value |
| Geometric max t/c | value | value |
| Maximum camber/c | value | value |
| x/c of maximum thickness | value | value |
| Requested physical TE (mm) | value | value |

Optionally show the numerical difference B − A with correct units and signs.

For coordinate-based airfoils, do not invent an NACA designation.

Preserve imported-coordinate provenance where available, but do not require a library lookup to compare an embedded coordinate profile.

An imported BladeSpec must remain self-contained.

## 18. Meaning of the comparison

This is a geometric comparison.

Do not claim that one airfoil is:

- Aerodynamically better.
- More efficient.
- More suitable for an RPM.
- Structurally stronger.
- Optimized for thrust.

Such claims require aerodynamic or structural analysis, which is outside Sprint 03B.

## 19. Comparison interaction

The engineer should be able to:

1. Select Station A.
2. Select Station B.
3. View the overlaid comparison.
4. Switch Source/Resolved mode.
5. Change either selection.
6. Return to normal single-station inspection.

Comparing two stations must not modify the engineering input values.

It must not trigger Generate Blade.

It must not change any airfoil profile unless the engineer explicitly uses the separate profile-editing workflow.

---

# PART 7 — OPTIONAL DUAL STATION GUIDES

## 20. Link comparison with the 3D viewer

When comparison mode is enabled and the displayed CAD matches the current BladeSpec:

- Show Station A at its Y location.
- Show Station B at its Y location.
- Use colors matching the 2D comparison legend.
- Label both stations.

For example:

```text
Station A:
r/R = 0.20
Y = 40 mm

Station B:
r/R = 0.80
Y = 160 mm

Blade diameter:
400 mm
```

When comparison mode is disabled, display only the main selected-station guide.

If the CAD is stale, hide both current-design guides.

Do not modify the original STL.

---

# PART 8 — USER INTERFACE

## 21. Integrate into existing layout

Do not redesign the complete application.

Keep:

- Global Settings.
- Airfoil Stations.
- Airfoil Library.
- Airfoil Inspector.
- Distribution Charts.
- 3D Viewer.
- Validation Summary.
- Generated Artifacts.

Suggested additions:

In the Airfoil Stations panel:

- Selected-row indication.
- Inspect action.
- Compare action.

In the 2D inspection area:

- Single Station tab.
- Compare Stations tab.

In the 3D viewer:

- Show Station Guides toggle.
- Legend identifying the selected stations.
- Station location label.

Keep the current enlarged viewer and camera modes.

The interface must remain usable on narrower screens.

Do not crowd the application with permanent comparison overlays when the user is not using the comparison feature.

## 22. Accessibility and clarity

Provide:

- Keyboard-operable station selection.
- Clear selected states.
- Accessible labels.
- Textual station identifiers.
- Color-independent identification.
- Explicit stale-CAD warnings.
- Clear distinctions between design-preview and final-CAD data.

The engineer must always be able to answer:

"What am I inspecting: the current design or the last generated CAD?"

---

# PART 9 — TESTING

## 23. Pure coordinate tests

Create focused tests for station guide calculations.

Verify examples including:

```text
Diameter = 400 mm
R = 200 mm

r/R = 0.20 -> Y = 40 mm
r/R = 0.60 -> Y = 120 mm
r/R = 1.00 -> Y = 200 mm
```

Also test:

```text
Root r/R = 0.18
```

and a non-400 mm diameter.

Verify that guide calculations do not depend on the visual bounding-box height.

Ensure the guide plane is perpendicular to the positive Y radial axis.

## 24. Frontend state tests

Add tests for:

- Selecting a station.
- Selection after station insertion.
- Selection after station deletion.
- Selection after changing the selected station's radius.
- Importing a different BladeSpec.
- Loading examples.
- Switching between single and comparison modes.
- Selecting two different stations.
- Comparing a NACA station with an imported coordinate station.
- Returning to single-station inspection.
- Preserving current BladeSpec while comparing.

Do not remove existing Sprint 03A tests.

## 25. Preview and stale-CAD tests

Test:

1. Successful Blade A with matching editor inputs.
2. Correct guides on Blade A.
3. Edit a blade parameter.
4. Guide overlay is hidden.
5. Current-design comparison remains available after a current preview completes.
6. Start Blade B generation.
7. No new-design guides appear on Blade A.
8. Blade B succeeds.
9. Guides reappear on Blade B if current inputs still match the submitted snapshot.
10. Blade B fails.
11. Old CAD retains its correct job identity.
12. No obsolete guide is displayed as a current-design location.

Test overlapping canonical preview responses.

Do not infer design/CAD consistency from job status alone.

## 26. Three.js tests

Verify:

- Guide creation and disposal.
- Correct world coordinates.
- Marker label updates.
- Orbit/zoom compatibility.
- Face/Edge/Isometric view compatibility.
- Expand/restore compatibility.
- ResizeObserver behavior.
- No STL reload on station selection.
- No duplicate WebGL contexts.
- No geometry resource leaks after repeated station changes.

A React component test alone is not enough for real WebGL behavior.

## 27. Comparison geometry tests

For source and resolved comparison modes, verify:

- Contours equal backend-provided coordinates.
- No hidden geometric rescaling.
- x/c and y/c share one geometric scale.
- Finite TE appears according to canonical resolved coordinates.
- Chord and thickness metrics match the corresponding backend preview.
- Imported coordinates remain unmodified.
- A/B selection never mutates BladeSpec.

Do not invent independent NACA or PCHIP formulas inside frontend test mocks.

Use realistic canonical fixtures for engineering verification.

---

# PART 10 — REAL BROWSER ACCEPTANCE

## 28. Playwright acceptance workflow

Run a real Chromium test.

Suggested workflow:

```text
Open BladeGen
    ↓
Load five-section example
    ↓
Generate real CAD
    ↓
Select station r/R = 0.60
    ↓
Verify the correct 3D guide position
    ↓
Rotate and expand viewer
    ↓
Verify guide remains aligned
    ↓
Select Station A = 0.20
    ↓
Select Station B = 0.80
    ↓
Verify both guides and labels
    ↓
Compare source airfoils
    ↓
Compare resolved airfoils
    ↓
Edit Chord
    ↓
Verify current-design guides disappear from stale CAD
    ↓
Generate revised blade
    ↓
Verify guides return only after successful matching build
```

Where practical, test 3-, 5-, and 8-section designs.

At minimum, execute a real end-to-end CAD build with station-guide verification, and separate automated state/geometry tests covering the other layouts.

Capture screenshots of:

- Single selected station in 3D.
- Two comparison stations in 3D.
- Source-profile comparison.
- Resolved-profile comparison.
- Stale CAD with guides hidden.
- Matching new CAD with guides restored.

Screenshots supplement assertions.

Do not claim precise station-guide positioning solely because a colored line is visible.

Assert the numeric world Y coordinate against BladeSpec.

---

# PART 11 — ENGINEERING REGRESSION

## 29. Preserve all existing CAD acceptance cases

Run the existing backend regression suite, including:

- 3-section blade.
- 5-section baseline.
- 8-section blade.
- NACA 0008 thickness override.
- Imported 41-point analytic airfoil.

Require:

- One valid solid.
- One closed shell.
- Zero non-degenerate free edges.
- Valid BRep.
- Successful STEP round-trip.
- Existing chord/twist/axis tolerances.
- Existing physical TE tolerance.
- Existing production contour tolerances.

Do not change accepted numerical geometry behavior.

This sprint should not require modifying:

- OpenVSP adapter.
- OCP solidification.
- Canonical curve resolver.
- BladeSpec v0.2.

If any backend modification is proposed, justify it explicitly and verify that it does not change generated CAD.

---

# PART 12 — DOCUMENTATION AND DELIVERY

## 30. Documentation

Create:

`docs/SPRINT_03B_REPORT.md`

and:

`docs/SPRINT_03B_ACCEPTANCE_MATRIX.md`

Update the README where necessary.

Document:

- How station selection works.
- How 3D station guides are calculated.
- How comparison mode works.
- Source versus resolved geometry.
- How stale CAD is handled.
- Why visual station guides are not actual STEP cross-sections.
- Exact tests run.
- Remaining limitations.

## 31. Final deliverables

Provide:

- Git branch and commit SHA.
- Changed-file summary.
- Screenshots of station selection and comparison.
- Backend test results.
- Frontend unit test results.
- Playwright results.
- CAD regression results.
- Known limitations.
- Instructions for manually testing the new interface.

Do not fabricate screenshots or test results.

Do not automatically merge into main.

---

# PART 13 — ACCEPTANCE CRITERIA

Classify Sprint 03B as STRONG PASS only when:

1. Every airfoil station can be selected reliably.
2. Selection remains stable after station insertion, deletion, and editing.
3. Selected stations appear at correct physical Y coordinates in the 3D viewer.
4. Guide positions are derived from BladeSpec, not guessed from the STL bounds.
5. Camera operations do not affect guide geometry.
6. Selecting stations does not reload or modify the STL.
7. 2D inspection follows the selected station correctly.
8. Two stations can be overlaid and compared using canonical backend data.
9. Source and resolved profiles remain distinct.
10. Comparison preserves equal geometric scaling.
11. Comparison does not change BladeSpec.
12. Imported coordinate airfoils are supported in comparison.
13. Current-design guides cannot appear misleadingly on stale CAD.
14. New successful CAD activates only matching station guides.
15. Failed builds cannot relabel old CAD or activate new-design guides.
16. Existing CAD engineering regression tests remain successful.
17. Frontend tests pass.
18. Real Chromium acceptance passes.
19. Historical research files remain unchanged.

If a P0 correctness issue remains unresolved, report PASS WITH LIMITATIONS or FAIL as appropriate.

---

# STRICT SCOPE CONTROL

Do NOT implement:

- Drag-to-edit chord/twist curves.
- Direct mouse editing of airfoil geometry.
- Click-to-pick arbitrary STEP surfaces.
- True BRep section extraction for interactive preview.
- Aerodynamic analysis.
- Thrust, torque, or efficiency calculations.
- Multi-blade assemblies.
- Hub generation.
- New airfoil databases.
- Replacement CAD engines.
- Major backend redesign.

These features are outside Sprint 03B.

---

# EXECUTION ORDER

**Phase 1 — Selection State**

Implement stable station identity and selection synchronization.

**Phase 2 — 3D Guides**

Add mathematically positioned station overlays to the existing Three.js viewer.

**Phase 3 — Airfoil Comparison**

Implement source/resolved overlay comparison and engineering measurements.

**Phase 4 — State Integrity**

Complete stale-CAD protection, job-specific guide behavior, and lifecycle cleanup.

**Phase 5 — Verification**

Run React, Three.js, Chromium, and real CAD regressions.

---

# FINAL INSTRUCTION

Start implementing Sprint 03B in the current BladeGen workspace.

Do not stop after planning.

Preserve the existing engineering engine.

Do not modify historical research results.

**The desired result is a BladeGen interface where an engineer can select a radial station, identify its position on the generated 3D blade, inspect its airfoil definition, and compare it with another station—without confusing current design inputs with previously generated CAD geometry.**