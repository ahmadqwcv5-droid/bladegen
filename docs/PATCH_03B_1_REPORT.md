# Patch 03B.1 — Viewer Resize and Station Guide Lifecycle

## Result

**STRONG PASS**

Patch 03B.1 fixes the fitted-camera resize regression and prevents unchanged
station-guide definitions from reallocating Three.js resources. The validated
BladeSpec, OpenVSP, OCP, airfoil, and geometry-validation mathematics were not
changed.

The work is on branch
`patch/03b.1-viewer-resize-guide-lifecycle`, based on reviewed Sprint 03B
merge `220a2712b1e1c0cd388f423a70d7e5e703cdc398`. The patch is not committed
yet, so that merge remains the current branch HEAD and there is no patch commit
SHA to report. No merge into `main` was performed.

The working tree already contained an uncommitted persistent OpenVSP runtime
repair when this patch began. It was preserved as required and is listed
separately below.

## Camera regression and policy

The Sprint 03B viewer updated the renderer and perspective aspect on resize but
left the fitted camera distance unchanged. A model fitted in one aspect could
therefore leave the frustum after the container became narrower.

The viewer now tracks two explicit framing modes:

- **Fitted** — initial load, Blade Face, Blade Edge, Isometric, and Fit to Model.
  A container resize measures the actual host, updates renderer size and camera
  aspect/projection, then calls the existing `calculateCameraFrame()` with the
  current direction and up vector. The blade-mesh box is authoritative; guide
  planes are excluded.
- **Manual** — OrbitControls pointer, wheel, pan, or zoom interaction. Resize
  updates renderer and projection only. It does not recenter the target, undo a
  close-up, or switch the selected view. Fit to Model explicitly returns to
  fitted mode.

The camera helper now derives near/far planes from the fitted box depth and
exports a real eight-corner projection measurement. Tests require every
projected x/y/z coordinate to remain within normalized device coordinates
`[-1, 1]` with a small numerical tolerance.

### Camera fixtures

Actual Three.js projection tests cover:

- long/narrow box: `(-30, 40, -12) → (35, 200, 16)`;
- short/wide stress box: `(-130, -16, -9) → (145, 28, 13)`;
- asymmetric nonzero-offset box: `(72, -35, -91) → (249, 19, 38)`;
- aspects `1.8`, `1.2`, `0.75`, and `0.50`;
- wide-to-narrow and narrow-to-wide transitions;
- preserved viewing direction, positive near plane, far greater than near;
- at least 70% normalized-axis occupancy, preventing a trivially tiny fit.

All fixture/aspect combinations passed.

### Real-browser projection measurements

The passing two-build Chromium workflow measured the canvas rather than
assuming it matched browser size. Every row reported
`data-frustum-contained=true`.

| State | Browser viewport | Canvas px | Camera aspect | Camera direction |
|---|---:|---:|---:|---|
| Wide normal | 1440 × 900 | 569.109 × 585.109 | 0.972650 | -0.529426, 0.213980, 0.820927 |
| Expanded | 1440 × 900 | 1406 × 707.063 | 1.988685 | -0.529426, 0.213980, 0.820927 |
| Restored | 1440 × 900 | 569.109 × 585.109 | 0.972650 | -0.529426, 0.213980, 0.820927 |
| Narrow page | 720 × 900 | 638 × 540 | 1.181481 | -0.529426, 0.213980, 0.820927 |

The narrow responsive layout intentionally gives the viewer a different grid
allocation, so actual canvas aspect—not browser aspect—is used for the fit.
Manual-orbit resize remained in manual mode, retained the Isometric selection,
and preserved direction within cosine similarity greater than `0.999`.

## Guide-array and resource lifecycle

The root cause was reference identity: `App` constructed a new guide array on
every render, and `BladeViewer` treated every new array as a replacement.

`App` now memoizes guide definitions from only relevant state:

- selected/A/B stable station IDs;
- inspection mode;
- station order;
- current matching canonical preview;
- blade diameter.

Build polling, messages, validation details, and other unrelated renders retain
the same guide-array reference. Stale preview changes still invalidate the
memo, so outdated locations cannot remain visible.

`StationGuideLayerController` adds a second defensive layer. It compares the
semantic guide values, authoritative model bounds, visibility, and destination
scene. Only a real display change removes/disposes/creates a group.

Instrumented test evidence:

| Scenario | Creates | Disposals before final cleanup | Result |
|---|---:|---:|---|
| Equivalent new array and cloned equal bounds | 1 | 0 | no reconstruction |
| Initial + selected station + A/B pair + changed model bounds | 4 | 3 | one replacement per real change |
| Final controller cleanup in the preceding sequence | — | 4 total | current layer disposed once |
| Repeated disabled sync | no additional create | no additional disposal | no-op |
| Primary STL geometry/material during guide disable/restore | 0 disposals | 0 disposals | preserved |

Resource disposal collects unique geometries and materials before disposal, so
shared resources cannot be disposed twice. A two-guide group still proves all
six geometries and six materials are each disposed exactly once.

