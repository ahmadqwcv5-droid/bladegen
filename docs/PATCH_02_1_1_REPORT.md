# Patch 02.1.1 report

## Result

**STRONG PASS.** Missing and explicit `null` thickness overrides now have the
same engineering meaning, public build progress reaches 100% only after the job
manager confirms success, the OCP-derived preview opens in an adaptive broadside
Blade Face View, and distribution inputs remain readable on narrow screens.

The patch does not change BladeSpec engineering conventions, canonical curve
mathematics, NACA generation, the OpenVSP adapter, OCP solidification, or any
geometry tolerance. `00_research_archive` was not modified.

## Nullable thickness override

The backend field is optional and Pydantic/FastAPI serializes an absent override
as JSON `null`. The frontend type previously described only `number | undefined`,
and checks using `!== undefined` therefore interpreted the API's `null` as an
active override.

`AirfoilSection.thickness_override_ratio` is now `number | null | undefined`.
The shared `hasThicknessOverride` helper recognizes only a finite numeric value
as explicit. Rendering, effective-thickness calculation, NACA coordination, and
editor validation all use that helper. `clearThicknessOverride` removes the
property and restores the corresponding thickness-curve value to the NACA
profile's nominal ratio. Physical trailing-edge values are not touched.

Tests cover actual FastAPI example serialization, explicit `null`, an omitted
property, a numeric override, NACA 0010 to 0008 coordination, `/api/validate`,
enable/disable behavior, and JSON round-trip semantics.

## Confirmed completion semantics

The CAD subprocess now finishes at the existing 95% independent-validation
milestone and reports `confirmation / Awaiting build confirmation` after writing
artifacts. It never owns public completion.

The job manager clamps all subprocess progress to 95% while a job is queued,
running, or failed. Only after a zero subprocess exit and verification of every
required artifact does the manager atomically set `status = succeeded`, stage
`complete`, and progress 100%. The progress component additionally renders 100%
only for `succeeded` jobs as a defensive UI invariant.

Regression tests prove that legacy or malformed running/failed 100% input is
shown as 95%, nonzero exit after the final milestone fails below 100%, and a
missing required artifact also fails below 100%.

## Engineering camera

Blade Face View is selected after every STL load. The direction is derived from
the loaded mesh rather than from a reference-blade constant:

1. Triangle normals contribute area-weighted outer products in the blade's XZ
   transverse plane.
2. The dominant eigen-direction identifies the pressure/suction broad-surface
   normal even though opposite surface normals cancel as vectors.
3. Blade Edge View uses the perpendicular transverse direction.
4. The known Y radial axis is projected into the camera plane to keep the blade
   visually upright. Isometric View combines the derived face and edge axes.

Fit to Model evaluates all eight bounding-box corners against both vertical and
horizontal perspective field of view. It therefore adapts to the actual canvas
aspect ratio, including narrow and expanded modes. `ResizeObserver` refits the
current orientation after a resize. Expand/restore still reuses the same scene,
mesh, controls, renderer, and WebGL context; cleanup and late-STL protection are
preserved.

Unit tests verify direction recovery on a rotated broad blade, upright radial
orientation, and corner containment for wide and narrow perspective cameras.
Real Playwright builds exercised Face, Edge, Isometric, Fit, resize,
expand/restore, and progress completion for 3-, 5-, and 8-section blades.

## Numeric tables

Distribution tables now have a local horizontal scroll container, tabular
numerals, sensible column minima, and 6.5 rem (104 px in the tested browser)
minimum input widths. A Chromium test at a 390 px viewport verifies the input
width, value visibility, and local `overflow-x: auto`; the viewer layout is not
made smaller to accommodate the table.

## Fresh CAD regression

The full backend run used OpenVSP 3.54.0 and cadquery-ocp/OpenCascade 7.9.3.1.
These values came from a fresh final STEP re-import and match the tracked Sprint
02 acceptance matrix at its published precision.

