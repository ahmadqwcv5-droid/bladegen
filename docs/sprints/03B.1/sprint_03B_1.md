# SPRINT 03B.1 — BladeGen Viewer Resize & Station Guide Lifecycle



## Objective

Implement a focused reliability and performance patch for the BladeGen 3D viewer introduced in Sprint 03B.

Sprint 03B successfully added:

- Stable airfoil station selection.
- Radial station guides in the Three.js viewer.
- Two-station airfoil comparison.
- Source/resolved section inspection.
- Stale-CAD protection.
- Correct guide coordinates derived from BladeSpec.

Source-code review identified two issues that should be corrected before moving to Visual Curve Editing.

**Issue 1 — Camera framing regression**

The viewer no longer recalculates a suitable camera distance after its container changes aspect ratio.

**Issue 2 — Unnecessary station-guide reconstruction**

The parent component creates a new station-guide array during ordinary React renders. This can trigger unnecessary Three.js guide disposal and reconstruction even when the engineering selection has not changed.

The patch must fix both issues without changing the validated CAD geometry engine.

---

# PART A — WORKSPACE PREPARATION

## 1. Inspect the repository

Review the current Git state.

The last reviewed Sprint 03B merge commit was:

`220a2712b1e1c0cd388f423a70d7e5e703cdc398`

Check whether newer commits exist.

Create a dedicated branch:

`patch/03b.1-viewer-resize-guide-lifecycle`

Preserve uncommitted changes.

Do not modify `00_research_archive`.

Do not automatically merge into `main`.

## 2. Relevant source files

Inspect:

- `frontend/src/App.tsx`
- `frontend/src/components/BladeViewer.tsx`
- `frontend/src/components/bladeViewerCamera.ts`
- `frontend/src/components/stationGuides.ts`
- `frontend/src/components/stationGuides.test.ts`
- `frontend/src/components/bladeViewerCamera.test.ts`
- `frontend/src/sprint03b.css`
- `frontend/e2e/sprint03b.spec.ts`

Preserve the existing architecture.

Do not modify OpenVSP, OCP, canonical airfoils, BladeSpec v0.2, or the geometry validation engine.

---

# PART B — FIX CAMERA RESIZE BEHAVIOR

## 3. Confirmed regression

In the previous viewer implementation, resizing performed:

```typescript
renderer.setSize(width, height, false)

if (mesh) {
  frameModel(currentDirection(), camera.up)
}
```

The Sprint 03B implementation currently performs:

```typescript
renderer.setSize(width, height, false)
```

without reevaluating camera framing.

Although the perspective camera aspect ratio is updated, the distance from the camera to the model remains unchanged.

Consequently, a model that fitted a wide viewport can become clipped after the viewer is narrowed.

This is particularly noticeable with short, wide blade geometries.

## 4. Required camera behavior

When the viewer container changes dimensions:

1. Measure the actual container width and height.
2. Update the renderer size.
3. Update the perspective camera aspect ratio.
4. Update the projection matrix.
5. Determine whether the existing camera framing remains valid.
6. Adjust framing when necessary.
7. Preserve the current viewing orientation.

Do not simply reset every resize to Blade Face View.

Do not unnecessarily reset the user's custom camera orientation.

Do not recreate the STL mesh.

Do not recreate the renderer or WebGL context.

## 5. Preserve engineering camera controls

The existing controls must continue to work:

- Blade Face View.
- Blade Edge View.
- Isometric View.
- Fit to Model.
- Orbit.
- Zoom.
- Pan.
- Expand Viewer.
- Restore Viewer.

A resize must not silently switch the selected viewing direction.

For example:

```text
User selects Isometric View
        ↓
User expands viewer
        ↓
User restores normal viewer
        ↓
Isometric orientation is preserved
        ↓
Entire blade remains visible
```

## 6. Prefer conditional camera refitting

Avoid a simplistic implementation that resets the camera target after every resize.

Recommended approach:

Introduce an explicit distinction between:

- Fitted or preset camera framing.
- Camera framing manually adjusted by the user.

When the camera is in fitted framing mode, recompute the required fitting distance after the viewport aspect changes.

Use the existing:

`calculateCameraFrame()`

from:

`frontend/src/components/bladeViewerCamera.ts`

The fitting algorithm already accounts for:

- Perspective vertical field of view.
- Horizontal field of view.
- Bounding-box corners.
- Camera direction.
- Camera up vector.

Reuse or extend it rather than introducing an unrelated fitting formula.

Preserve the existing orbit direction.

When the user has manually panned or zoomed:

