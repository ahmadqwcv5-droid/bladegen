# PATCH 02.1.1 — BladeGen Engineering UI Corrections



## Mission

Implement a focused corrective patch on the existing BladeGen Level 1 Alpha application.

The project has successfully completed Sprint 02.1, including real backend progress reporting, a larger expandable Three.js viewer, independent CAD validation, and browser-level testing.

A source-code and screenshot review identified three specific issues requiring correction:

1. Incorrect handling of nullable `thickness_override_ratio` values between FastAPI/Pydantic and React.
2. A progress-reporting race that may expose 100% while the build is still running.
3. An inadequate default 3D camera angle that makes the blade appear too narrow even in expanded mode.

Additionally, improve numeric-table readability where practical.

**This is a small reliability and usability patch. Do not rebuild or redesign BladeGen.**

---

## 1. Repository preparation

Inspect the current Git working tree.

The latest reviewed Sprint 02.1 version is on `main`, at merge commit:

`0d98d9e5c382048648e70e74804fa267e59b02e7`

Check whether newer commits exist and inspect the current implementation before modifying anything.

Create a patch branch:

`sprint/02.1.1-engineering-ui-fixes`

Preserve uncommitted changes if present.

Do not modify:

- `00_research_archive`
- BladeSpec engineering conventions
- Canonical curve mathematics
- NACA geometry generation
- OpenVSP geometry adapter
- OCP solidification algorithms
- Existing geometry tolerances

Do not introduce another geometry backend.

---

# PART A — FIX THICKNESS OVERRIDE NULL SEMANTICS

## 2. Confirmed problem

Inspect:

- `frontend/src/types/bladespec.ts`
- `frontend/src/App.tsx`
- `frontend/src/editor/bladespecEditor.ts`
- `backend/bladegen/models/blade_spec.py`
- `backend/api/routes/blades.py`

The backend Pydantic model defines:

```python
thickness_override_ratio: float | None = None
```

FastAPI serializes an absent override as:

```json
{
  "thickness_override_ratio": null
}
```

However, parts of the React application test:

```typescript
section.thickness_override_ratio !== undefined
```

This incorrectly considers `null` an active override.

It affects:

- The Explicit Override checkbox.
- NACA thickness coordination.
- Input validation logic.
- Potentially the engineering meaning of edited specifications.

### Required correction

Use consistent nullable semantics throughout the frontend.

Update the TypeScript type appropriately:

```typescript
thickness_override_ratio?: number | null
```

Define a shared, clearly named helper for determining whether an explicit numeric override exists.

For example:

```typescript
function hasThicknessOverride(section: AirfoilSection): boolean {
  return section.thickness_override_ratio != null
}
```

Audit every relevant check.

Do not simply fix the checkbox while leaving the editing and validation functions inconsistent.

### Expected behavior

For a section containing:

```json
{
  "airfoil": {
    "type": "naca4",
    "code": "0010"
  },
  "thickness_override_ratio": null
}
```

the application must:

- Show Explicit Override as disabled.
- Show effective thickness ratio 0.10.
- Treat the NACA profile's nominal thickness as authoritative.
- Permit automatic thickness-curve coordination when the NACA code changes.

If the user changes NACA `0010` to `0008`, without an explicit override:

- Effective thickness must become 0.08.
- The corresponding thickness distribution must be coordinated.
- Backend validation must pass.
- No unrelated user control values should change silently.

If the user explicitly enables an override of 0.10 for NACA 0008:

- The checkbox must be enabled.
- Effective t/c must be 0.10.
- The thickness distribution must be consistent with the override.
- Disabling the override must restore nominal NACA thickness semantics.

Preserve support for both omitted and explicit `null` override fields in existing neutral JSON files.

Do not alter the physical trailing-edge thickness when modifying nominal or effective airfoil thickness.

---

## 3. Add tests for real API serialization

Do not test only JSON imported directly from repository examples.

Add tests that use the actual JSON shape returned by FastAPI.

Required test cases:

1. Pydantic returns `thickness_override_ratio: null` for absent overrides.
2. React displays an unchecked override for null.
3. React displays an unchecked override for an omitted property.
4. React displays a checked override for a valid numeric override.
5. Changing NACA 0010 to 0008 updates effective t/c from 0.10 to 0.08.
6. The submitted JSON passes `/api/validate`.
7. Enabling and disabling an override preserves expected engineering behavior.
8. JSON export and re-import do not create unintended overrides.

Do not weaken existing thickness consistency checks.