| Case | Solid / shell / free edges | Closed / valid | Volume mm3 | Chord max mm | Twist max deg | Axis max mm | TE max mm |
|---|---:|---:|---:|---:|---:|---:|---:|
| 3 sections, root 0.25 | 1 / 1 / 0 | true / true | 28,910.418807 | 0.002337 | 0.001784 | 0.000102 | 0.002046 |
| 5-section reference | 1 / 1 / 0 | true / true | 38,559.346223 | 0.004043 | 0.001591 | 0.004526 | 0.016732 |
| 8 sections, root 0.18 | 1 / 1 / 0 | true / true | 35,725.270721 | 0.004573 | 0.001570 | 0.004419 | 0.007775 |
| NACA 0008, effective t/c 0.10 | 1 / 1 / 0 | true / true | 24,135.299077 | 0.002337 | 0.001784 | 0.000102 | 0.002047 |

All geometry summaries passed. All re-imports retained one solid, one shell, a
closed valid BRep, and zero non-degenerate free edges. The largest round-trip
volume delta was `6.905e-9 mm3`; the largest bounding-box coordinate delta was
`7.496e-12 mm`. No CAD source or tolerance was changed.

## Browser evidence

- [3-section normal Face View](screenshots/patch02_1_1/three_section_normal_face.png)
- [3-section expanded Face View](screenshots/patch02_1_1/three_section_expanded_face.png)
- [5-section normal Face View](screenshots/patch02_1_1/five_section_normal_face.png)
- [5-section expanded Face View](screenshots/patch02_1_1/five_section_expanded_face.png)
- [8-section normal Face View](screenshots/patch02_1_1/eight_section_normal_face.png)
- [8-section expanded Face View](screenshots/patch02_1_1/eight_section_expanded_face.png)

Screenshots supplement functional checks: Playwright also asserted the default
view state, distinct Face/Edge/Isometric rendered images, exact canvas/host size
after resize, successful restore with Escape, and absence of any non-success API
response at 100%.

## Verification executed

```text
./scripts/test_backend.sh
50 passed, 1 existing Starlette/httpx deprecation warning in 324.19 s

cd frontend && npm test -- --reporter=dot
6 files, 35 tests passed

cd frontend && npm run build
TypeScript and Vite production build passed; 30 modules transformed

cd frontend && npx playwright test e2e/patch-camera.spec.ts
1 passed in 5.7 min; actual OpenVSP/OCP 3/5/8-section builds

cd frontend && npx playwright test e2e/job-failure.spec.ts e2e/real-build.spec.ts
2 passed in 1.2 min; result identity/failure race and real CAD workflow

cd frontend && npx playwright test e2e/numeric-table.spec.ts
1 passed in 4.5 s; narrow-screen numeric readability
```

No final verification test failed or was skipped. An initial camera-matrix
attempt stopped at the OpenVSP stage because the ephemeral `/tmp` OpenVSP
runtime was absent after an environment reset. OpenVSP 3.54.0 and its runtime
library were restored, the same test was rerun without code concessions, and it
passed all three real blades. Vite retains its non-failing warning that the
Three.js production chunk is over 500 kB.

## Files changed

- `README.md`
- `backend/api/services/jobs.py`
- `backend/bladegen/pipeline.py`
- `backend/tests/test_patch_02_1_1.py`
- `frontend/src/types/bladespec.ts`
- `frontend/src/editor/bladespecEditor.ts`
- `frontend/src/editor/bladespecEditor.test.ts`
- `frontend/src/App.tsx`
- `frontend/src/nullableThickness.test.tsx`
- `frontend/src/components/BuildProgress.tsx`
- `frontend/src/components/BuildProgressCompletion.test.tsx`
- `frontend/src/components/BladeViewer.tsx`
- `frontend/src/components/bladeViewerCamera.ts`
- `frontend/src/components/bladeViewerCamera.test.ts`
- `frontend/src/components/DistributionTable.tsx`
- `frontend/src/patch02_1_1.css`
- `frontend/e2e/patch-camera.spec.ts`
- `frontend/e2e/numeric-table.spec.ts`
- `docs/PATCH_02_1_1_REPORT.md`
- `docs/screenshots/patch02_1_1/*.png`

## Remaining limitations

- Build execution remains serialized to one isolated CAD worker.
- Percentages are confirmed engineering milestones, not elapsed-time estimates;
  a long operation can legitimately remain at one value.
- Coordinate airfoils remain editable through neutral JSON rather than a
  graphical point editor.
- The production bundle size warning remains a performance follow-up, not a
  correctness or engineering blocker.

The patch remains on `sprint/02.1.1-engineering-ui-fixes`; it has not been
merged into `main`.
