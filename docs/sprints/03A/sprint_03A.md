# SPRINT 03A — BladeGen Airfoil Library & Visual Engineering Design Tools



## Mission

Develop the first part of Sprint 03: **Airfoil Library & Visual Design Tools**.

BladeGen already has a validated geometry engine, dynamic airfoil stations, independent radial distributions, real STEP generation, CAD validation, progress reporting, and an expandable 3D viewer.

The next objective is to make the application more useful for engineers **before they generate the CAD model**.

Implement:

1. A practical searchable Airfoil Library.
2. Import of user-defined DAT/CSV airfoil coordinate files.
3. A 2D Airfoil Inspector with engineering measurements.
4. Interactive plots for Chord, Twist, Rake, Skew, and Thickness distributions.

This sprint must produce a working engineering workflow, not merely visual mockups.

---

# PART 1 — PROJECT PREPARATION

## 1. Inspect the existing implementation

The last reviewed main commit was:

`06501025bb28efcce3b4faf9a5f07ad5d09a57b8`

Check the current repository and Git working tree before modifying anything.

Create a dedicated branch:

`sprint/03a-airfoil-library-visual-tools`

Preserve uncommitted work.

Do not modify `00_research_archive`.

Important existing modules include:

- `backend/bladegen/airfoils/canonical.py`
- `backend/bladegen/curves/canonical.py`
- `backend/bladegen/curves/resolver.py`
- `backend/bladegen/models/blade_spec.py`
- `backend/api/routes/blades.py`
- `frontend/src/App.tsx`
- `frontend/src/editor/bladespecEditor.ts`
- `frontend/src/components/DistributionTable.tsx`
- `frontend/src/components/BladeViewer.tsx`
- `frontend/src/types/bladespec.ts`

Review them before creating new abstractions.

## 2. Preserve the engineering engine

The established pipeline must remain:

```text
BladeSpec v0.2
    ↓
Canonical Curve and Airfoil Resolution
    ↓
OpenVSP
    ↓
OCP Solidification
    ↓
Validated STEP
```

Do not replace OpenVSP, OCP, SciPy, or the current canonical mathematics.

Do not weaken the existing geometry tolerances.

Do not change the BladeSpec v0.2 format merely to accommodate library metadata.

A saved BladeSpec containing coordinate-based airfoils must remain self-contained and reproducible without the original imported DAT/CSV file.

---

# PART 2 — AIRFOIL LIBRARY

## 3. Create a lightweight Airfoil Library

Build a backend-neutral Airfoil Library layer.

It should support two initial categories:

**Category A — Parametric NACA 4-digit**

Use the existing canonical NACA generator rather than storing thousands of redundant coordinate files.

Provide useful default selections:

- NACA 0008
- NACA 0010
- NACA 0012
- NACA 2412
- NACA 4412
- NACA 4415

The user must still be able to enter other valid NACA 4-digit codes.

Respect the mathematical constraints enforced by the existing generator. Do not present unsupported profiles as valid.

**Category B — Imported coordinate airfoils**

Provide a reusable local library of user-imported airfoil coordinates.

Use a small file-based registry or similarly lightweight local storage.

Do not introduce PostgreSQL, remote services, cloud storage, or user accounts.

Suggested structure, adaptable to the existing project:

```text
backend/bladegen/airfoils/
    canonical.py
    importers.py
    library.py
    geometry_metrics.py

backend/api/routes/
    airfoils.py

user_data/airfoils/
    index.json
    profiles/
```

Treat `user_data/airfoils/` as mutable local application data, separate from the research archive and generated CAD results.

Do not commit arbitrary user-imported profiles or personal metadata to Git.

## 4. Library metadata

Each imported profile should have:

- Display name.
- Airfoil category.
- Original filename.
- Source/provenance, if supplied.
- License information, if known.
- Import format.
- Original-file SHA-256.
- Canonical-coordinate SHA-256.
- Coordinate point counts.
- Derived geometric thickness/camber measurements.
- Optional user notes.

Unknown licensing information must remain explicitly unknown.

Do not automatically claim that third-party profile data are public-domain or commercially redistributable.

Avoid automatically downloading or copying public airfoil databases in this sprint.

---

# PART 3 — DAT/CSV IMPORT

## 5. Implement a robust coordinate importer

The application must allow users to select an airfoil coordinate file from their computer.

Support at minimum:

### DAT

A conventional single-contour airfoil `.dat` format, commonly ordered:

```text
Trailing edge, upper surface
        ↓
Leading edge
        ↓
Trailing edge, lower surface
```

Support optional title/header lines where unambiguous.

### CSV

Support clearly documented coordinate layouts such as:

```csv
x,y
1.0,0.0
0.5,0.06
0.0,0.0
0.5,-0.04
1.0,0.0
```

Also consider explicit surface identification when the format contains an `upper`/`lower` field.

Implement deterministic format detection.

Do not assume every DAT file uses the same ordering.

If a file uses an unsupported or ambiguous layout, reject it with an informative message instead of guessing.

A parser for every historical airfoil format is not required in Sprint 03A.

## 6. Convert imported files to the neutral coordinate representation

The existing product representation expects:

```json
{
  "type": "coordinates",
  "upper": [[0.0, 0.0], [0.5, 0.06], [1.0, 0.0]],
  "lower": [[0.0, 0.0], [0.5, -0.04], [1.0, 0.0]]
}
```

Both surfaces must use the documented leading-edge-to-trailing-edge ordering.

The imported shape must be translated into this representation before it enters the geometry engine.

Preserve meaningful source geometry.

Do not smooth, refit, or substantially resample an imported profile without an explicit, documented operation.

Normalize non-normalized coordinates only under an unambiguous, documented policy, preferably with explicit user confirmation and a preview of the transformation.

Do not arbitrarily clamp small negative leading-edge x/c offsets. Cambered normal-offset airfoils may legitimately extend slightly beyond the nominal 0–1 x/c interval.

## 7. Import validation

Detect and reject:

- Empty files.
- Unsupported encoding or formatting.
- NaN and infinite values.
- Missing upper or lower surface.
- Too few points.
- Duplicate or degenerate input that prevents creating a valid contour.
- Invalid surface ordering.
- Clearly self-intersecting profiles.
- Unsupported normalization or ambiguous leading/trailing edges.
- Unreasonably large files.

Provide understandable errors that identify the cause.

Use bounded file sizes, safe filenames, and controlled local storage.

Never accept an arbitrary client-supplied filesystem destination.

A malformed airfoil upload must not crash the application or replace a previously valid selected profile.

## 8. Persistence and reproducibility

Imported profiles should remain available in the local library after restarting the application.

However, the generated BladeSpec must embed the actual normalized coordinates.

A CAD project must not require a library lookup to rebuild after its BladeSpec JSON has been exported.

Library metadata and the neutral geometric definition are separate concerns.

If profiles are updated or replaced in the library, existing saved BladeSpecs must retain their original embedded geometry.

---

# PART 4 — AIRFOIL SELECTOR

## 9. Add Airfoil selection to the existing station editor

Currently the Airfoil Stations table is centered on NACA codes and displays coordinate profiles mainly as JSON.

Replace this limited selection experience with an Airfoil Selector.

Required functionality:

- Open selector from an airfoil station.
- Search profiles by name.
- Filter between NACA and imported profiles.
- Preview the selected profile.
- View its geometric measurements.
- Apply the selected profile to the active station.
- Cancel without modifying the current BladeSpec.

The user should always know which radial station they are modifying.

Show the chosen profile name in the station table.

Keep NACA identifiers as strings so leading zeroes are preserved.

Do not remove support for direct NACA code editing unless an equally convenient alternative is implemented.

## 10. Coordinate airfoil and thickness semantics

This is a critical engineering requirement.

The existing program has a separate `thickness_distribution` and optional `thickness_override_ratio`.

When the user selects a new NACA or imported coordinate profile, the interface must not silently produce contradictory thickness intent.

For NACA, preserve the established behavior:

- Nominal thickness derives from the code.
- Explicit overrides remain explicit.
- Physical TE thickness is a separate millimeter-valued requirement.

For imported coordinate airfoils:

- Determine and display geometric maximum thickness/chord from the canonical coordinates.
- Make the relationship with the current thickness distribution explicit.
- Offer a clear resolution if the imported profile's natural t/c differs from the current thickness curve.
- Do not silently alter unrelated distribution points.
- Do not silently rescale the imported shape under an undocumented policy.

**Important:** Verify how OpenVSP's `PROP_THICK` interacts with imported FILE_AIRFOIL coordinates.

An imported profile must not appear correct in the 2D preview while being unexpectedly scaled in the final STEP.

If existing backend behavior is inconsistent, implement the smallest compatible correction and demonstrate it through a real imported-profile CAD test.