---

# PART B — CORRECT 100% BUILD PROGRESS SEMANTICS

## 4. Current issue

Inspect:

- `backend/bladegen/progress.py`
- `backend/bladegen/pipeline.py`
- `backend/api/services/jobs.py`
- `frontend/src/components/BuildProgress.tsx`

The pipeline currently writes a 100% completion milestone before the CLI subprocess has fully exited.

The JobManager independently marks the build as succeeded after checking the process return code and required artifacts.

This creates a possible state where the API returns:

```json
{
  "status": "running",
  "progress_percent": 100
}
```

even though final job success is not yet confirmed.

### Required behavior

Enforce this invariant:

**100% is displayed only when the JobManager has confirmed `status == "succeeded"`.**

Keep the existing real engineering milestones:

- 0% queued
- 5% validation completed
- 18% canonical resolution completed
- 52% OpenVSP completed
- 72% STEP solidification completed
- 80% preview completed
- 95% independent geometry validation completed

After required artifacts are written, the pipeline may record that its work is ready, but public job progress must remain below 100% until the manager confirms success.

A suitable approach:

- The subprocess reports up to 95%.
- The JobManager waits for a zero exit code.
- Required artifacts are verified.
- The JobManager atomically marks the job `succeeded` and sets progress to 100%.

Do not introduce timer-based progress increments.

Preserve:

- Isolated CAD subprocess execution.
- Atomic progress updates.
- Monotonic progress.
- Timeouts.
- Job-specific progress files.
- Existing API response compatibility.

### Failure requirements

If the subprocess fails after writing its artifacts but before confirmed success:

- Job status must be `failed`.
- Progress must remain below 100%.
- The UI must display the actual failure.
- The last confirmed engineering stage must remain identifiable.

A missing required artifact must also prevent successful completion.

### Tests

Add tests asserting:

- A running job never returns 100%.
- A succeeded job returns 100%.
- A failed job never returns 100%.
- A nonzero subprocess exit after the last pipeline milestone cannot produce a successful status.
- Missing required artifacts prevent 100%.
- Existing progress tests remain green.

---

# PART C — IMPROVE THE DEFAULT 3D BLADE VIEW

## 5. Current limitation

Inspect:

`frontend/src/components/BladeViewer.tsx`

and:

`frontend/src/sprint02_1.css`

The current viewer works and supports expansion, but the latest screenshots show the blade appearing unusually narrow.

The larger viewer itself is not the problem.

The default camera looks at the blade from a direction that does not adequately reveal its broad surface.

### Required correction

Introduce a meaningful engineering camera system.

The viewer must offer:

- Blade Face View
- Blade Edge View
- Isometric View
- Fit to Model

Preserve existing Front and Side controls where useful.

### Preferred default

**Blade Face View should be the default camera orientation after the STL loads.**

The view should reveal:

- The approximate planform of the blade.
- Chord variation along the radius.
- Blade sweep/skew.
- The broad pressure/suction surface rather than primarily its edge.

Do not hard-code a single camera vector optimized only for the 400 mm reference blade if that produces poor results on other designs.

Use the known blade coordinate conventions and/or mesh geometry to select an appropriate broadside direction.

A deterministic method based on projected silhouette or surface orientation is acceptable.

Keep the blade radial axis visually vertical when appropriate.

The Edge View should intentionally show the blade from an approximately perpendicular direction, making twist and section geometry easier to inspect.

---

## 6. Fit-to-model improvements

Update camera fitting to account for both vertical and horizontal field of view.

The current viewer uses a perspective camera, so the correct distance must consider the actual canvas aspect ratio.

Required behavior:

- The entire blade remains visible.
- The model is not unnecessarily small.
- No clipping occurs at the root or tip.
- The model is not distorted when resizing.
- A narrow viewer and an expanded viewer both frame the geometry correctly.

Preserve:

- ResizeObserver.
- OrbitControls.
- Pan and zoom.
- Expand Viewer.
- Escape to close.
- Single WebGL context when expanding.
- Proper disposal of resources.
- Late STL response protection.

Do not regenerate the STL merely to improve its camera view.

The STL remains a preview derived from the final validated OCP solid.

---

## 7. Viewer acceptance testing

Test the camera on at least:

1. The validated five-section reference blade.
2. The three-section blade.
3. The eight-section blade.

For each:

- Load the actual generated preview.
- Verify that Blade Face View shows the broad surface.
- Verify Blade Edge View is meaningfully different.
- Verify Isometric and Fit to Model.
- Expand and restore the viewer.
- Resize the browser.
- Confirm no clipping or disproportionate stretching.

Use Playwright for browser behavior.

Capture normal and expanded screenshots.

Screenshots are visual evidence, not a replacement for functional assertions.

---

# PART D — SMALL NUMERIC TABLE IMPROVEMENTS

## 8. Improve distribution-table readability

In the current screenshots, some r/R input fields are too narrow to show values comfortably.

Inspect:

- `frontend/src/components/DistributionTable.tsx`
- `frontend/src/styles.css`
- `frontend/src/sprint02.css`
- `frontend/src/sprint02_1.css`

Make a focused CSS/layout adjustment.

Requirements:

- Numeric values such as `0.35`, `0.625`, and `0.9995` must remain readable.
- Tables should not clip important engineering numbers.
- Inputs should have sensible minimum widths.
- Narrow screens should support appropriate local scrolling rather than hiding digits.
- Layout changes must not reduce the improved 3D viewer area unnecessarily.

Do not redesign the entire interface.

Do not introduce a graphical curve editor in this patch.

---

# PART E — REGRESSION AND VERIFICATION

## 9. Frontend verification

Run existing Vitest tests.

Add the new nullable-thickness and camera-control tests.

Run the production TypeScript/Vite build.

Run Playwright against the actual local application.

Verify:

- Load Example receives nullable fields correctly.
- NACA changes coordinate thickness correctly.
- Real generation progress works.
- Viewer defaults to a broad blade view.
- Expand/restore remains functional.
- Previous successful result identity remains correct.

---

## 10. Backend verification

Run existing backend tests.

Preserve the real OpenVSP/OCP acceptance cases:

- Three-section blade.
- Five-section reference.
- Eight-section blade.
- NACA 0008 effective thickness override.

No numerical geometry regression is acceptable.

Compare:

- Valid solid status.
- Free edges.
- Adaptive volume.
- Chord/twist/axis errors.
- Physical trailing-edge thickness.
- STEP round-trip validity.

Do not change established CAD tolerances.

If this patch does not change the engineering pipeline, expected CAD output should remain numerically consistent with the previous accepted builds.

---

# PART F — FINAL DELIVERABLES

## 11. Documentation

Create:

`docs/PATCH_02_1_1_REPORT.md`

Include:

- Root cause of the null/undefined problem.
- Exact files changed.
- How thickness override semantics were corrected.
- How public 100% progress is now gated.
- How the default broadside camera is selected.
- Viewer screenshots.
- Before/after numeric-table screenshots if useful.
- Actual tests executed.
- Failed or skipped tests.
- Any remaining limitations.

Update README only where functionality or user instructions changed.

Do not rewrite unrelated documentation.

---

## 12. Acceptance criteria

Classify the patch as STRONG PASS only when:

1. Missing and null thickness overrides behave identically.
2. Explicit numeric overrides remain fully functional.
3. Changing NACA automatically coordinates nominal thickness when no override exists.
4. Exported and imported BladeSpecs preserve engineering meaning.
5. Running jobs cannot publicly reach 100%.
6. Only confirmed successful jobs reach 100%.
7. Blade Face View is a useful default for all three acceptance blades.
8. Expanded viewer remains reliable.
9. Camera framing adapts correctly to changes in aspect ratio.
10. Numeric fields are readable without clipping.
11. Existing geometry tolerances remain unchanged.
12. All backend and frontend regression tests pass.
13. Browser tests actually execute and pass.
14. No historical research files are modified.

If any criterion is not verified, report PASS WITH LIMITATIONS or FAIL as appropriate.

---

## 13. Scope restrictions

Do NOT implement:

- Airfoil Library.
- Hub geometry.
- Multiple blades.
- Aerodynamic analysis.
- Performance optimization.
- New backend architecture.
- Database.
- New CAD engine.
- Major frontend redesign.

These belong to later sprints.

Do not merge automatically into main unless explicitly requested.

---

# FINAL INSTRUCTION

Implement this as a focused corrective patch.

**Priority order:**

1. Fix nullable Thickness Override semantics.
2. Correct 100% progress completion gating.
3. Improve default blade camera and Face/Edge views.
4. Improve table readability.
5. Run all required tests and document results.

The goal is to preserve BladeGen's validated engineering capabilities while making the user interface accurately represent engineering inputs, build status, and the generated blade geometry.

Do not stop after planning. Implement, test, and report actual results.