- Do not unexpectedly recenter their chosen inspection target.
- Do not undo intentional close-up inspection.
- Maintain valid rendering and camera projection.
- Keep Fit to Model available to restore complete visibility.

If necessary, implement a small explicit camera-framing state to distinguish these behaviors.

Document the chosen policy.

## 7. Correct geometric acceptance

A correctly fitted model must remain inside the camera's visible frustum.

For an automatically fitted model, project the eight bounding-box corners into normalized device coordinates.

Require:

```text
-1 <= projected_x <= 1

-1 <= projected_y <= 1

-1 <= projected_z <= 1
```

Allow only a small numerical tolerance.

Do not use canvas size equality as a substitute for checking geometric visibility.

Do not include station-guide planes in the authoritative model bounding box used for camera fitting.

The actual blade mesh defines the main fitting extent.

Station guides are visual overlays.

---

# PART C — REGRESSION TEST FOR WIDE BLADES

## 8. Create a camera stress-test fixture

The existing five-section reference blade is relatively long and narrow.

This geometry does not adequately stress horizontal camera framing.

Add a synthetic Three.js geometry fixture representing a short, wide object or blade-like solid.

This fixture is for testing camera mathematics and viewer behavior only.

It must not be presented as a validated propeller CAD output.

Test cases should include:

- Long, narrow blade.
- Short, wide blade.
- Asymmetric bounding box.
- Model with nonzero X/Z offset.

Use dimensions and aspect ratios that expose the original failure.

## 9. Required resize scenarios

Test at least:

```text
Wide viewport:
Aspect ratio = 1.8

Normal viewport:
Aspect ratio = 1.2

Narrow viewport:
Aspect ratio = 0.75

Very narrow viewport:
Aspect ratio = 0.50
```

Acceptance requirements:

- All bounding-box corners remain visible when fitted mode is active.
- The model maintains its proportions.
- Camera direction remains consistent.
- Near and far clipping planes remain valid.
- The model is not unnecessarily small.
- No camera jump occurs when selecting another station.
- Expanded and restored views retain valid framing.

Also test a manually orbited model.

Verify that resizing does not unexpectedly restore the default view.

---

# PART D — STATION GUIDE PERFORMANCE

## 10. Current rendering problem

Inspect:

`frontend/src/App.tsx`

The current implementation constructs a new station-guide array during every React render:

```typescript
const stationGuides: StationGuide[] = ...
```

Meanwhile:

`frontend/src/components/BladeViewer.tsx`

contains an effect similar to:

```typescript
useEffect(() => {
  guidesRef.current = guides
  guidesEnabledRef.current = guidesEnabled
  showGuidesRef.current = showGuides

  syncGuides()
}, [guides, guidesEnabled, showGuides])
```

Because arrays are compared by reference, ordinary parent rerenders may trigger guide reconstruction even when their contents are identical.

This can cause unnecessary:

- Geometry creation.
- Material creation.
- GPU resource disposal.
- Scene graph updates.

Correct this behavior.

## 11. Memoize guide definitions

Use React `useMemo` or another stable derived-state mechanism.

The guide array should change only when relevant engineering state changes.

Relevant dependencies include:

- Selected station identity.
- Comparison Station A identity.
- Comparison Station B identity.
- Inspection mode.
- Station ordering.
- Station radial positions.
- Blade diameter.
- Current matching canonical preview.

Avoid unstable inline dependency arrays.

Do not let unrelated state changes recreate the guide definitions.

Examples of unrelated updates:

- Build elapsed-time polling.
- Generic status-message changes.
- Moving between validation details.
- Editing an unrelated interface-only preference.
- Rerendering the parent without changing station selection.

## 12. Separate guide state from guide geometry

The current `stationGuides.ts` already contains:

- `stationYmm()`
- `makeStationGuide()`
- `createStationGuideGroup()`
- `disposeStationGuideGroup()`

Preserve this separation.

Do not move engineering-coordinate calculations into the React rendering loop.

Guide world position must continue to be:

```text
Y = (diameter_mm / 2) * r_over_R
```

Guide width/depth may depend on the STL bounding box.

Guide Y must never depend on the STL bounding box.

## 13. Avoid rebuilding unchanged guide layers

Within `BladeViewer`, ensure the Three.js guide group is replaced only when its actual display requirements change.

Valid reconstruction triggers include:

- Selecting a different station.
- Changing A/B comparison selections.
- Switching between single and comparison modes.
- Hiding/showing guides.
- Switching to a new generated CAD model.
- Changing the physical guide locations after a new matching build.