Do not claim that imported airfoils preserve their shape based only on JSON or OpenVSP coordinate readback.

---

# PART 5 — 2D AIRFOIL INSPECTOR

## 11. Build a real engineering profile viewer

Create a reusable component, for example:

`frontend/src/components/AirfoilInspector.tsx`

Display a 2D airfoil plot with:

- Upper and lower surfaces.
- Chord line.
- Leading edge.
- Trailing edge.
- Clear x/c and y/c axes.
- Equal geometric scale, or an explicitly labeled vertical exaggeration.
- Effective local chord in millimeters.
- Nominal and effective thickness ratios, where applicable.
- Maximum geometric thickness and its approximate x/c location.
- Maximum camber and its location.
- Requested physical TE thickness.

Use engineering-friendly formatting.

The inspector must be useful both inside the Airfoil Selector and when selecting an existing radial station.

## 12. Show the actual section definition

The inspector should distinguish:

**Source profile**

The original NACA or imported coordinate definition.

**Resolved design profile**

The section after applying the selected effective thickness and the canonical physical trailing-edge modification.

The latter must match the explicit coordinates intended for OpenVSP.

Show the TE change clearly when relevant.

For example:

```text
Station: r/R = 0.60
Airfoil: NACA 2412

Local chord: 54.0 mm
Effective t/c: 0.1200
Requested TE: 0.80 mm

Preview: Resolved Design Section
```

This is a design-definition preview, not a measurement of the final STEP.

Label it accordingly.

Do not claim the 2D section has passed final CAD validation before Generate has run.

---

# PART 6 — CANONICAL PREVIEW API

## 13. Avoid duplicate geometric mathematics

The canonical source of truth already exists in Python:

- `bladegen.airfoils.canonical`
- `bladegen.curves.canonical`
- `bladegen.curves.resolver`

Do not independently recreate NACA geometry or product PCHIP behavior in React solely for display.

Introduce a lightweight backend endpoint for design previews.

Suggested API:

```text
GET  /api/airfoils/catalog
POST /api/airfoils/import
GET  /api/airfoils/{profile_id}
POST /api/design-preview
```

Adjust naming to the existing API conventions.

`POST /api/design-preview` should accept the current neutral BladeSpec and return enough information to display:

- The explicit airfoil stations and their resolved 2D profiles.
- The selected station's source and resolved contours.
- Its physical chord and TE information.
- Dense sampled distribution curves.
- Original user control points.

The preview endpoint must not run OpenVSP or OCP.

It should use the canonical geometry definitions and SciPy mathematical interpolation directly.

A fast 2D preview is not a substitute for final STEP validation.

## 14. Handle live editing safely

Preview requests may overlap while the user edits parameters.

Implement:

- Debounced updates.
- Cancellation or response-revision checks.
- Loading state.
- Validation feedback.
- Protection against old responses overwriting newer inputs.

Do not crash if an airfoil code is temporarily incomplete while typing.

An invalid draft must not be shown as an authoritative preview.

Avoid triggering expensive full CAD builds during ordinary table editing.

---

# PART 7 — SPANWISE DISTRIBUTION CHARTS

## 15. Add visual curves for all five distributions

Create a reusable chart component, for example:

`frontend/src/components/DistributionChart.tsx`

Support:

- Chord.
- Twist.
- Rake.
- Skew.
- Thickness ratio.

Each chart must display:

- Radial position `r/R` on the horizontal axis.
- The evaluated canonical distribution as a continuous line.
- Original user control points as markers.
- Engineering units.
- Tooltip or hover values.
- A visual distinction between control points and interpolated samples.

The chart must update when the user edits the corresponding table.

Keep the numerical table as the authoritative editing interface.

Do not implement drag-to-edit in this sprint.

## 16. Preserve exact interpolation semantics

The product already supports:

- Linear.
- SciPy PCHIP.

Sample both methods from the backend canonical evaluator.

Do not implement a separate approximation that merely looks similar to PCHIP.

Use enough points to produce a smooth display, for example approximately 201–401 samples over the valid radial domain.

The charts must match the engineering values that OpenVSP ultimately receives through the canonical resolver.

Test intermediate points, not merely the original control points.

## 17. Display meaningful engineering units

The BladeSpec stores some quantities normalized by blade radius.

For the visual charts, prefer engineering-readable units:

- Chord: mm.
- Twist: degrees.
- Rake: mm.
- Skew: mm.
- Thickness: percent t/c, clearly labeled.

With:

```text
R = diameter_mm / 2
```

the graphical display may convert normalized values to physical units.

Do not change the underlying BladeSpec units or semantics.

Changing blade diameter must update the physical-unit charts correctly.

## 18. Integrate charts into the existing editor

The current application displays multiple distribution tables.

Introduce a clearer presentation, such as:

- A chart above its corresponding table.
- Tabs for Chord/Twist/Rake/Skew/Thickness.
- Expandable individual distribution panels.

Choose a layout that remains usable with the expanded 3D viewer.

Avoid placing five large plots on the screen simultaneously if that makes the application excessively long.

Do not remove dynamic control-point insertion/removal.

Do not break existing numerical editing.

---

# PART 8 — PERFORMANCE AND ROBUSTNESS

## 19. Keep previews lightweight

The design-preview operation should normally complete quickly for typical 3–8-section designs.

It must not create OpenVSP processes.

It must not create STEP or STL files.

Avoid transferring unnecessarily dense data when only one selected profile is displayed.

If large coordinate profiles are imported, keep rendering and memory usage bounded.

Consider code splitting or lazy-loading chart UI if it significantly increases the frontend bundle.

## 20. Preserve existing functionality

The following must remain working:

- Dynamic airfoil stations.
- Independent distribution grids.
- Root-radius synchronization.
- NACA thickness overrides.
- Finite physical trailing-edge thickness.
- Neutral BladeSpec import/export.
- Existing job/progress state.
- Expanded 3D viewer.
- Valid solid STEP generation.
- Independent CAD validation.

The new library and preview functions must integrate with these features rather than bypass them.

---

# PART 9 — REQUIRED TESTS

## 21. Airfoil import tests

Create representative fixtures for:

1. Valid single-contour DAT.
2. Valid CSV airfoil.
3. Symmetric airfoil.
4. Cambered airfoil.
5. Finite-TE source profile.
6. Reversed or unsupported ordering.
7. Duplicate/degenerate points.
8. Invalid numeric values.
9. Unsupported format.
10. Missing upper/lower contour.

For valid imports, verify:

- Upper/lower ordering.
- Normalization.
- Leading/trailing edge geometry.
- Coordinate checksum consistency.
- Preservation of actual profile shape.
- Correct derived thickness/camber.

Do not use only NACA-generated fixtures; include at least one independent, explicitly defined coordinate profile.

## 22. Preview consistency tests

For NACA 4412 and NACA 0012, verify that backend-generated preview coordinates match the canonical generator.

For a station with finite TE, verify that the resolved 2D preview matches the canonical TE modification within tight numerical tolerance.

For Linear and PCHIP, compare chart samples with direct SciPy/canonical evaluations at many non-control locations.

Verify physical-unit conversions.

## 23. Frontend tests

Add Vitest/React Testing Library tests covering:

- Search NACA library.
- Select a profile.
- Cancel selection.
- Import DAT.
- Import CSV.
- Reject an invalid file without corrupting the project.
- Display 2D source and resolved profiles.
- Show TE values.
- Update charts after changing control points.
- Preserve Linear/PCHIP behavior.
- Change station profile without affecting unrelated stations.
- Preserve coordinate profiles through JSON export/import.
- Reject stale asynchronous preview responses.

## 24. Real-browser tests

Extend the existing Playwright suite.

Execute the workflow:

```text
Open BladeGen
    ↓
Load example
    ↓
Open Airfoil Library
    ↓
Preview NACA profile
    ↓
Select different Airfoil
    ↓
Inspect its 2D profile
    ↓
Change Chord/Twist values
    ↓
Observe distribution charts update
    ↓
Import custom DAT airfoil
    ↓
Apply it to one radial station
    ↓
Export BladeSpec
    ↓
Re-import BladeSpec
    ↓
Generate real STEP
    ↓
Verify successful CAD validation
```

Use a real FastAPI/OpenVSP/OCP pipeline for at least the final import-to-STEP acceptance workflow.

Do not claim a complete test passed if the final STEP was never generated.

---

# PART 10 — REAL CAD ACCEPTANCE

## 25. Regression blades

Re-run the established acceptance cases:

- Three-section blade.
- Five-section baseline.
- Eight-section blade.
- NACA 0008 with effective thickness override.

Confirm that existing tolerances remain unchanged.

## 26. Imported airfoil acceptance

Create an additional real CAD test using at least one non-NACA coordinate profile imported through the new DAT/CSV workflow.

