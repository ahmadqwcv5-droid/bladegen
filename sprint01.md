# SPRINT 01 — BladeGen Level 1 Alpha: Project Foundation & First Working Application

## Project objective

We are transitioning from successful geometry research spikes to the development of a real software product named **BladeGen**.

The product's first-level objective is:

**A user enters engineering parameters for a propeller blade, selects airfoil profiles at radial stations, generates a validated 3D blade, previews it, and exports a manufacturing-oriented solid STEP file.**

The geometry engine already exists and has been tested extensively.

Do NOT restart development from scratch.

Your mission in this sprint is to:

1. Safely organize and archive the entire existing research workspace.
2. Promote the latest validated geometry engine into a clean product codebase.
3. Establish a maintainable backend and frontend architecture.
4. Implement the first functional, end-to-end user workflow.
5. Preserve all engineering regression tests.
6. Document the project so the next development sprint can continue immediately.

The sprint must produce working software, not merely a proposal or architecture document.

---

# PART A — WORKSPACE ORGANIZATION

## 1. Identify the current workspace root

First inspect the actual current workspace.

Determine:

- Current working directory.
- Existing project folders.
- Spike and test directories.
- Existing source-code locations.
- Existing Git repository, if present.
- Existing virtual environments and external dependencies.
- Any configuration files required by the coding agent or development environment.

Do not assume the workspace is empty.

Do not assume a hard-coded filesystem path.

Define:

`WORKSPACE_ROOT = the existing workspace root`

All future product development must happen directly under this root.

## 2. Create one permanent research archive

Create this directory:

`WORKSPACE_ROOT/00_research_archive/`

This folder is the permanent historical archive of all research and experimentation completed before Sprint 01.

Move all existing research-related workspace files and folders inside it.

This includes, when present:

- Test 01, Test 02, Test 03, Test 04, Test 05.
- Spike 00A and Spike 00A.1.
- Spike 01, Spike 01B, Spike 01C, Spike 01D.
- Existing CAD files.
- STEP and STL outputs.
- Reports and validation CSV/JSON files.
- Existing experimental Python scripts.
- Source benchmarks and associated assets.
- Temporary research directories and notes.

**Preserve the original directory names and relative internal structure.**

Example:

Before:

```text
WORKSPACE_ROOT/
├── test_01/
├── test_02/
├── spike_01_bladegen/
├── spike_01B_custom_blade/
├── spike_01C_curve_resolution/
├── spike_01D_multi_airfoil_te/
└── other_research_files/
```

After:

```text
WORKSPACE_ROOT/
├── 00_research_archive/
│   ├── test_01/
│   ├── test_02/
│   ├── spike_01_bladegen/
│   ├── spike_01B_custom_blade/
│   ├── spike_01C_curve_resolution/
│   ├── spike_01D_multi_airfoil_te/
│   └── other_research_files/
│
├── backend/
├── frontend/
├── tests/
├── examples/
├── docs/
├── scripts/
└── README.md
```

The actual existing folder names may differ. Preserve them rather than renaming them to match this illustration.

## 3. Important archival safety requirements

The migration must be non-destructive.

Before moving files:

- Inventory existing files and directories.
- Record file sizes and SHA-256 hashes.
- Check for uncommitted Git changes.
- Identify symlinks and mounted external paths.
- Identify existing application/environment configuration.

Rules:

- Do not delete any existing source files.
- Do not overwrite files during migration.
- Do not modify historical CAD artifacts.
- Do not rewrite old validation reports.
- Do not modify historical results to fit the new project.
- Do not move anything outside WORKSPACE_ROOT.
- Do not recursively move the archive folder into itself.

Keep `.git` at repository root if it exists. Retain or carefully recreate essential repository/agent configuration and active development-environment files in their required locations. Document every exception to the archival move.

Do not blindly move an active virtual environment in a way that invalidates its paths. Preserve or recreate development environments safely.

Use `git mv` where appropriate.

After archival, verify file integrity against the pre-migration inventory.

Create:

```text
00_research_archive/
├── ARCHIVE_README.md
└── ARCHIVE_MANIFEST.csv
```

The manifest must contain:

- Original path.
- Archived path.
- File size.
- SHA-256.
- Migration status.

Make the archived research tree effectively immutable by project convention.

**New product code must never depend on imports from 00_research_archive.**

---

# PART B — PROMOTE THE EXISTING GEOMETRY ENGINE

## 4. Locate the authoritative BladeGen implementation

Inspect the existing research folders.

The latest validated product architecture is:

```text
BladeSpec v0.2
    ↓
Canonical Curve Resolver
    ↓
Canonical Airfoil Generation
    ↓
ResolvedBladeSpec
    ↓
OpenVSP Adapter
    ↓
OCP Sewing / Solidification
    ↓
Valid Solid STEP
    ↓
Independent Geometry Validation
```

The earlier project used a Python package named `bladegen`, with core implementation under the Spike 01 codebase and subsequent enhancements from Spikes 01C and 01D.

Locate the actual latest implementation before copying anything.

Do not assume the newest code resides inside the latest spike folder.

## 5. Create the production backend

Create:

```text
WORKSPACE_ROOT/backend/
├── bladegen/
│   ├── models/
│   ├── curves/
│   ├── airfoils/
│   ├── adapters/
│   ├── solid/
│   ├── validation/
│   ├── pipeline.py
│   └── cli.py
│
├── api/
│   ├── main.py
│   ├── routes/
│   ├── services/
│   └── schemas/
│
├── pyproject.toml
└── README.md
```

Adapt the actual existing package layout where necessary. Avoid restructuring validated internal code simply for aesthetic reasons.

Copy the authoritative validated engine into `backend/bladegen/`.

This is a new product working copy.

Preserve the original research implementation inside the archive.

Do not rebuild the generator using CadQuery.

The backend must continue to use:

- Python 3.12
- Pydantic v2
- NumPy
- SciPy
- OpenVSP Python API
- OCP / OpenCascade
- pytest

Add FastAPI for the application interface.

Use Ruff for code quality.

Ensure that the backend can be installed and imported without manipulating the Python path to reference old spike directories.

## 6. Preserve BladeSpec v0.2

The product must use the already validated backend-neutral BladeSpec.

Supported concepts include:

- Diameter.
- Root radius ratio.
- Reference-axis location.
- Rotation direction.
- Airfoil sections.
- NACA 4-digit profiles.
- Explicit coordinate-based airfoils.
- Chord distribution.
- Twist distribution.
- Rake distribution.
- Skew distribution.
- Thickness distribution.
- Physical trailing-edge thickness.
- Linear/PCHIP curve interpolation.

Do not add OpenVSP-specific fields to BladeSpec.

No large schema redesign is allowed in Sprint 01.

---

# PART C — ENGINEERING CORRECTIONS

## 7. Correct authoritative volume computation

During independent review of Spike 01D, a mass-properties inconsistency was found.

The finite-TE STEP returned approximately:

```text
Fixed integration:
38600.113382 mm³

Adaptive integration:
38559.346131 mm³
```

This is a numerical integration discrepancy, not evidence of a defective solid.

Do not use the default fixed-order mass-properties calculation as the authoritative engineering volume.

Use the previously validated adaptive OpenCascade integration method with documented convergence settings.

Use a second numerical method where practical as a diagnostic cross-check.

Report:

- Adaptive volume.
- Integration method and tolerance.
- STEP pre-export volume.
- Re-imported STEP volume.
- Volume round-trip difference.

Important: A matching STEP round-trip volume does not independently prove that the absolute volume calculation is accurate when both measurements use the same integration method.

Maintain separate checks for CAD integrity and volume integration accuracy.

## 8. Resolve nominal airfoil thickness consistently

Spike 01D showed that changing the tip from NACA 0010 to NACA 0008 also required a matching change in the thickness distribution.

The user interface must avoid inconsistent engineering intent.

Implement clear semantics:

- The selected NACA profile provides its nominal thickness ratio.
- An explicitly requested thickness override is a separate engineering choice.
- The backend validates consistency or resolves the documented override policy.
- Changing a selected NACA profile must not silently retain a contradictory old nominal thickness value.

Preserve backwards compatibility with existing BladeSpec v0.2 input files.

If full automatic resolution requires a schema change, document the issue first and implement the smallest backward-compatible correction justified by the existing schema.

Do not silently break old examples.

## 9. Preserve trailing-edge validation

Spike 01D measured up to:

`0.018899 mm`

TE thickness error against the existing `0.020 mm` tolerance.

This result passed, but the maximum occurred at a root-interior cut rather than at the exact root cap plane.

Maintain the existing physical-TE checks.

Report both:

- Requested radial station.
- Actual radial location used for CAD measurement.

Do not label an inward-offset cut as an exact endpoint measurement.

Do not weaken the existing TE tolerance.

---

# PART D — FIRST WORKING PRODUCT API

## 10. Create the FastAPI application

Build a local backend API.

Minimum endpoints:

```text
GET  /api/health

GET  /api/examples

GET  /api/examples/{example_id}

POST /api/validate

POST /api/build

GET  /api/jobs/{job_id}

GET  /api/jobs/{job_id}/artifacts
```

The API must accept neutral BladeSpec JSON.

The validation endpoint must return understandable field-level validation errors.

The build endpoint must call the actual geometry engine.

No mock geometry generation is allowed in production mode.

## 11. Build execution model

OpenVSP has mutable process-level state and should not be treated as a safe concurrent geometry engine by default.

Use an isolated process for each build, or a clearly controlled single-worker architecture.

For Sprint 01:

- Only one active OpenVSP geometry build is required at a time.
- Prevent conflicting simultaneous builds.
- Each build gets a unique output directory.
- Every build records status and errors.
- Failed builds must not be marked successful.
- Do not expose arbitrary filesystem paths through API input.
- Use safe, generated job identifiers.
- Set a configurable build timeout.

Store outputs under a working directory such as:

```text
WORKSPACE_ROOT/output/runs/{job_id}/
```

This is active generated data, not research archive content.

Do not make `output/` a source-code dependency.

## 12. Define build artifacts

For a successful build, provide:

```text
blade_solid.step
blade_preview.stl
blade_spec.json
validation.json
```

Optionally retain:

```text
blade_openvsp.vsp3
blade_openvsp.step
```

for debugging.

The preview STL must be derived from the final validated solid geometry, preferably by tessellating the OCP solid or re-imported STEP.

Do not generate an unrelated preview representation that could disagree with the exported CAD.

---

# PART E — FRONTEND FOUNDATION

## 13. Create the first BladeGen user interface

Use:

- React
- TypeScript
- Vite
- Three.js for the 3D preview

Do not add a database, user accounts, authentication, cloud deployment, or aerodynamic simulation in this sprint.

The application is local-first.

Create:

```text
WORKSPACE_ROOT/frontend/
├── src/
│   ├── components/
│   ├── pages/
│   ├── api/
│   ├── types/
│   └── App.tsx
├── package.json
└── README.md
```

Aim for a clean engineering application, not a demo landing page.

Use practical form inputs and clear engineering units.

## 14. Initial user workflow

Implement the following complete workflow:

```text
Open BladeGen
     ↓
Load example BladeSpec
     ↓
View/edit blade parameters
     ↓
Validate inputs
     ↓
Generate Blade
     ↓
View build status
     ↓
Preview generated blade
     ↓
Download STEP
     ↓
Inspect validation results
```

All steps must be connected to the real backend.

## 15. Parameter editor

Provide these editable groups:

### Global settings

- Blade name.
- Diameter in mm.
- Root radius ratio.
- Reference-axis fraction.
- Rotation direction.

### Airfoil stations

An editable table containing:

- `r/R`
- Airfoil type.
- NACA code.
- Trailing-edge thickness in mm.

Start with NACA 4-digit support.

Keep coordinate-based airfoil definitions supported in the backend, even if the UI initially provides them through an advanced JSON editor.