Invalid reconstruction triggers include:

- An unrelated React rerender.
- Updating a status message.
- Changing a component that does not affect guide geometry.

Keep the existing guide colors and labels.

## 14. Preserve guide disposal

When replacement is genuinely required:

1. Remove the previous guide group.
2. Dispose its geometries.
3. Dispose its materials.
4. Create the new guide group.
5. Attach it to the existing Three.js scene.

Do not dispose the primary blade STL geometry during a station selection.

Do not recreate:

- The scene.
- The renderer.
- The OrbitControls instance.
- The STL loader.
- The WebGL context.

Also ensure that failed or superseded asynchronous STL loads cannot attach obsolete guides to a newer model.

---

# PART E — PRESERVE STALE-CAD SAFETY

## 15. Do not weaken Sprint 03B result synchronization

Sprint 03B introduced important behavior:

- Current editable BladeSpec is separate from the displayed CAD.
- Submitted BladeSpec snapshots identify generated artifacts.
- Station guides appear only on matching CAD.
- Guides disappear when CAD becomes stale.
- Old successful CAD remains correctly identified while a new build runs.
- A failed build cannot relabel old CAD.

Preserve all of these rules.

The performance optimization must not cache guides so aggressively that outdated station locations remain displayed.

Guide memoization must correctly invalidate when the engineering definition changes.

## 16. Required stale-CAD sequence

Test:

```text
Generate Blade A
      ↓
Show correct station guides
      ↓
Modify Chord
      ↓
Current CAD becomes stale
      ↓
Hide station guides
      ↓
Generate Blade B
      ↓
While B runs, keep old CAD correctly identified
      ↓
B succeeds
      ↓
Show guides only when B matches current BladeSpec
```

Also test B failing.

No stale or incorrectly positioned guide may remain.

---

# PART F — FRONTEND TESTS

## 17. Camera unit tests

Extend:

`frontend/src/components/bladeViewerCamera.test.ts`

Add explicit tests for:

- Wide-to-narrow viewport transitions.
- Narrow-to-wide transitions.
- Short-wide geometry.
- Asymmetric bounding boxes.
- Preserved viewing direction.
- Bounding-box corner containment.
- Valid near/far planes.
- Correct perspective aspect ratio.

Use actual Three.js camera projection in tests.

Do not test only the scalar distance returned by the fitting helper.

## 18. Guide lifecycle tests

Extend:

`frontend/src/components/stationGuides.test.ts`

and add component-level tests where useful.

Verify:

1. Unchanged guide definitions do not trigger reconstruction.
2. Unrelated parent rerenders do not reconstruct guide geometry.
3. Changing the selected station triggers the expected update.
4. Changing comparison A/B triggers the expected update.
5. Disabling guides removes the existing layer.
6. Re-enabling guides restores the correct layer.
7. Switching CAD artifacts uses the correct model bounds.
8. All removed guide resources are disposed exactly once.
9. The primary STL geometry remains intact.
10. Guide physical Y coordinates remain unchanged by camera resizing.

Use spies or instrumentation to count genuine creation/disposal operations.

Do not rely only on DOM labels.

## 19. Existing frontend regressions

Run all existing frontend tests.

Preserve:

- Dynamic station editing.
- Airfoil Library.
- DAT/CSV import.
- Source/resolved inspection.
- Station comparison.
- Canonical distribution charts.
- Correct chart hover.
- Progress reporting.
- Preview revision protection.
- Stale CAD behavior.

Run the TypeScript/Vite production build.

---

# PART G — REAL BROWSER VERIFICATION

## 20. Playwright acceptance

Extend the existing browser suite.

Required workflow:

```text
Open BladeGen
      ↓
Load five-section example
      ↓
Generate real CAD
      ↓
Select Station 3
      ↓
Verify Y = 120 mm
      ↓
Select Isometric View
      ↓
Fit to Model
      ↓
Expand Viewer
      ↓
Restore Viewer
      ↓
Resize browser to narrow viewport
      ↓
Verify complete blade visibility
      ↓
Switch station selection repeatedly
      ↓
Verify STL is not reloaded
      ↓
Verify the canvas/context is reused
      ↓
Enter comparison mode
      ↓
Verify dual station guides
      ↓
Modify a blade parameter
      ↓
Verify stale guides disappear
      ↓
Generate revised CAD
      ↓
Verify correct guides return
```

Add a separate focused browser or camera test for the short-wide synthetic geometry.

Test model visibility using geometric projection or another meaningful quantitative method.

