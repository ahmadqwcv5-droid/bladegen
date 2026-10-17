# BladeGen Level 1 Alpha

BladeGen turns a backend-neutral BladeSpec v0.2 JSON document into one validated
blade solid, or nests that complete blade in PropellerSpec v0.1 to generate a
validated full propeller. The blade pipeline is BladeSpec → canonical resolution
→ headless OpenVSP → OCP sewing/solidification → STEP re-import qualification.
The separate assembly pipeline copies that validated solid with exact OCP
X-axis rotations, fuses an X-axis hub, cuts and measures a through-bore, and
round-trips one authoritative assembly STEP. The browser previews only OCP-
derived STL artifacts.

## Supported scope

- Single-blade and full-propeller design modes; searchable parametric NACA and persistent imported DAT/CSV coordinate profiles.
- Canonical source/resolved 2D airfoil inspection, two-station comparison, and backend-sampled engineering charts.
- Transactional vertical chart editing in engineering units with backend validation and bounded undo/redo.
- Stable station selection with exact radial-location guides in the matching generated 3D blade.
- Dynamic airfoil stations plus independently editable distribution controls.
- Independent chord, twist, rake, skew, and thickness station grids.
- Physical finite trailing-edge thickness with measured tolerance reporting.
- Complete BladeSpec and PropellerSpec JSON new/open/export/reset with atomic import, complete project baselines, and stale-build snapshot tracking.
- A 2–8 blade-count contract with one shared runtime capability policy; 2, 3, and 4 are the only qualified build choices in this release.
- Simple cylindrical X-axis hub, positive-volume root connections, unintended-collision rejection, and coaxial through-bore.
- One valid closed STEP solid, OCP preview STL, and separate blade/assembly machine-readable validation.

Not yet included: advanced manufacturing hubs, spinner/fillets/keyway/bolt
features, independent per-blade pitch or geometry, aero analysis, optimization,
VSPAERO, authentication, or cloud execution. Counts 5–8 remain valid contract
inputs but are not production-qualified by Sprint 04A.

## Prerequisites and installation

The tested machine uses Python 3.12, the uv package manager, BladeGen's managed
fixed-plane OpenVSP 3.54.0 Linux Python runtime, cadquery-ocp/OpenCascade
7.9.3.1, Node 24.14.0, and npm 11.9.0.

```bash
./scripts/setup_backend.sh
cd frontend && npm install && cd ..
```

`setup_backend.sh` builds the pinned, project-local runtime with its required
real Python bindings under the ignored `.tooling/` directory. This does not
require root access or replace the retained stock runtime. To build, repair, or
verify only the CAD runtime, run `./scripts/setup_openvsp_fixed_plane.sh`
(`setup_openvsp.sh` is a compatibility entrypoint). `OPENVSP_ROOT` remains the
single explicit override and takes precedence, but an invalid or stock root is
rejected without fallback. See the
[managed runtime guide](docs/developer/FIXED_PLANE_RUNTIME.md).

## Run

In separate terminals:

```bash
./scripts/start_backend.sh
./scripts/start_frontend.sh
```

For the measured X-57 trial profile, run this single launcher from the
repository root instead:

```bash
./scripts/start_level1_trial.sh
```

It serves the UI at `http://127.0.0.1:5175` with a 900-second per-design
worker budget; the ordinary backend launcher retains its 300-second default.
Use the exact [user-tested X-57 BladeSpec](fixtures/reference_user_x57/blade_spec_X57.json)
for same-blade replay. See the [Level 1A scope](docs/releases/level1a/SCOPE_AND_STATUS.md)
and [sprint/task index](docs/sprints/README.md) for the evidence boundaries.

For the ordinary two-terminal start, open `http://127.0.0.1:5173`. Use **Choose from Library** at any airfoil
station to search NACA profiles or import DAT/CSV coordinates. Imported geometry is
embedded in exported BladeSpec JSON; local metadata persists under
`user_data/airfoils/`. Sparse coordinate definitions receive a non-blocking
pre-generation warning; the original coordinates are preserved and final STEP
validation remains authoritative. See [Airfoil Library](docs/user/AIRFOIL_LIBRARY.md) and
[Import Formats](docs/user/AIRFOIL_IMPORT_FORMATS.md).