The browser workflow retained one STL request, one renderer build, and the same
canvas DOM object through camera operations and repeated station changes. The
successful revised CAD artifact correctly caused a second STL request and
renderer build.

## Stale-CAD synchronization

The existing snapshot policy is unchanged and was reverified:

1. Blade A succeeds and matching guides appear.
2. A chord edit marks the displayed result stale and removes its guide layer.
3. Old CAD remains identified while Blade B runs.
4. Blade B succeeds with a distinct job/artifact.
5. Guides return only after the displayed result and canonical preview both
   match the edited BladeSpec.

The existing failed-B component test also passed: failed work cannot relabel
Blade A or enable current-design guides.

## Verification

Executed on 2026-10-12 with OpenVSP 3.54.0 and
cadquery-ocp/OpenCascade 7.9.3.1:

```text
cd frontend && npm test
15 test files, 74 tests passed in 11.86 s

cd frontend && npm run build
TypeScript/Vite passed; 38 modules transformed
(existing non-failing large-chunk warning)

cd frontend && npx playwright test e2e/sprint03b.spec.ts --project=chromium
1 real Chromium workflow passed in 2.4 min; two real CAD builds

cd frontend && npm run test:e2e
7 real Chromium workflows passed in 12.2 min

./scripts/test_backend.sh
92 passed in 382.05 s (6m22s)
1 existing Starlette/httpx deprecation warning
```

### CAD non-regression

Fresh tests passed the accepted 3-section, 5-section, 8-section, NACA 0008
override, and imported analytic profile cases. All re-imported as one solid and
one closed valid shell with zero free edges and valid STEP round trips.

| Case | Volume mm³ | Chord max mm | Twist max deg | Axis max mm | TE max mm | Contour RMS / P95 / max mm |
|---|---:|---:|---:|---:|---:|---:|
| 3 sections | 28,910.418807 | 0.002337 | 0.001784 | 0.000102 | 0.002046 | 0.007393 / 0.014322 / 0.016796 |
| 5-section baseline | 38,559.346223 | 0.004043 | 0.001591 | 0.004526 | 0.016732 | 0.014744 / 0.029710 / 0.033974 |
| 8 sections | 35,725.270721 | 0.004573 | 0.001570 | 0.004419 | 0.007775 | 0.010843 / 0.020239 / 0.024809 |
| NACA 0008 override | 24,135.299077 | 0.002337 | 0.001784 | 0.000102 | 0.002047 | 0.007248 / 0.014119 / 0.016613 |
| Imported analytic | 38,264.318717 | 0.004043 | 0.001593 | 0.004526 | 0.016732 | 0.014744 / 0.031276 / 0.036200 |

No engineering tolerance changed. The largest established STEP round-trip
volume delta remains `6.985e-9 mm³`.

## Screenshot evidence

The following were generated by the passing Chromium workflow:

- [Wide viewport with contained blade](screenshots/patch03b1/wide_viewport_full_blade.png)
- [Narrow viewport with contained blade](screenshots/patch03b1/narrow_viewport_full_blade.png)
- [Expanded viewer](screenshots/patch03b1/expanded_viewer.png)
- [Restored viewer](screenshots/patch03b1/restored_viewer.png)
- [Two station guides](screenshots/patch03b1/two_selected_station_guides.png)
- [Stale CAD with guides hidden](screenshots/patch03b1/stale_cad_guides_hidden.png)
- [New matching CAD with guides restored](screenshots/patch03b1/new_successful_cad_guides_restored.png)

No synthetic “before” screenshot was fabricated after the fix. The pre-patch
failure is reproducible from the reviewed resize code (aspect update without
refit); the new projection tests provide stronger geometric evidence than a
pixel comparison.

## Changed files

Patch-specific:

- `frontend/src/App.tsx`
- `frontend/src/Sprint03B.test.tsx`
- `frontend/src/components/BladeViewer.tsx`
- `frontend/src/components/bladeViewerCamera.ts`
- `frontend/src/components/bladeViewerCamera.test.ts`
- `frontend/src/components/stationGuides.ts`
- `frontend/src/components/stationGuides.test.ts`
- `frontend/e2e/sprint03b.spec.ts`
- `README.md`
- `docs/PATCH_03B_1_REPORT.md`
- `docs/screenshots/patch03b1/*`
- `sprint_03B_1.md`

Preserved pre-existing OpenVSP runtime repair:

- `.gitignore`
- `README.md`
- `backend/bladegen/adapters/openvsp_adapter.py`
- `scripts/setup_backend.sh`
- `scripts/start_backend.sh`
- `scripts/test_backend.sh`
- `scripts/openvsp_env.sh`
- `scripts/setup_openvsp.sh`

## Remaining limitations

- Manual close-up inspection can intentionally leave part of the blade outside
  the frustum; resize preserves that choice. Fit to Model restores containment.
- Station guides remain visual radial planes, not BRep cross-sections.
- The short/wide fixture validates camera mathematics and is not claimed as a
  propeller CAD output.
- Vite retains its existing non-failing Three.js chunk-size warning.
- The Starlette/httpx deprecation warning is unchanged.

`00_research_archive` was not modified.
