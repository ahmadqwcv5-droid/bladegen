# Sprint 02 report

## Result

**PASS WITH LIMITATIONS.** Dynamic station editing, neutral project JSON,
BladeSpec-driven final-CAD validation, three/five/eight-section real builds,
and explicit NACA thickness override all pass. The only acceptance limitation
is environmental: Playwright is not installed, so no browser-level automation
was claimed. Component tests and a production frontend build were executed.

## What changed

- Added a deterministic station planner using all explicit airfoil stations,
  adjacent airfoil midpoints, and independent distribution controls.
- Replaced fixed 0.20/0.203 assumptions with domain-relative inward root/tip
  cuts. Reports retain requested and sampled radii and label inferred endpoint
  TE values separately.
- Made the first OpenVSP XSec `RadiusFrac` authoritative for root readback.
  OpenVSP 3.54.0 clamps `AFLimit` to 0.20, but correctly builds a first XSec
  at 0.18; using `AFLimit` as product root state was therefore incorrect.
- Added arbitrary airfoil-row and independent curve-row editing, stable UI row
  identities, local numeric drafts, root synchronization, explicit thickness
  overrides, effective-thickness feedback, and lossless JSON import/export.
- Added immutable submitted-spec snapshots, stale-result warnings, active-job
  protection, per-station validation details, and improved Three.js framing,
  axes, loading/error state, fit-to-model, and cleanup.
- Resolved NACA coordinates at their effective thickness before the CAD
  boundary. This prevents OpenVSP's thickness scaling from also scaling the
  physical finite trailing-edge gap.

## Explicit answers

1. **Can users add/remove airfoil stations?** Yes. Endpoint deletion is
   prevented and at least two stations are retained.
2. **Can distribution points be managed independently?** Yes, for chord,
   twist, rake, skew, and thickness, with independent counts and interpolation.
3. **Does BladeSpec retain neutral v0.2 semantics?** Yes. UI-only row IDs never
   enter JSON; no OpenVSP fields were added.
4. **Are validation stations submitted-spec driven?** Yes. No historical fixed
   station arrays remain.
5. **Is a non-0.20 root supported?** Yes. Case A passed at 0.25 and Case C at
   0.18.
6. **Did the three-section case pass?** Yes.
7. **Did the five-section regression pass?** Yes, without changing engineering
   values or tolerances.
8. **Did the eight-section case pass?** Yes, with all eight explicit stations
   represented in the validation plan.
9. **Did all final solids pass topology?** Yes: one solid, one closed shell,
   zero non-degenerate free edges, valid BRepCheck, and successful STEP
   round-trip in every acceptance case.
10. **Did geometry measurements pass?** Yes. Exact maxima are in the acceptance
    matrix and saved validation JSON.
11. **Can projects round-trip through JSON?** Yes, including coordinate
    airfoils and independent point counts.
12. **Are previews bound to generated inputs?** Yes. Successful results retain
    an immutable spec snapshot and job ID; later edits mark them stale.
13. **Does NACA override change measured CAD thickness?** Yes. NACA 0008 with
    explicit 0.10 effective thickness measured 0.100074–0.100142.
14. **What tests ran?** Listed below.
15. **What remains incomplete?** Browser-level Playwright automation was not
    run because Playwright is absent from the environment. Coordinate airfoils
    are preserved losslessly but still use an advanced JSON representation,
    not a graphical coordinate editor.

## Actual commands and results

```bash
./scripts/test_backend.sh
# 31 passed, 1 deprecation warning in 93.42 s

cd frontend && npm test
# 2 files, 14 tests passed

cd frontend && npm run build
# TypeScript and Vite production build passed

OPENVSP_ROOT=/tmp/openvsp_root/opt/OpenVSP \
LD_LIBRARY_PATH=/tmp/cminpack_root/usr/lib/x86_64-linux-gnu \
.venv/bin/pytest -q backend/tests/test_sprint02_cad_acceptance.py
# 3 passed in 220.97 s; real OpenVSP/OCP acceptance builds
```

Direct CLI builds were also executed for Cases A, B, C, and the NACA 0008
override. The tracked results are in `docs/sprint02_validation/`. Large
STEP/STL/VSP3 files remain under ignored `output/runs/` and are not committed.

## Manual browser checklist

1. Start backend and frontend, load the custom example, and add/remove an
   interior airfoil station.
2. Independently add a chord point and a twist point; change one interpolation
   method and verify the other table is unchanged.
3. Change the root and verify all six root locations update together.
4. Enter `0008`, enable an explicit 0.10 override, and confirm nominal/effective
   thickness are distinct and visible.
5. Export JSON, start a new project, import it, and compare every station and
   distribution count.
6. Generate a blade, edit one input afterward, and confirm the preview remains
   visible but is labeled stale and tied to its previous job ID.
7. Inspect topology, geometry summary, endpoint sample radii, and per-station
   measurements; then download STEP and validation JSON.
