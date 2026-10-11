# Sprint 03A report

## Result

**STRONG PASS.** BladeGen now has a persistent searchable airfoil library,
bounded deterministic DAT/CSV import, a canonical source/resolved 2D inspector,
and backend-sampled engineering charts for all five distributions. A real
non-NACA imported profile completed browser export/re-import and produced one
valid closed STEP solid through OpenVSP/OCP.

The BladeSpec v0.2 contract, canonical curve mathematics, OpenVSP adapter,
OCP solidification, and established tolerances remain in place.
`00_research_archive` was not modified.

## Implemented workflow

### Library and import

`AirfoilLibrary` combines on-demand canonical NACA profiles with atomic local
JSON persistence for imported profiles. It stores provenance, explicit license
state, both SHA-256 values, point counts, normalization policy, measurements,
and notes. `user_data/airfoils/` is mutable and Git-ignored.

The importer supports conventional upper-first single-contour DAT, single-
contour CSV, and explicit `upper`/`lower` CSV. It bounds bytes and points,
requires finite ordered surfaces, detects crossings and ambiguity, sanitizes
filenames, and never accepts a destination path. Non-unit data requires an
explicit normalization checkbox; otherwise source points are preserved without
smoothing or resampling.

### Canonical preview

`POST /api/design-preview` validates the live BladeSpec and calls the existing
canonical resolver, NACA generator, TE policy, and SciPy evaluator. It returns
source and resolved contours plus 251 canonical samples and original controls
for chord, twist, rake, skew, and thickness. Physical chart units are derived
from `R = diameter_mm / 2`. It starts no OpenVSP process and writes no CAD file.

React debounces requests by 250 ms, aborts superseded fetches, uses revision
checks, retains the last valid preview during invalid drafts, and labels every
2D view as a design definition rather than final-CAD validation.

### Engineering UI

Every radial station can open the library, search/filter, inspect measurements,
preview another NACA code or imported profile, apply, or cancel. Direct NACA
editing remains available. Applying coordinate geometry embeds the full neutral
arrays and coordinates only that station's thickness control to natural t/c.
The physical TE millimeter value and unrelated distribution controls are not
changed.

The inspector switches between source and resolved design contours and reports
local chord, nominal/effective/geometric t/c, camber, locations, source TE gap,
and requested physical TE. One tab-selected distribution chart is shown at a
time above all authoritative numeric tables. Lines are backend samples; markers
are original controls; hover reports engineering values.

## Imported-profile / OpenVSP finding

OpenVSP's PROP thickness curve interacts with FILE_AIRFOIL coordinates. The
tested correct behavior is obtained when the active thickness control equals
the source profile's measured natural maximum t/c. The UI applies that explicit
resolution, and the canonical resolver now rejects contradictory hand-authored
coordinate BladeSpecs before preview or CAD generation.

The first real test deliberately exposed a separate sparse-definition issue:
an independent five-point-per-surface contour retained 11% thickness but
OpenVSP's smooth surface representation differed by up to `0.493 mm` from the
piecewise-linear canonical expectation. No tolerance was weakened. The final
acceptance fixture is an independently specified analytic contour with 41
committed points per surface. It passed the additional imported-profile `0.050 mm` maximum acceptance target
at `0.036200 mm`, as well as the historical `0.120 mm` production control-section
maximum gate. Sprint 03A originally mislabeled the stricter target as the
production gate; Patch 03A.1 corrects that wording without changing either value. This is source-definition density, not downstream
resampling of a user upload.

See [the acceptance matrix](SPRINT_03A_ACCEPTANCE_MATRIX.md) for all measured
CAD results and [import formats](AIRFOIL_IMPORT_FORMATS.md) for exact policies.

## Verification

```text
./scripts/test_backend.sh
76 passed, 1 existing Starlette/httpx deprecation warning in 401.87 s

cd frontend && npm test -- --reporter=dot
11 files, 45 tests passed

cd frontend && npm run build
TypeScript/Vite passed; 35 modules transformed

cd frontend && npm run test:e2e
5 Chromium tests passed in 8.8 min
```

The full browser suite includes the prior failed-job identity test, narrow
numeric-table test, actual 3/5/8-section camera matrix, prior real build and
download scenario, and the new DAT → selector → inspector/charts → embedded
BladeSpec export/re-import → real validated STEP scenario.

Two development attempts failed and were corrected transparently: the sparse
coordinate CAD gate described above, and an initial browser assertion with an
ambiguous duplicate text locator. No final test was skipped or failed.

## Screenshot evidence

- [Searchable Airfoil Selector](screenshots/sprint03a/airfoil_selector.png)
- [Canonical NACA 2412 Inspector](screenshots/sprint03a/naca_2412_inspector.png)
- [Imported coordinate Inspector and metadata](screenshots/sprint03a/imported_airfoil_inspector.png)
- [Chord distribution chart](screenshots/sprint03a/chord_distribution.png)
- [Twist distribution chart](screenshots/sprint03a/twist_distribution.png)
- [Final validated imported-airfoil blade](screenshots/sprint03a/imported_airfoil_validated_step.png)

## Main files added or changed

- Backend: `airfoils/importers.py`, `airfoils/library.py`,
  `airfoils/geometry_metrics.py`, `api/routes/airfoils.py`, and the coordinate
  t/c guard in `curves/resolver.py`.
- Frontend: `AirfoilSelector`, `AirfoilInspector`, `DistributionChart`, live
  preview/API types, station application logic, and `sprint03a.css`.
- Tests: importer/library/preview/coordinate semantics/imported CAD backend
  suites, React selector/inspector/chart/stale-response suites, and one complete
  real-browser workflow.

## Remaining limitations

- The library provides import/read/search but no delete or metadata-edit UI.
- Library display names are metadata, not BladeSpec fields. After standalone
  JSON re-import, embedded coordinate geometry is retained exactly but shown as
  the generic `Coordinate profile` label.
- Supported import layouts are intentionally narrow; ambiguous historical DAT
  variants are rejected.
- Numeric tables remain the only editing surface; charts are not draggable.
- Build execution remains one serialized CAD worker.
- Vite retains its non-failing Three.js chunk-size warning.

The work remains on `sprint/03a-airfoil-library-visual-tools` and has not been
merged into `main`.