Use a clearly documented and independently specified coordinate fixture.

Place the imported profile at an actual radial control station.

Generate a new STEP through OpenVSP/OCP.

Require:

- One valid solid.
- One closed shell.
- Zero non-degenerate free edges.
- Valid BRepCheck.
- Successful STEP round-trip.
- Existing chord/twist/axis/TE tolerances.
- Control-contour fidelity against the actual imported canonical profile.

Verify that the imported airfoil has not been silently replaced with a NACA profile or unexpectedly rescaled.

If backend adjustments are necessary for imported-profile semantics, document them carefully.

Do not loosen geometry tolerances to hide an import or scaling problem.

---

# PART 11 — DOCUMENTATION

## 27. Deliverables

Create:

```text
docs/SPRINT_03A_REPORT.md
docs/SPRINT_03A_ACCEPTANCE_MATRIX.md
docs/AIRFOIL_LIBRARY.md
docs/AIRFOIL_IMPORT_FORMATS.md
```

Update the root README and architecture documentation where necessary.

Document the supported DAT/CSV formats and rejected formats explicitly.

Explain the distinction between:

- NACA parametric profiles.
- Imported coordinate profiles.
- Effective thickness ratio.
- Physical trailing-edge thickness.
- 2D design preview.
- Final STEP geometry validation.

Include screenshots of:

- Airfoil Selector.
- NACA 2D Inspector.
- Imported coordinate airfoil.
- Chord distribution chart.
- Twist distribution chart.
- Final validated blade using an imported airfoil.

---

# PART 12 — ACCEPTANCE CRITERIA

Classify Sprint 03A as STRONG PASS only if:

1. The Airfoil Library is searchable and functional.
2. Parametric NACA profiles use the existing canonical generator.
3. DAT and CSV imports create valid neutral coordinate airfoils.
4. Invalid imports are rejected safely.
5. Imported profiles persist in the local library.
6. Saved BladeSpec files remain self-contained.
7. The user can select a different profile for any radial station.
8. Thickness and finite-TE semantics remain correct.
9. The 2D Inspector shows the actual resolved design profile.
10. Chord/Twist/Rake/Skew/Thickness charts use canonical backend evaluations.
11. Linear/PCHIP changes are represented correctly.
12. Visual previews update safely without running OpenVSP.
13. Existing engineering features and regression tests remain functional.
14. A real imported-coordinate airfoil passes final STEP validation.
15. Backend tests pass.
16. Frontend tests pass.
17. At least one real-browser import-to-STEP workflow passes.
18. No historical research files are modified.

Report PASS WITH LIMITATIONS if any critical behavior is not fully verified.

Do not fabricate successful CAD tests or screenshot evidence.

---

# PART 13 — STRICT SCOPE CONTROL

Do NOT implement yet:

- Multi-blade propeller geometry.
- Hub or bore modeling.
- Aerodynamic performance calculations.
- Thrust/torque optimization.
- Automatic airfoil recommendation by RPM.
- VSPAERO.
- A large internet-scraped airfoil database.
- Direct 3D station picking.
- Dragging distribution control points on charts.
- Advanced airfoil comparison overlays.
- Cloud storage or authentication.
- A replacement geometry backend.

These belong to future development phases.

---

# EXECUTION ORDER

Implement in this order:

**Phase 1 — Airfoil Library Core**

Build the local registry, canonical import parsers, validations, and tests.

**Phase 2 — Canonical Preview API**

Provide accurate 2D resolved airfoils and backend-sampled distribution curves without OpenVSP.

**Phase 3 — User Interface**

Implement the searchable selector, DAT/CSV import, 2D inspector, and distribution charts.

**Phase 4 — Engineering Integration**

Ensure profile selection and imported coordinates interact correctly with thickness, TE, BladeSpec import/export, and existing dynamic stations.

**Phase 5 — Full Verification**

Run backend/frontend/Playwright tests, previous CAD regressions, and the new imported-airfoil STEP acceptance.

Stop and report a genuine engineering blocker rather than silently replacing or weakening validated geometry behavior.

---

# FINAL INSTRUCTION

Start implementing immediately in the existing BladeGen workspace.

Preserve the geometry core.

Do not create another research-only spike.

Do not stop after architecture planning.

Do not automatically merge into `main` unless explicitly authorized.

**The desired result is an engineering application in which users can discover and inspect airfoils, import custom profiles, understand chord/twist and other radial distributions visually, and then generate a verified STEP from those exact design inputs.**