Choose **Single Blade** or **Full Propeller** without losing blade-editor state.
Full Propeller exposes blade count, hub diameter/length, bore diameter, and
initial azimuth. **Validate Assembly** checks the neutral contract without
starting CAD; **Generate Propeller** performs measured intersection, collision,
Boolean, bore, and final-STEP validation. Changing any submitted blade or
assembly input marks the displayed result stale. Propeller mode shows front
(along X), side, isometric, fit, and expanded-view controls; single-blade radial
station guides are deliberately disabled for the rotated assembly.

The assembly card shows the nominal blade-root radius, current hub radius,
radial gap/overlap, and the strict exclusive hub-diameter bound. Hub length
controls axial extent and cannot close a radial gap. These editing-time values
are guidance; the backend repeats authoritative preflight and a passing result
does not replace measured CAD intersection/fusion checks. Runtime capabilities
come from GET /api/propellers/capabilities, so unsupported counts 5–8 are
rejected before a job is queued or OpenVSP is launched.

**Open JSON** identifies BladeSpec versus PropellerSpec from document structure.
A PropellerSpec restores its name, complete nested blade, and every assembly
input in Full Propeller mode. Invalid files leave the current project unchanged.
**Reset** restores the whole imported/new/example baseline. Current draft
validity, active generation, and the last successful result are shown
separately, so rejected new inputs never relabel prior CAD.

Build jobs are serialized and isolated in child
processes. Outputs live under `output/runs/<job_id>/`.

During generation, the page shows backend-confirmed CAD stages, percentage, and
elapsed time. The numeric percentage advances only when a pipeline milestone has
completed. The CAD subprocess reports at most 95%; only the job manager sets
100% after a zero exit code and required-artifact checks confirm success. A failed
job retains its last confirmed stage while the most recent successful preview and
artifacts keep their original job identity.

The normal solid viewer occupies roughly 45% of the desktop workspace. Use
**Expand Viewer** for the large inspection mode; orbit, pan, zoom, Fit to Model,
Blade Face, Blade Edge, and Isometric controls remain available. Blade Face is
the default and is derived from the loaded mesh to reveal its broad surface.
Preset and fitted views are refitted after container resize while preserving
their viewing direction. A manually orbited, panned, or zoomed inspection is
not recentered on resize; use **Fit to Model** to restore complete framing.
Press Escape or **Restore Viewer** to return without reloading the STL.

Select **Inspect** on any station to link its current canonical 2D definition to a visual XZ guide in the 3D scene. Guide Y is calculated exactly as `(diameter_mm / 2) * r_over_R`; the model bounds only size the overlay. **Compare Stations** overlays canonical source or resolved profiles at equal x/y scale and can show orange A and teal B guides. These guides are visual radial-location aids, not measured STEP cross-sections. If editor inputs differ from the displayed CAD snapshot, the old CAD remains labeled and all current-design guides are hidden until a matching build succeeds.

Distribution charts edit control values vertically while keeping each `r/R` fixed. Chord, rake, and skew are displayed in millimeters, twist in degrees, and thickness in percent t/c; BladeSpec continues to store its canonical normalized values. Drag a marker or focus it and use Arrow Up/Down (Shift for 10×). Release validates one full BladeSpec candidate before commit. Natural NACA/imported thickness controls are protected unless a NACA station has an explicit override. Undo/Redo buttons and Ctrl/Cmd+Z, Ctrl/Cmd+Shift+Z, or Ctrl+Y operate on curve transactions without generating CAD.

CLI build:

```bash
source scripts/openvsp_env.sh
.venv/bin/bladegen doctor
.venv/bin/bladegen build \
  examples/custom_multi_airfoil_finite_te.json --output output/manual
```

Full-propeller CLI builds require neither FastAPI nor React:

```bash
source scripts/openvsp_env.sh
.venv/bin/bladegen build-propeller \
  examples/propeller_three_blade.json --output output/propeller_three
```

The Sprint 04A.1 regression case uses a 400 mm blade with a two-blade 90 × 30 mm
hub and 12 mm bore:

```bash
source scripts/openvsp_env.sh
.venv/bin/bladegen build-propeller \
  examples/propeller_two_blade_hub_90x30.json --output output/propeller_90x30
```

The HTTP equivalents are `POST /api/propellers/validate` and
`POST /api/propellers/build`; job status and allow-listed downloads continue to
use `/api/jobs/{job_id}` and `/api/jobs/{job_id}/artifacts`. `GET /api/runtime`
reports generation readiness independently from input validity.

