# SPRINT 02.1 — BladeGen Reliability, Real Build Progress & Expanded 3D Viewer

## Project repository

https://github.com/ahmadqwcv5-droid/bladegen

## Objective

Improve the existing BladeGen Level 1 Alpha application without replacing its validated geometry engine.

The sprint has five objectives:

1. Show real backend-driven progress during blade generation.
2. Expand and improve the Three.js blade viewer.
3. Fix build-job and preview-result identity problems.
4. Strengthen imported BladeSpec validation.
5. Add browser-level and regression testing.

**This is a focused product-reliability and usability sprint, not a new geometry experiment.**

---

# 1. Start from the current project

Inspect the actual current workspace and Git status.

The Sprint 02 implementation has already been committed and merged into `main` on GitHub. Confirm the local state before starting.

Create a development branch, for example:

`sprint/02.1-reliability-progress-viewer`

If uncommitted user changes exist, preserve them and do not overwrite them.

Work in the existing workspace structure:

```text
backend/
frontend/
tests/
examples/
docs/
scripts/
output/runs/
00_research_archive/
```

Do not create a new application.

Do not move, rewrite, or delete `00_research_archive`.

Do not rebuild the geometry engine.

---

# 2. Preserve the validated engineering architecture

The working pipeline is:

```text
BladeSpec v0.2
      ↓
Canonical Curve Resolver
      ↓
Canonical Airfoil Geometry
      ↓
OpenVSP
      ↓
OCP Solidification
      ↓
STEP
      ↓
Independent CAD Validation
```

Preserve:

- SciPy canonical PCHIP.
- Adaptive curve sampling.
- NACA generation.
- Finite trailing-edge policy.
- OpenVSP backend.
- OCP sewing and solidification.
- Adaptive Gauss–Kronrod volume computation.
- Existing validation thresholds.
- Dynamic 3-, 5-, and 8-section support.

Do not introduce a second CAD engine.

Do not change BladeSpec v0.2 unless an unavoidable backend-neutral product requirement is discovered.

---

# PART A — REAL GENERATION PROGRESS

## 3. Current limitation

Inspect:

`backend/api/services/jobs.py`

The existing job model contains:

- job_id
- status
- error
- output directory

and uses a single-worker executor with an isolated CLI subprocess.

The API exposes only broad states:

```text
queued
running
succeeded
failed
```

The frontend therefore cannot show which geometry-generation stage is currently executing.

Implement meaningful progress reporting.

---

# 4. Backend-owned progress state

Extend the job status representation with fields conceptually equivalent to:

```json
{
  "job_id": "...",
  "status": "running",
  "stage": "openvsp",
  "stage_label": "Generating blade surfaces",
  "progress_percent": 18,
  "message": "OpenVSP is constructing the blade geometry",
  "elapsed_seconds": 24.5,
  "error": null
}
```

Preserve compatibility with existing job status fields.

Use the backend as the single source of truth for progress.

The UI must not fabricate progress based on timers.

Progress must correspond to actual pipeline milestones.

---

# 5. Recommended generation milestones

Use the following stage model as an initial guideline:

| Stage | Displayed progress |
|---|---:|
| Queued | 0% |
| BladeSpec validated | 5% |
| Canonical curves and airfoils resolved | 18% |
| OpenVSP blade surfaces exported | 52% |
| OCP valid solid STEP completed | 72% |
| Preview mesh generated | 80% |
| Independent STEP geometry validation completed | 95% |
| Validation artifacts successfully written | 100% |

These percentages are stage-weighted engineering progress indicators, not measured elapsed-time percentages.

For example, while OpenVSP is working, progress may remain at 18%.

Do not slowly increase it to 52% just because time is passing.

The frontend may show an animated activity indicator during a long-running stage, but the numeric percentage must remain truthful.

Never display 100% before the actual build has succeeded.

On failure, retain the last confirmed progress percentage and show the failure stage.

---

# 6. Instrument the real pipeline

Inspect:

- `backend/bladegen/pipeline.py`
- `backend/bladegen/cli.py`
- `backend/api/services/jobs.py`
- `backend/api/schemas/responses.py`
- `backend/api/routes/blades.py`

Add a small, maintainable progress-reporting abstraction.

Recommended approach:

- The isolated build subprocess writes structured progress information into its own job directory.
- The API reads this information while the subprocess runs.
- The frontend continues polling the existing job endpoint.

