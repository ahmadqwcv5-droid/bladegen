# Sprint 01 report

## Outcome

BladeGen Level 1 Alpha is implemented as a maintainable product around the
validated geometry core. It includes the safe research archive, independent
Python package, neutral BladeSpec v0.2 API/CLI, corrected adaptive volume,
serialized subprocess builds, editable React UI, OCP-derived Three.js preview,
downloads, validation summary, scripts, and documentation.

## Migration

- Not a Git worktree; no uncommitted changes existed.
- 24 historical root entries / 284 files moved under `00_research_archive`.
- 284/284 archived files re-hashed successfully after migration and again at
  Sprint completion; zero overwrite or integrity failures.
- Retained at root: active `.venv`, `.vscode`, and `sprint01.md`.
- Authoritative source: the Spike 01 package containing the 01C canonical
  resolver and 01D multi-airfoil/finite-TE work. The product is a clean source
  copy and contains no import from the archive.

## Product behavior

The API supplies health, examples, validation, build submission, job status,
artifact listing, and allow-listed downloads. The queue has one worker and each
job executes OpenVSP in an isolated subprocess under `output/runs/<uuid>` with a
configurable timeout. Failed processes are failed jobs; no mock geometry is used.

NACA code supplies nominal profile thickness. `thickness_override_ratio` is an
optional, explicit engineering decision; without it, a contradictory thickness
curve is rejected. The UI updates a coincident thickness control when NACA is
edited and exposes an override control. Non-coincident grids remain independent.

## Validated engineering example

The promoted finite-TE multi-airfoil example was built through the new product
pipeline at `output/runs/sprint01_reference/` and through one real FastAPI job.

- STEP: `output/runs/sprint01_reference/blade_solid.step`
- Topology: 1 solid, 1 shell, 8 faces, 0 non-degenerate free edges.
- Closed shell: true; `BRepCheck_Analyzer`: valid.
- Surface area: 17,061.538320 mm².
- Bounding box min: `[-12.740031, 39.805047, -19.209247]` mm.
- Bounding box max: `[35.573775, 200.021610, 39.762914]` mm.
- Authoritative adaptive-GK volume: **38,559.346223 mm³**, tolerance `1e-9`,
  estimated relative error `9.325e-10`.
- Fixed-rule diagnostic: 38,600.113382 mm³ (40.767159 mm³ high), confirming why
  it is not authoritative.
- STEP re-import: PASS; volume delta `6.905e-9` mm³; bbox delta `7.496e-12` mm.
- Independent OCP sectioning: PASS. Maximum chord error 0.004043 mm, twist error
  0.001591°, reference-axis error 0.004526 mm, control contour RMS/P95/max
  0.014705/0.029710/0.033974 mm, and TE error 0.018899 mm.
- Root request `r/R=0.200` was measured at the cap-clean inward cut `0.203`:
  requested TE 1.200000 mm, actual 1.181101 mm. Tip request `1.000` was measured
  at `0.9995`: requested 0.300000 mm, actual 0.300418 mm.

The preview STL was tessellated from the final validated OCP solid, not from an
independent mesh reconstruction.

## Verification executed

- Ruff: PASS, no findings.
- Backend/model/API non-CAD suite: 28 passed, 0 failed.
- Genuine end-to-end CAD regression: 1 passed in 67.44 s, producing and
  re-importing a fresh STEP and independently measuring chord/twist/TE.
- Aggregate: **29 passed, 0 failed, 0 skipped** across the executed test runs.
- Live unmocked API job: HTTP 202 → running → succeeded; all eight artifacts
  listed and the STEP download returned HTTP 200.
- Frontend `npm run build`: PASS (TypeScript + Vite, 23 modules).
- Archive integrity: 284/284 manifest files verified.

One non-failing warning remains: current Starlette warns that its `httpx`-based
`TestClient` compatibility path is deprecated. The production API is unaffected.
Vite also reports a 785 kB main JS chunk; future code splitting is appropriate.

## Start commands

```bash
./scripts/setup_backend.sh
cd frontend && npm install && cd ..
./scripts/start_backend.sh
./scripts/start_frontend.sh
```

Then open `http://127.0.0.1:5173`.

## Remaining limitations and next sprint

No browser automation was available, so UI verification consists of the
production build plus the live backend workflow; interactive browser behavior
should receive a Playwright smoke test next. Level 1 remains a single-blade CAD
tool—not a manufacturing or aerodynamic certification system.

Recommended Sprint 02: improve the editing workflow with graphical curves,
station insertion/removal, advanced coordinate-profile import/provenance,
autosave/export of BladeSpec, responsive progress/log display, code-split the 3D
viewer, and add Playwright coverage. Preserve the geometry engine and validation
tolerances unchanged.