Tests, production UI build, and browser acceptance:

```bash
./scripts/test_backend.sh
cd frontend
npm test
npm run build
npx playwright install chromium  # first browser-test setup only
npm run test:e2e
```

Sprint 02 reproducible CAD examples are in `examples/sprint02_case_a_three_section.json`,
`examples/custom_multi_airfoil_finite_te.json`, and
`examples/sprint02_case_c_eight_section.json`. See the
[Sprint 02 report](docs/sprints/02/SPRINT_02_REPORT.md),
[acceptance matrix](docs/sprints/02/SPRINT_02_ACCEPTANCE_MATRIX.md), and
[Sprint 02.1 reliability report](docs/sprints/02.1/SPRINT_02_1_REPORT.md) for measured results.
The focused null/progress/camera corrections are documented in the
[Patch 02.1.1 report](docs/sprints/02.1.1/PATCH_02_1_1_REPORT.md). Sprint 03A visual design
and imported-profile CAD results are in the [Sprint 03A report](docs/sprints/03A/SPRINT_03A_REPORT.md)
and [acceptance matrix](docs/sprints/03A/SPRINT_03A_ACCEPTANCE_MATRIX.md). Sprint 03B interactive station inspection, comparison, and stale-CAD synchronization are documented in the [Sprint 03B report](docs/sprints/03B/SPRINT_03B_REPORT.md) and [acceptance matrix](docs/sprints/03B/SPRINT_03B_ACCEPTANCE_MATRIX.md). Sprint 03C visual curve editing, transaction safety, and real-CAD evidence are documented in the [Sprint 03C report](docs/sprints/03C/SPRINT_03C_REPORT.md) and [acceptance matrix](docs/sprints/03C/SPRINT_03C_ACCEPTANCE_MATRIX.md). StrictMode-safe continuous editing and no-op history integrity are documented in the [Patch 03C.1 report](docs/sprints/03C.1/PATCH_03C_1_REPORT.md).

Sprint 04A full-propeller geometry, measured 2/3/4-blade acceptance, and known
qualification limits are documented in the [Sprint 04A report](docs/sprints/04A/SPRINT_04A_REPORT.md)
and [acceptance matrix](docs/sprints/04A/SPRINT_04A_ACCEPTANCE_MATRIX.md).
Dynamic assembly preflight, result-state separation, runtime capabilities, and
complete project save/open are documented in the
[Patch 04A.1 report](docs/sprints/04A.1/PATCH_04A_1_REPORT.md) and
[acceptance matrix](docs/sprints/04A.1/PATCH_04A_1_ACCEPTANCE_MATRIX.md).
Sprint 04B reviewed bulk distribution input, airfoil-station setup, responsive
canonical evaluation, and qualified generic CAD evidence are documented in the
[Sprint 04B report](docs/sprints/04B/SPRINT_04B_REPORT.md),
[acceptance matrix](docs/sprints/04B/SPRINT_04B_ACCEPTANCE_MATRIX.md),
[performance qualification](docs/sprints/04B/SPRINT_04B_PERFORMANCE.md), and
[bulk-input format guide](docs/user/BULK_INPUT_FORMATS.md).
The managed fixed-plane native engine, fail-closed product integration, and
fresh X-57 production qualification are recorded in the
[FP-01 integration report](docs/sprints/FP01/FP01_INTEGRATION_REPORT.md) and
[acceptance matrix](docs/sprints/FP01/FP01_ACCEPTANCE_MATRIX.md).

## Limitations and licensing

OpenVSP is distributed under the NASA Open Source Agreement; OpenCascade uses
LGPL-2.1 with its additional exception. NumPy/SciPy are BSD-family, Pydantic,
FastAPI, React, Three.js, and Vite are MIT-licensed. This is dependency
awareness, not legal advice; redistribution rights, including NASA OSA terms,
must be reviewed for the intended distribution. No PropGen or other third-party
application source was copied.

See [architecture](docs/developer/ARCHITECTURE.md), [geometry conventions](docs/developer/GEOMETRY_CONVENTIONS.md),
[validation policy](docs/developer/VALIDATION_POLICY.md), and the [Patch 03A.1 engineering report](docs/sprints/03A.1/PATCH_03A_1_REPORT.md).