For example:

`output/runs/{job_id}/progress.json`

Write progress updates atomically, using a temporary file followed by an atomic rename.

This prevents the API from reading partially written JSON.

An alternative streaming JSON-lines implementation is acceptable if it is equally robust and does not block the build process.

Important requirements:

- Progress must be monotonic during a single job.
- Progress must never mix across jobs.
- The CLI must still work independently.
- Progress reporting failures must not silently invalidate a successful CAD build.
- No local filesystem paths may be exposed unnecessarily in API responses.
- Existing build timeout and subprocess isolation must be preserved.

---

# 7. Progress state during failures and timeouts

If OpenVSP fails:

```text
Status: Failed
Stage: OpenVSP geometry
Progress: last confirmed value
Error: actual relevant error
```

If OCP fails to create a closed shell:

```text
Status: Failed
Stage: CAD solidification
```

If independent geometry validation fails:

```text
Status: Failed
Stage: STEP geometry validation
```

If the subprocess times out, show a meaningful timeout message.

Do not mark unsuccessful jobs as completed.

Preserve useful diagnostic logs in the job directory.

---

# 8. Frontend progress component

Create a reusable component, for example:

`frontend/src/components/BuildProgress.tsx`

It should display:

- Current stage.
- Percentage.
- Progress bar.
- Short meaningful status message.
- Actual elapsed time.
- Queued/running/succeeded/failed state.

Suggested UI:

```text
Generating Blade

[████████████░░░░░░░░░░░░] 52%

Stage:
OpenVSP surfaces generated

Elapsed:
00:38

Current operation:
Creating validated solid STEP
```

The visual progress should update from API responses.

Use appropriate accessibility attributes:

- role="progressbar"
- aria-valuemin
- aria-valuemax
- aria-valuenow

For stage activity, use a separate spinner or indeterminate indicator if necessary.

Do not display unsupported estimated time remaining.

---

# PART B — PREVIEW AND JOB RELIABILITY

## 9. Fix confirmed result identity issue

Inspect:

`frontend/src/App.tsx`

Current implementation uses:

- `job`
- `activeJob`
- `artifacts`
- `validationResult`
- `submittedSnapshot`
- `resultSnapshot`

A problem exists when a user successfully generates Blade A and subsequently starts Blade B.

While Blade B runs, the preview may still display Blade A, but its label may use the current job ID for Blade B.

That is misleading.

Fix the state architecture.

Separate:

```text
activeJob
```

from:

```text
displayedResult
```

The displayed result should contain an immutable record such as:

```text
job_id
submitted_bladespec_snapshot
preview_url
step_artifact_url
validation_data
completed_at
```

The currently running job must not change the identity of an existing successful result.

---

# 10. Required result behavior

Scenario:

1. User generates Blade A.
2. Blade A succeeds.
3. Preview A is displayed.
4. User changes chord or twist.
5. UI clearly marks Preview A as stale.
6. User starts generating Blade B.
7. Preview A may remain visible, correctly labeled as A.
8. Blade B finishes successfully.
9. Preview and artifacts switch atomically to B.

If B fails:

- Preview A must remain associated with Blade A.
- Artifacts A must remain identifiable as belonging to A.
- Job B must show its actual failure.
- No stale data may be relabeled as B.

Prevent overlapping asynchronous responses from older jobs from overwriting newer results.

Prevent accidental double submission while a build request is pending.

Test these scenarios explicitly.

---

# PART C — LARGER 3D VIEWER

## 11. Improve default page layout

Inspect:

- `frontend/src/App.tsx`
- `frontend/src/styles.css`
- `frontend/src/sprint02.css`

The current layout uses approximately:

```text
Parameters: 67%
Viewer:     33%
```

with a viewer height of about 420 px.

This makes inspecting the blade difficult.

Change the default desktop layout toward:

```text
Parameters: 55%
Viewer:     45%
```

Use a responsive layout appropriate for engineering software.

Make the default viewer significantly taller, approximately:

`height: clamp(480px, 65vh, 850px)`

Adjust for smaller screens rather than allowing overflow.

The user must be able to inspect the blade comfortably without immediately entering fullscreen.

---

# 12. Expanded viewer mode

Add a visible button:

**Expand Viewer**

When clicked, open a large viewer occupying most of the browser window.

Acceptable implementations:

- Accessible modal-style expanded viewer.
- Fullscreen API with a reliable non-fullscreen fallback.

Required behavior:

- Expand viewer.
- Restore normal layout.
- Close using Escape.
- Preserve the same loaded CAD preview.
- Preserve camera orientation where practical.
- Keep orbit, pan, and zoom functional.
- Avoid unnecessary STL reloads and GPU resource duplication.
- Work correctly on desktop and smaller screens.

Do not launch OpenVSP's own graphical application.

Keep the existing Three.js viewer.

---

# 13. Camera and resizing improvements

Inspect:

`frontend/src/components/BladeViewer.tsx`

The existing viewer uses a fixed 420 px rendering height and a window resize listener.

Implement more reliable container-based resizing.

Use `ResizeObserver` or an equivalent lifecycle-safe approach.

When the viewer container changes size:

- Update renderer dimensions.
- Update camera aspect ratio.
- Update projection matrix.
- Preserve correct geometry proportions.
- Avoid stretching the model.

Keep:

- OrbitControls.
- Fit to Model.
- Visible coordinate axes.
- STL geometry loaded from the final validated OCP solid.

Add useful controls if practical:

- Isometric View.
- Front View.
- Side View.
- Reset Camera.

Do not make complex model selection or CAD feature editing part of this sprint.

---

# 14. Three.js lifecycle safety

Review how asynchronous STL loading interacts with component cleanup.

Ensure:

- A late response from a previous STL request cannot replace a newer model.
- Disposed components do not modify the active scene.
- Old geometries and materials are released.
- Render loops are stopped when no longer needed.
- Event listeners and resize observers are removed.
- Expanding/collapsing the viewer does not leak WebGL resources.

Provide explicit loading and error feedback.

The viewer must not silently become blank if STL loading fails.

---

# PART D — INPUT VALIDATION RELIABILITY

## 15. Strengthen JSON import

Inspect:

`frontend/src/editor/bladespecEditor.ts`

The existing `parseBladeSpec()` performs JSON parsing and only minimal structural checking.

Do not trust TypeScript type assertions as runtime validation.

Implement complete import-time validation using the current backend-neutral BladeSpec contract.

Recommended flow:

```text
User selects JSON
       ↓
Parse JSON
       ↓
Perform basic structural checks
       ↓
POST /api/validate
       ↓
If valid:
    load into editor

If invalid:
    preserve existing project
    display meaningful error
```

The imported file must not become the active editor state until validation succeeds.

A failed import must not destroy a valid currently loaded project.

Preserve coordinate-based airfoils and every distribution without data loss.

Do not add OpenVSP fields to the user-facing JSON.

---

# 16. Improve validation error presentation

The application should clearly distinguish:

- Input validation error.
- Build execution failure.
- STEP topology failure.
- Independent geometry-validation failure.
- Preview loading failure.

Do not display a generic success message when only BladeSpec input validation passed.

Provide useful field-level errors when possible.

Keep existing backend Pydantic validation as authoritative for the input contract.

---

# PART E — COMPLETE CAD VALIDATION GATES

## 17. Strengthen wire-level checks

Inspect:

- `backend/bladegen/validation/measure_sections.py`
- `backend/bladegen/pipeline.py`

The existing measurement records include:

- resulting_wires
- wire_valid
- wire_closed

Ensure required section checks include:

```text
resulting_wires == 1
wire_valid == true
wire_closed == true
```

The required validation gate must fail appropriately when a measured section is invalid.

Do not replace the existing whole-solid BRep checks.

Both remain useful:

```text
CAD solid validity
+
Independent section wire validity
```

Preserve the current geometric tolerances.

---

# PART F — TESTING

## 18. Backend progress tests

Add tests for:

- Queue starts at 0%.
- Progress advances only when confirmed stages complete.
- Progress is monotonic.
- Progress never exceeds 100%.
- Success reaches 100%.
- Failure preserves last confirmed stage.
- Timeout reports failure.
- Atomic progress-file reading.
- Two jobs never share progress information.
- Existing subprocess isolation remains functional.

Test the job status API response fields.

---

# 19. Frontend reliability tests

Extend the existing Vitest / React Testing Library tests.

At minimum cover:

1. Progress display during queue and running stages.
2. Success at 100%.
3. Failure at the correct stage.
4. Blade A preview remains associated with Job A while Job B builds.
5. Failed Job B does not relabel Preview A.
6. Completed Job B replaces Preview A correctly.
7. Editing inputs marks the last successful preview stale.
8. Invalid imported JSON is rejected without replacing the current project.
9. Valid imported JSON preserves all BladeSpec fields.
10. Duplicate Generate clicks do not create accidental duplicate jobs.

Do not remove existing Sprint 02 tests.

---

# 20. Real-browser acceptance

Attempt to install and configure Playwright in the development environment, following the project's existing dependency conventions.

Do not assume browser automation is unavailable merely because it was absent during Sprint 02.

Run a real browser scenario:

```text
Open BladeGen
      ↓
Load example
      ↓
Edit a parameter
      ↓
Generate blade
      ↓
Observe progress stages
      ↓
Wait for successful completion
      ↓
Load 3D preview
      ↓
Expand viewer
      ↓
Orbit / zoom / fit
      ↓
Restore normal viewer
      ↓
Download STEP
      ↓
Edit inputs
      ↓
Verify stale-result warning
```

The browser test should use a real local backend whenever feasible.

Use a lightweight mocked API scenario separately to exercise failure and job-race conditions.

If Playwright cannot be installed or executed, document the exact environment blocker and provide a reproducible manual checklist.

Do not claim browser acceptance passed without executing it.

---

# 21. Engineering regression tests

Re-run existing engineering tests, including:

- The original five-section baseline.
- Three-section blade with root 0.25.
- Eight-section blade with root 0.18.
- NACA 0008 thickness override.
- Valid STEP solidification.
- Adaptive volume integration.
- STEP round-trip.
- Independent chord/twist/TE measurements.

Do not loosen validated tolerances.

Progress instrumentation must not alter generated blade geometry.

Where possible compare baseline numerical results before and after Sprint 02.1.

---

# PART G — OUTPUTS

## 22. Documentation

Create:

`docs/SPRINT_02_1_REPORT.md`

Document:

- Implemented progress stages.
- Exact stage-to-percentage mapping.
- Backend progress transport mechanism.
- Failure and timeout behavior.
- Preview/job identity fix.
- Expanded viewer implementation.
- Imported JSON validation changes.
- CAD validation changes.
- Actual executed tests.
- Known remaining limitations.

Update the root README with user instructions for progress tracking and expanded viewing.

---

# 23. Acceptance criteria

Sprint 02.1 is a STRONG PASS only when:

1. Progress comes from real backend stage transitions.
2. Progress is visible while the CAD subprocess runs.
3. Percentage never advances falsely to completion.
4. Build failures are correctly attributed to the failing stage.
5. Old previews cannot be mislabeled with new job IDs.
6. Invalid imported BladeSpec files cannot corrupt the editor state.
7. Viewer expansion and collapse work correctly.
8. Resizing does not distort the CAD preview.
9. Three.js resources are cleaned up correctly.
10. Section wire validity is part of the required CAD validation gate.
11. Existing geometry tests remain green.
12. Frontend production build succeeds.
13. Frontend unit/component tests pass.
14. Real-browser behavior is verified, or its untested status is explicitly reflected in the final classification.

If a P0 correctness feature is incomplete, classify accordingly rather than forcing a STRONG PASS.

---

# 24. Final delivery

Provide:

- Branch name and commit SHA.
- Summary of changed files.
- Screenshot of the normal-sized viewer.
- Screenshot of the expanded viewer.
- Screenshot of progress during a real build.
- Screenshot of a successful build.
- Screenshot or test evidence of a failed job.
- Backend test results.
- Frontend test results.
- Browser test results.
- Real CAD regression results.
- Remaining limitations.
- Exact commands to run the application.

Do not fabricate percentages, screenshots, tests, or results.

Do not automatically merge into `main` unless explicitly requested.

---

# FINAL INSTRUCTION

Implement Sprint 02.1 in the existing BladeGen workspace.

Prioritize the following execution order:

1. Backend progress reporting.
2. Frontend progress UI.
3. Active-job versus displayed-result separation.
4. Expanded/responsive 3D viewer.
5. JSON import validation.
6. Wire-level validation gate.
7. Backend, frontend, browser, and CAD regression testing.

Do not stop after planning.

Do not build new aerodynamic features.

Do not replace the validated geometry engine.

**The goal is a dependable engineering application that clearly communicates its progress, correctly identifies the CAD being displayed, and provides a comfortable large 3D viewing experience.**