Do not claim the model remains fully visible merely because the Canvas element is visible.

## 21. Browser evidence

Capture screenshots showing:

- Wide viewport with full blade.
- Narrow viewport with full blade.
- Expanded viewer.
- Restored viewer.
- Two selected station guides.
- Stale CAD with guides hidden.
- New successful CAD with guides restored.

Report viewport dimensions and model-framing results.

---

# PART H — CAD NON-REGRESSION

## 22. Preserve existing engineering tests

Run the existing backend test suite.

Re-run the accepted CAD cases:

- Three-section blade.
- Five-section reference blade.
- Eight-section blade.
- NACA thickness override case.
- Imported analytic coordinate airfoil.

Require the established:

- Solid validity.
- Closed-shell status.
- Zero free edges.
- STEP round-trip validity.
- Chord/twist/axis tolerances.
- Physical TE tolerance.
- Contour tolerances.

The patch must not alter generated STEP geometry.

Do not modify the numerical engineering tolerances.

If numerical results change, investigate and report the cause.

---

# PART I — DELIVERABLES

## 23. Documentation

Create:

`docs/PATCH_03B_1_REPORT.md`

Document:

- The original resize regression.
- The implemented camera-fitting policy.
- How manual camera interaction is preserved.
- The guide-array instability root cause.
- The final memoization strategy.
- Resource creation/disposal verification.
- Before/after screenshots.
- Camera projection test results.
- Actual frontend tests.
- Actual Playwright tests.
- Backend/CAD regression results.
- Remaining limitations.

Update README only if the user-visible camera behavior changes.

## 24. Final summary

Provide:

- Branch name.
- Commit SHA.
- Changed files.
- Number of frontend tests passed.
- Number of backend tests passed.
- Playwright results.
- CAD regression status.
- Screenshots.
- Known remaining issues.

Do not fabricate performance improvements.

If claiming fewer guide recreations, provide actual instrumentation or test evidence comparing previous and corrected behavior.

Do not automatically merge into `main`.

---

# PART J — ACCEPTANCE CRITERIA

Classify Patch 03B.1 as STRONG PASS only if:

1. The viewer resizes correctly across wide and narrow aspect ratios.
2. A fitted model remains completely visible after resizing.
3. A short, wide synthetic blade stress test passes.
4. Camera orientation is preserved during expand/restore.
5. Manual orbit/pan/zoom behavior is not unexpectedly reset.
6. Fit to Model remains accurate.
7. Station guides retain exact physical Y coordinates.
8. Unrelated React rerenders do not rebuild guide geometry.
9. Real selection changes update guides correctly.
10. All removed guide geometries and materials are disposed.
11. Station changes do not reload STL or recreate the WebGL context.
12. Stale CAD never displays current-design station guides.
13. Previously validated CAD outputs remain unchanged.
14. Frontend unit tests pass.
15. TypeScript/Vite production build passes.
16. Real Chromium tests pass.
17. Backend engineering regressions pass.
18. `00_research_archive` remains untouched.

Report PASS WITH LIMITATIONS if a required behavior remains unverified.

---

# STRICT SCOPE CONTROL

Do NOT implement:

- Visual Curve Editing.
- Drag-to-edit Chord or Twist.
- Arbitrary 3D surface picking.
- Actual BRep cross-section extraction.
- Additional airfoil databases.
- Multi-blade propellers.
- Hub geometry.
- Aerodynamic performance calculations.
- New CAD backends.
- Major frontend redesign.

This patch is limited to viewer correctness and rendering lifecycle efficiency.

---

# EXECUTION ORDER

**Phase 1 — Camera Regression**

Reproduce and fix the wide-to-narrow framing problem.

**Phase 2 — Guide Memoization**

Stabilize guide references and prevent unnecessary Three.js reconstruction.

**Phase 3 — Lifecycle Verification**

Test geometry/material disposal and STL/renderer reuse.

**Phase 4 — Browser Acceptance**

Verify real CAD viewing, camera operations, comparisons, and stale-result behavior.

**Phase 5 — Regression**

Run all existing frontend/backend tests and document actual results.

---

# FINAL INSTRUCTION

Implement Patch 03B.1 in the existing BladeGen workspace.

Do not stop after planning.

Preserve the validated geometry engine.

Make the smallest maintainable changes that solve the confirmed issues.

**The desired result is a 3D engineering viewer that keeps the blade correctly framed across viewport changes, preserves the engineer's chosen viewing orientation, and updates station guides efficiently without unnecessary WebGL resource reconstruction.**