### Spanwise distributions

Provide editable curves or tables for:

- Chord.
- Twist.
- Rake.
- Skew.
- Thickness, where applicable.

**Important:** Airfoil-station radii and distribution-control radii do not necessarily coincide.

Do not force all curves onto one shared station grid if that changes BladeSpec semantics.

A simple tabbed/table-based UI is acceptable for Sprint 01.

Graphical curve editing can come in a later sprint.

## 16. Example loader

Promote at least one validated neutral example into:

```text
WORKSPACE_ROOT/examples/
```

Use the Spike 01D finite-TE multi-airfoil example as the primary user-facing demonstration.

Do not depend on the archived file at runtime.

The UI should initially open this example or make it available through a clear Load Example action.

---

# PART F — 3D PREVIEW AND RESULTS

## 17. Implement a basic 3D viewer

Use Three.js to display the generated preview mesh.

Required:

- Orbit rotation.
- Zoom.
- Fit-to-model.
- Visible blade geometry.
- Simple neutral material.
- Loading and error states.

The preview must correspond to the actual generated solid.

Do not require OpenVSP's graphical interface.

## 18. Validation summary

After generation, show:

- Solid count.
- Closed-shell status.
- BRep validity.
- Free-edge count.
- Volume with calculation method.
- STEP round-trip status.
- Geometry-validation summary where available.

Do not claim that a geometrically valid blade is aerodynamically optimized or manufacturing-certified.

Provide download links for:

- Solid STEP.
- Validation JSON.
- Preview STL.

---

# PART G — PROJECT QUALITY

## 19. Regression tests

Promote relevant existing tests from the research implementation into the new product test suite.

The previous Spike 01D campaign reported 44 passing tests.

Do not merely copy that claim into the new README.

Actually execute the applicable tests after migration.

Preserve the existing engineering tolerances.

Add at least one new genuine end-to-end regression test that:

1. Loads a BladeSpec v0.2 JSON.
2. Executes the actual geometry engine.
3. Produces a new STEP file.
4. Re-imports the newly generated STEP using OCP.
5. Confirms one valid closed solid.
6. Independently measures representative chord/twist/TE values.
7. Fails if any required validation threshold is exceeded.

Do not make all new tests depend solely on historical validation CSV files.

## 20. API tests

Test:

- Health endpoint.
- Valid BladeSpec submission.
- Invalid input rejection.
- Example loading.
- Build-job status lifecycle.
- Successful artifact retrieval.
- Failed build reporting.

## 21. Frontend verification

At minimum verify:

- Frontend production build succeeds.
- Example parameters load correctly.
- Editing a parameter updates the submitted BladeSpec.
- Generate calls the real backend.
- Job status is visible.
- STEP download works.
- 3D preview loads.

If browser automation is available, add one lightweight application smoke test.

---

# PART H — DOCUMENTATION AND RUNNING

## 22. Root README

Create:

`WORKSPACE_ROOT/README.md`

It must explain:

- What BladeGen does.
- Its current supported scope.
- Installation prerequisites.
- Python/OpenVSP/OCP requirements.
- Frontend prerequisites.
- How to install the backend.
- How to start the API.
- How to start the UI.
- How to build a blade from CLI.
- Where output files are stored.
- How to run tests.
- Known limitations.

Provide exact commands tested on the actual machine.

## 23. Development scripts

Create convenient commands or scripts, conceptually:

```text
scripts/setup_backend.sh
scripts/start_backend.sh
scripts/start_frontend.sh
scripts/test_backend.sh
```

Scripts must use the new project paths.

No script may require importing Python code directly from:

`00_research_archive/`

The installed OpenVSP Python API may require environment setup specific to its official Linux distribution. Preserve that compatibility and document it.

## 24. Engineering documentation

Create:

```text
docs/ARCHITECTURE.md
docs/GEOMETRY_CONVENTIONS.md
docs/VALIDATION_POLICY.md
docs/MIGRATION_REPORT.md
docs/SPRINT_01_REPORT.md
```

`GEOMETRY_CONVENTIONS.md` must clearly define the radial axis, chord direction, positive twist, rake/skew signs, reference axis, units, and TE measurement convention.

`MIGRATION_REPORT.md` must include:

- Original workspace inventory.
- Archive structure.
- Archived file integrity verification.
- Source selected as the authoritative v0.2 engine.
- Any files excluded from archival and why.
- Any known historical scripts requiring old relative paths.

`SPRINT_01_REPORT.md` must document completed tasks, tests, failures, remaining limitations, and how to start the working application.

## 25. Licensing awareness

Record dependencies and their licenses, especially OpenVSP and OCP.

Do not copy third-party code from PropGen or other public repositories during this sprint.

Do not claim commercial redistribution is automatically permitted without examining the relevant licenses and NASA Open Source Agreement requirements.

This is a documentation requirement, not a request for a complete legal review.

---

# PART I — SCOPE CONTROL

## 26. What not to build yet

Do NOT implement:

- Complete multi-blade propellers.
- Hub manufacturing geometry.
- Propeller aerodynamic optimization.
- Thrust/torque simulation.
- VSPAERO integration.
- A large airfoil database.
- Cloud services.
- Authentication.
- Complex CAD feature editing.
- A separate geometry engine.

Those belong to future sprints.

Our first objective is a dependable working application around the validated blade geometry core.

## 27. Airfoil library preparation

Prepare the architecture for future airfoil-library support.

The future library should support:

- Parametric NACA families.
- Named coordinate-based airfoils.
- User-imported DAT/CSV airfoils.
- Profile metadata and provenance.

For Sprint 01, provide basic NACA 4-digit selection only, with the existing coordinate-based input capability retained.

Do not populate a large database yet.

---

# PART J — ACCEPTANCE CRITERIA

Sprint 01 is successful only if all these conditions are met:

1. Existing research files are preserved under `00_research_archive`.
2. No archived file is lost or unintentionally overwritten.
3. The new product directories exist outside the archive at workspace root.
4. The production backend no longer imports research code from old spike folders.
5. BladeSpec v0.2 remains compatible with validated existing examples.
6. OpenVSP and OCP build a real blade from user-supplied parameters.
7. A valid solid STEP is generated and independently re-imported.
8. Volume reporting uses the corrected adaptive method.
9. A working frontend can load/edit a BladeSpec and request generation.
10. The resulting blade can be previewed in 3D.
11. The user can download STEP and validation results.
12. Backend tests and frontend builds are actually executed.
13. Previously validated engineering tolerances are not weakened.
14. No mock result is substituted for failed CAD generation.
15. Full installation and run instructions are available.

If a required dependency is unavailable, report the blocker honestly, retain the completed source, and mark the relevant acceptance criterion as incomplete.

Do not declare a successful end-to-end build without actually running one.

---

# PART K — FINAL DELIVERABLE

At completion, provide:

### 1. Final workspace tree

Show the actual new root structure and the research archive.

### 2. Migration results

Number of archived files, integrity verification, and any exceptions.

### 3. Working application

Commands required to start the backend and frontend.

### 4. Engineering example

Build the validated Spike 01D finite-TE multi-airfoil example using the NEW product pipeline.

Report:

- Output STEP path.
- Solid validity.
- Face count.
- Volume using the adaptive method.
- Representative geometric validation metrics.
- STEP round-trip.

### 5. Test results

Report actual passed/failed/skipped tests.

### 6. Known issues

List unresolved issues without concealing them.

### 7. Next sprint recommendation

Suggest the next focused development sprint, prioritizing interface usability and engineering workflow improvement rather than rewriting the geometry engine.

---

# FINAL INSTRUCTION

**Start implementing immediately. Do not stop after planning.**

First archive the historical workspace safely.

Then promote the validated BladeGen engine into the new project.

Then implement and test the first real user-to-STEP workflow.

Work directly in WORKSPACE_ROOT.

Keep all new application development outside `00_research_archive`.

The objective is a maintainable BladeGen application, not another isolated research experiment.