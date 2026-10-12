# SPRINT 03C — BladeGen Visual Curve Editing & Engineering Undo/Redo



## Mission

Extend the existing BladeGen Level 1 Alpha application with accurate, interactive editing of spanwise engineering distributions.

The engineer must be able to drag an existing control point directly on a distribution chart, change its engineering value, see immediate visual feedback, commit a valid BladeSpec update, and undo or redo that edit.

Supported distributions:

- Chord
- Twist
- Rake
- Skew
- Thickness ratio

The existing numeric tables must remain fully functional.

**The central engineering requirement is that visual editing must never introduce a second, conflicting definition of blade geometry.**

BladeSpec remains the authoritative design document, and the Python canonical evaluator remains the authority for Linear and SciPy PCHIP interpolation.

This is a product-development sprint, not a new geometry research spike.

---

# PART A — PREPARATION

## 1. Inspect the current repository

Review the current Git state and preserve all uncommitted work.

The last reviewed main branch commit was:

`96f7b408cdbd181f668f82adc7dd2ad36fd2e79b`

Verify the actual current HEAD before editing.

Create a branch:

`sprint/03c-visual-curve-editing`

Do not automatically merge into `main`.

Do not modify `00_research_archive`.

## 2. Review the existing components

At minimum inspect:

- `frontend/src/App.tsx`
- `frontend/src/components/DistributionChart.tsx`
- `frontend/src/components/DistributionTable.tsx`
- `frontend/src/components/NumericInput.tsx`
- `frontend/src/editor/bladespecEditor.ts`
- `frontend/src/types/bladespec.ts`
- `frontend/src/sprint03a.css`
- `frontend/src/sprint03b.css`
- `backend/api/routes/airfoils.py`
- `backend/api/routes/blades.py`
- `backend/bladegen/curves/canonical.py`
- `backend/bladegen/curves/resolver.py`
- `backend/bladegen/models/blade_spec.py`

Important existing behavior:

`DistributionChart.tsx` displays canonical backend samples and user-control markers.

`DistributionTable.tsx` edits control points numerically using existing editor helpers.

`App.tsx` manages BladeSpec, asynchronous canonical previews, build snapshots, and stale-CAD protection.

`POST /api/design-preview` returns backend-evaluated curve samples and control points, already converted to engineering display units.

Reuse these capabilities.

Do not introduce a new charting framework unless a genuine limitation justifies it.

---

# PART B — ENGINEERING CONTRACT

## 3. Preserve the existing design representation

The product uses:

```text
BladeSpec v0.2
    ↓
Canonical Python Linear / SciPy PCHIP
    ↓
Resolved BladeSpec
    ↓
OpenVSP
    ↓
OCP
    ↓
Validated STEP
```

Do not modify this architecture.

Do not change:

- BladeSpec schema.
- OpenVSP adapter.
- OCP solidification.
- NACA generation.
- Imported airfoil definitions.
- Physical trailing-edge policy.
- CAD validation tolerances.

No new CAD geometry generation is required for ordinary curve editing.

## 4. Engineering unit conversions

The chart displays physical engineering units while BladeSpec stores some normalized values.

Use:

```text
R = diameter_mm / 2
```

Required conversion rules:

| Curve | Displayed value | Stored BladeSpec value |
|---|---|---|
| Chord | mm | chord_over_R = chord_mm / R |
| Twist | degrees | twist_deg |
| Rake | mm | rake_over_R = rake_mm / R |
| Skew | mm | skew_over_R = skew_mm / R |
| Thickness | % t/c | thickness_ratio = percent / 100 |

Implement one reusable conversion layer.

It must work in both directions.

Do not embed independent conversion formulas in several React components.

Never round the stored engineering value merely because the UI displays fewer decimal places.

Display formatting and stored precision are separate concerns.

## 5. Control-point position policy

For Sprint 03C, dragging changes **only the vertical engineering value** of an existing control point.

It must NOT change:

- `r_over_R`.
- Number of points.
- Point ordering.
- Interpolation method.
- Airfoil station locations.
- Any unrelated distribution.

The horizontal position is locked.

For example:

```text
Before:

r/R = 0.50
Chord = 60.0 mm

After dragging vertically:

r/R = 0.50
Chord = 64.0 mm
```

For D = 400 mm, the resulting stored value must be:

```json
{
  "r_over_R": 0.5,
  "chord_over_R": 0.32
}
```

Existing table-based editing of radial positions remains available.

Do not implement horizontal drag-to-edit in this sprint.

---

# PART C — INTERACTIVE CONTROL MARKERS

## 6. Extend DistributionChart

Modify:

`frontend/src/components/DistributionChart.tsx`

Add interactive control-point markers.

Required behavior:

- Hover highlights a control point.
- Pointer-down selects it.
- Vertical dragging changes a provisional value.
- A floating readout shows r/R and the proposed engineering value.
- Pointer-up attempts to commit the edit.
- Escape cancels the edit.
- Pointer cancellation rolls back safely.

Make the interactive hit target larger than the visible marker.

Maintain the current visual distinction between user controls and interpolated curve samples.

Do not make every sampled curve point draggable.

Only actual BladeSpec control points are editable.

## 7. Use Pointer Events

Use the appropriate browser Pointer Events API.

Support:

- Mouse.
- Touch.
- Pen input.

Use pointer capture where appropriate.

A drag must remain controlled if the pointer temporarily leaves the circle or SVG.

Clean up capture and temporary state after:

- Successful release.
- Escape.
- Pointer cancellation.
- Switching distribution tabs.
- Changing the active BladeSpec.
- Component unmount.

Do not allow an abandoned drag to leave a partially modified engineering value.

## 8. Accurate screen-to-engineering conversion

The existing chart uses:

```typescript
CHART_WIDTH = 640
CHART_HEIGHT = 260
CHART_MARGIN = {
  left: 58,
  right: 18,
  top: 18,
  bottom: 42
}
```

Sprint 03A.1 already corrected horizontal hover-coordinate conversion.

Extend the same approach to vertical dragging.

Use the actual SVG coordinate transformation, including:

- viewBox.
- Responsive dimensions.
- preserveAspectRatio letterboxing.
- CSS scaling.
- Plot margins.
- Reversed screen Y direction.

The proposed engineering value must be derived from the plotted vertical scale.

Do not normalize `clientY` against the entire browser rectangle while ignoring SVG margins.

Provide pure, independently testable conversion helpers.

## 9. Stable drag-axis behavior

At pointer-down, capture the current plotted Y-axis range.

Keep that range stable throughout the drag.

Otherwise, dynamically changing the chart's minimum and maximum values may cause the dragged marker to jump or oscillate.

The committed chart can auto-scale again after the backend returns its new canonical samples.

If the user reaches the visible axis boundary, provide a clear limit/readout.

Do not silently invent an arbitrary engineering maximum.

Numeric table editing must remain available for values outside the current visual range.

A future axis zoom feature may be implemented separately.

---

# PART D — CANONICAL PREVIEW INTEGRITY

## 10. Backend remains authoritative

Do NOT implement a new frontend PCHIP calculation for drawing the edited curve.

The existing Python backend already owns:

- Linear interpolation.
- SciPy PCHIP.
- Curve evaluation.
- Canonical curve resolution.

Continue using:

`POST /api/design-preview`

to obtain authoritative plotted samples.

The existing frontend contains `evaluateDistribution()` for control-point management. Do not treat its JavaScript implementation as the authoritative source for newly drawn PCHIP curves.

## 11. Two-phase editing model

Implement an explicit distinction between:

**Draft edit**

The user is currently moving a control point.

**Committed edit**

The proposed value has passed validation and has been added to the BladeSpec editing history.

During an active drag:

- Move the control marker immediately.
- Show the provisional numerical value.
- Reflect the provisional value in the corresponding table cell or a clearly associated draft readout.
- Keep the underlying committed BladeSpec unchanged until commit.
- Display the existing canonical curve as the last confirmed curve, clearly distinguished from the provisional point.
- Do not represent an unvalidated approximation as a final PCHIP result.

On pointer release:

1. Construct a candidate BladeSpec from the latest committed specification.
2. Update exactly the intended control-point value.
3. Perform inexpensive local engineering checks.
4. Validate the candidate through the existing backend validation contract.
5. Commit the candidate only if valid.
6. Request the refreshed canonical design preview through the existing revision-aware workflow.
7. Replace the plotted curve with the returned canonical samples.

If validation fails, restore the original committed value and explain why.

Avoid automatic CAD generation.

## 12. Performance policy

Do not submit a backend request on every pointer-move event.

Use local UI state and optionally requestAnimationFrame to keep marker movement responsive.

Prefer:

- Zero backend requests while dragging.
- One authoritative validation operation after release.
- One canonical preview refresh following a successful commit.

If some existing application behavior requires additional requests, document and bound them.

Do not overload the Python resolver with dozens of requests per second.

Do not allow asynchronous responses from older revisions to replace the current chart.

The current debounce, cancellation, and revision-snapshot protections must remain functional.

---

# PART E — ENGINEERING VALIDATION

## 13. General numeric rules

Every committed value must be finite.

Preserve existing schema semantics.

At minimum:

- Chord must remain strictly positive.
- Thickness ratio must remain strictly positive.
- Twist must remain finite.
- Rake may be positive, zero, or negative.
- Skew may be positive, zero, or negative.

Do not introduce arbitrary hard-coded Twist, Rake, or Skew engineering limits without justification.

Do not silently clamp invalid engineering values and commit a different value than the user intended.

Instead, show a validation message and provide a way to correct or cancel the edit.

## 14. Thickness requires special protection

This is a P0 requirement.

The current backend ensures consistency between:

- NACA nominal thickness.
- Explicit NACA thickness override.
- Imported coordinate profile natural t/c.
- Thickness distribution.

A general visual editor must not bypass these rules.

Implement the following behavior:

**NACA station with no explicit thickness override**

If a thickness control point coincides with that station, it must not be changed independently in a way that contradicts nominal NACA thickness.

Show a locked marker or an explicit explanation directing the engineer to enable the existing Thickness Override control.

**NACA station with an explicit override**

If the corresponding thickness control is edited, update its explicit override consistently as part of the same atomic engineering transaction.

Do not leave the curve and override with contradictory values.

**Imported coordinate airfoil station**

The active thickness curve must remain consistent with the coordinate profile's natural geometric t/c.

Do not silently scale or rewrite imported coordinates.

Do not allow a drag to create a contradictory thickness definition.

**Thickness control points that do not coincide with airfoil stations**

Allow editing when the resulting complete BladeSpec remains valid.

Because interpolation may affect thickness at nearby airfoil stations, validate the entire candidate rather than only checking the edited control point.

Never silently add, remove, or move thickness control points to force a drag to pass.

## 15. Clear user feedback

If an edit cannot be committed, show a useful message.

Examples:

```text
Cannot change this thickness control.

NACA 4412 requires t/c = 0.12 unless
an explicit thickness override is enabled.
```

```text
This edit changes the interpolated thickness
at an imported airfoil station.

The imported profile must retain its natural t/c.
```

Do not return only a generic "Invalid BladeSpec" message when a more specific engineering explanation is available.

---

# PART F — SYNCHRONIZED NUMERIC TABLES

## 16. Keep the table and chart synchronized

The numeric table remains the authoritative, accessible editing alternative.

Required behavior:

- Chart marker reflects the current committed table value.
- During drag, the table or associated draft display reflects the provisional value.
- After successful commit, the table displays the new stored value.
- After cancellation, it displays the unchanged original value.
- Numeric table edits trigger canonical chart refresh.
- Changing interpolation from Linear to PCHIP refreshes the plotted curve without changing control values.

No independent state copies may remain permanently out of sync.

## 17. Preserve control-point identity

The application already supports dynamic control-point insertion and deletion.

Do not identify an active drag exclusively by a fragile array index without accounting for structural changes.

During a drag:

- Prevent conflicting structural edits, or cancel safely before processing them.
- Never apply a delayed drag completion to a different point after insertion or deletion.
- Do not accidentally move another point when switching between distribution tabs.

Use a stable transaction identity, and local point IDs if necessary.

Frontend-only identifiers must not be included in the neutral BladeSpec export.

---

# PART G — UNDO / REDO

## 18. Add engineering edit history

Implement a bounded undo/redo system for distribution editing.

At minimum, include:

- Successful chart drags.
- Numeric changes to distribution control values.
- Distribution point insertion/removal.
- Distribution interpolation changes.

All changes to the same distribution must use a consistent editing-history mechanism.

A complete drag must produce **one history transaction**, regardless of how many pointer-move events occurred.

Do not create one history entry per mouse pixel.

An invalid or canceled drag creates no history entry.

## 19. History semantics

Support:

- Undo.
- Redo.
- Disabled buttons when unavailable.
- Clear redo history after a new committed edit.
- Deterministic bounded history, for example 50 transactions.

When a new project is loaded, imported, or reset, establish a new history baseline.

Do not allow undo to unexpectedly restore a different previously loaded project.

If unrelated Global Settings or Airfoil Station edits are outside this sprint's undo scope, define exactly how they invalidate or interact with the curve-history stack. Never allow undoing a curve edit to overwrite an unrelated, newer engineering change.

Prefer atomic snapshots or reversible transactions that preserve full BladeSpec consistency.

## 20. Keyboard shortcuts

Support conventional desktop shortcuts:

- Ctrl/Cmd + Z — Undo.
- Ctrl/Cmd + Shift + Z — Redo.
- Ctrl + Y — Redo where appropriate.
- Escape — Cancel active drag.

Do not hijack native undo behavior when the engineer is typing inside a text or numeric input.

Ensure keyboard shortcuts do not interfere with existing dialogs and imported file workflows.

## 21. Atomic thickness history

When a thickness edit updates both:

- `thickness_distribution`, and
- an explicit `thickness_override_ratio`,

Undo must restore both values together.

Redo must reapply both together.

Never allow undo to restore only half of a consistent engineering transaction.

---

# PART H — KEYBOARD ACCESSIBILITY

## 22. Point editing without a mouse

Control points must remain operable without pointer dragging.

Provide keyboard focus on editable controls.

Support arrow-key value adjustments with documented increments.

Suggested initial engineering increments:

| Curve | Normal step |
|---|---|
| Chord | 0.5 mm |
| Twist | 0.25° |
| Rake | 0.5 mm |
| Skew | 0.5 mm |
| Thickness | 0.1 percentage point |

Shift may multiply the step by ten.

These are input convenience steps, not numerical precision limits.

Allow exact values through the numeric table.

Provide:

- Accessible control labels.
- Current r/R.
- Current engineering value and unit.
- Visible focus state.
- Appropriate disabled/locked states.
- Screen-reader feedback on successful or rejected edits.

Keyboard editing must follow the same validation and history rules as pointer editing.

---

# PART I — USER EXPERIENCE

## 23. Editing-state indicators

Make the interaction clear.

Suggested states:

- Ready to edit.
- Dragging draft value.
- Validating proposed value.
- Edit accepted.
- Edit rejected.
- Canonical preview updating.

Distinguish draft markers visually from committed control markers.

Do not allow the engineer to confuse the old canonical line with a newly validated curve.

## 24. Prevent accidental design changes

Clicking on a control point without meaningful movement should select it, not silently change its engineering value.

Use a small movement threshold where appropriate.

If the user changes tabs during a drag, cancel or explicitly finalize the edit according to one documented policy.

Prefer cancellation rather than surprise commits.

If backend validation is still pending, guard against conflicting submissions and older asynchronous results.

## 25. Maintain the existing layout

Preserve:

- Airfoil Library.
- 2D Airfoil Inspector.
- Airfoil Comparison.
- Station-selection workflow.
- 3D Viewer and station guides.
- Engineering distribution tables.
- Validation reporting.
- STEP export.

Enhance the existing `DistributionChart` rather than rebuilding the entire UI.

Ensure the chart remains usable in:

- Normal desktop layout.
- Expanded or narrow editor layout.
- 720px viewport.
- Approximately 520px viewport.

Touch dragging should not accidentally scroll the page while a pointer is captured on a control point.

Use scoped touch-action behavior on editable markers instead of disabling scrolling for the whole application.

---

# PART J — CAD AND REVISION SAFETY

## 26. Never build CAD automatically during visual editing

Dragging must not invoke:

- POST /api/build
- OpenVSP
- OCP
- STEP export
- STL generation

Only the existing Generate Blade action may initiate a CAD build.

## 27. Preserve current design versus displayed CAD separation

During an active drag:

- The existing generated CAD remains unchanged.
- Clearly indicate that the user is editing a provisional design value.
- Hide or appropriately disable current-design station guides if the draft could be mistaken for already generated CAD.
- Prevent Generate until the draft has been committed or canceled.

After successful commit:

- The design revision changes.
- Previous CAD becomes stale where appropriate.
- Current-design station guides remain hidden over stale CAD.
- The canonical 2D design preview refreshes.
- The old STEP remains associated with its original job.

After Undo:

- The active design revision must reflect the restored BladeSpec.
- If the restored specification exactly matches the displayed CAD snapshot, the existing stale-CAD mechanism may reactivate matching guides after canonical preview confirmation.

Do not generate a new STEP solely to support undo.

## 28. Preserve existing async safety

The current application already has:

- Canonical preview revisions.
- Request cancellation.
- Build job identity.
- Submitted BladeSpec snapshots.
- Stale CAD detection.

The new drag editor must integrate with these mechanisms.

An old validation response must never overwrite a newer committed edit.

If validation is canceled, superseded, or fails because the backend is unavailable, preserve the last valid committed BladeSpec.

Do not silently commit an unvalidated candidate.

---

# PART K — REQUIRED ENGINEERING TESTS

## 29. Unit conversion tests

Verify both conversion directions.

Examples for D = 400 mm:

```text
R = 200 mm

Chord:
60 mm -> chord_over_R = 0.30
64 mm -> chord_over_R = 0.32

Rake:
4 mm -> rake_over_R = 0.02

Skew:
-8 mm -> skew_over_R = -0.04

Thickness:
12% -> thickness_ratio = 0.12
```

Test a second diameter, such as D = 720 mm.

Verify that changing diameter changes physical displayed lengths correctly without silently changing normalized engineering intent.

## 30. Pointer conversion tests

Test mouse and pointer positions at:

- Chart top boundary.
- Chart bottom boundary.
- Plot midpoint.
- Different viewport aspect ratios.
- SVG letterboxed layout.
- Scrolled document.
- Pointer leaving the visible marker while captured.

Check exact engineering-unit calculations within floating-point tolerance.

## 31. Drag transaction tests

Test:

1. Drag Chord from 60 mm to 64 mm at r/R 0.50.
2. Confirm r/R stays 0.50.
3. Confirm stored chord_over_R becomes 0.32.
4. Confirm other control points remain unchanged.
5. Confirm one history entry is created.
6. Confirm Undo restores 0.30.
7. Confirm Redo restores 0.32.
8. Cancel with Escape.
9. Cancel with pointercancel.
10. Click without moving.
11. Switch distribution tabs during a drag.
12. Delete a control point while a drag is active.
13. Prevent stale asynchronous validation from changing the wrong point.

Test negative Rake/Skew values and positive-only Chord/Thickness requirements.

## 32. Thickness safety tests

Include:

- NACA station without override — contradictory drag rejected or locked.
- NACA station with explicit override — curve and override change atomically.
- Imported coordinate airfoil — natural t/c remains protected.
- Non-coincident thickness control — candidate validated against all station constraints.
- Undo restores all coordinated thickness fields.
- Redo restores all coordinated thickness fields.
- No airfoil coordinates are modified by thickness chart dragging.
- No physical trailing-edge millimeter requirement is changed inadvertently.

Use actual representative BladeSpecs rather than relying only on mock objects that omit thickness constraints.

## 33. Canonical interpolation tests

After a valid edit, compare new plotted samples against direct Python canonical evaluations for:

- Linear.
- SciPy PCHIP.

Use multiple intermediate locations, not only control points.

Verify that the chart uses `design-preview` data for its committed curve.

No frontend-generated replacement PCHIP curve is permitted.

## 34. Frontend integration tests

Extend existing Vitest/React Testing Library coverage.

Test:

- Marker selection.
- Pointer dragging.
- Draft readout.
- Commit and rollback.
- Synchronized table values.
- Interpolation changes.
- Undo/Redo buttons.
- Keyboard shortcuts.
- Disabled or locked thickness controls.
- Canonical preview loading/revision safety.
- Stale-CAD marking.
- No build requests from visual editing.

Do not remove previous Sprint 03B tests.

---

# PART L — REAL BROWSER ACCEPTANCE

## 35. Playwright workflow

Run a real Chromium acceptance test against the application.

Minimum scenario:

```text
Open BladeGen
     ↓
Load five-section example
     ↓
Open Chord distribution chart
     ↓
Select r/R 0.50 control point
     ↓
Drag value from 60 mm to 64 mm
     ↓
Confirm displayed r/R remains 0.50
     ↓
Confirm the numeric table stores 0.32
     ↓
Wait for canonical backend preview
     ↓
Verify chart reflects the new value
     ↓
Undo
     ↓
Verify 0.30 is restored
     ↓
Redo
     ↓
Verify 0.32 returns
     ↓
Switch to Twist chart
     ↓
Change an existing control from 23° to 27°
     ↓
Verify the updated table and canonical chart
     ↓
Attempt an invalid Thickness edit
     ↓
Verify rollback and meaningful error
     ↓
Verify no CAD build has occurred automatically
     ↓
Click Generate Blade explicitly
     ↓
Wait for a validated STEP
     ↓
Verify the resulting CAD measurements
```

For the Chord case, the final CAD should measure approximately 64 mm at r/R 0.50 within the existing final STEP chord tolerance.

The browser test must use actual pointer interactions, not only direct calls to editor functions.

Run at least one normal and one narrow-viewport interaction test.

## 36. Browser assertions

Verify:

- The intended marker is captured.
- The X/r/R coordinate remains fixed.
- The correct point value changes.
- No additional control point is inserted.
- Undo/Redo restores exact stored values.
- PCHIP is refreshed by the backend.
- No `/api/build` request occurs during dragging, undo, or redo.
- Stale CAD guides remain hidden after a changed committed design.
- A final explicit build succeeds.
- No unintended STL reload occurs during chart editing.
- Existing Airfoil comparison and 3D inspection remain usable.

Capture screenshots of:

- Selected control point.
- Active drag with draft engineering value.
- Updated canonical curve and table.
- Undo/Redo behavior.
- Rejected thickness edit.
- Final generated CAD after explicit Generate.

---

# PART M — CAD NON-REGRESSION

## 37. Preserve previous engineering acceptance

Run the complete existing backend suite.

At minimum retain acceptance for:

- Three-section blade.
- Five-section reference blade.
- Eight-section blade.
- NACA 0008 thickness override.
- Imported analytic coordinate airfoil.

Require unchanged:

- One valid solid.
- One closed shell.
- Zero non-degenerate free edges.
- BRep validity.
- STEP round-trip.
- Chord/twist/reference-axis tolerances.
- Physical TE tolerance.
- Contour production tolerances.

No changes to OpenVSP/OCP geometry behavior are expected in this sprint.

If a geometry regression appears, report the cause rather than modifying tolerances.

---

# PART N — IMPLEMENTATION STRUCTURE

## 38. Suggested modules

Extend or introduce modules approximately as follows:

```text
frontend/src/
├── components/
│   ├── DistributionChart.tsx
│   ├── DistributionTable.tsx
│   ├── EditableControlPoint.tsx
│   └── ...
│
├── editor/
│   ├── bladespecEditor.ts
│   ├── curveUnits.ts
│   ├── curveTransactions.ts
│   └── useCurveHistory.ts
│
├── App.tsx
└── sprint03c.css
```

Use the existing structure when it provides a cleaner implementation.

Avoid creating unnecessary abstractions.

Separate:

- Screen coordinate conversion.
- Engineering-unit conversion.
- Draft interaction state.
- BladeSpec mutation.
- Validation.
- Undo/Redo history.

Do not put all these responsibilities into one large React component.

## 39. Keep the application maintainable

The previous sprints established a working frontend architecture.

Sprint 03C should improve rather than destabilize it.

Keep dependencies minimal.

Do not add a new global state-management library unless there is a justified need.

Do not rewrite the 3D viewer.

Do not move the backend geometry logic into React.

---

# PART O — DOCUMENTATION

## 40. Deliverables

Create:

`docs/SPRINT_03C_REPORT.md`

`docs/SPRINT_03C_ACCEPTANCE_MATRIX.md`

Update README with user-facing instructions for:

- Dragging a curve control point.
- Interpreting temporary versus committed values.
- Locked thickness controls.
- Undo/Redo.
- Reverting invalid edits.
- Generating STEP after edits.

Document every engineering unit conversion.

Explain that the graph's final interpolation is always determined by the canonical backend.

## 41. Final engineering report

Include:

- Branch and commit SHA.
- Source files changed.
- Actual tests executed.
- Backend test results.
- Frontend test results.
- Browser tests.
- Real STEP validation results.
- Curve-edit transaction behavior.
- Undo/Redo scope.
- Performance evidence regarding preview API calls.
- No-automatic-CAD-generation evidence.
- Known limitations.

Do not claim a STRONG PASS based only on successful pointer movement.

---

# PART P — ACCEPTANCE CRITERIA

Sprint 03C qualifies as STRONG PASS only if:

1. Existing control points are vertically draggable.
2. Dragging does not modify r/R.
3. No hidden control points are inserted.
4. All five engineering distributions support the intended visual-editing workflow.
5. Engineering-unit conversion is exact within numerical tolerance.
6. Draft values are visibly distinguished from committed values.
7. Invalid edits never silently corrupt BladeSpec.
8. NACA and imported-airfoil thickness semantics remain consistent.
9. Canonical Linear/PCHIP plots come from the backend.
10. Numeric tables remain synchronized.
11. Undo/Redo works as documented.
12. A drag produces one atomic history transaction.
13. Escape and pointer cancellation restore the original value.
14. Keyboard-accessible editing is available.
15. No CAD generation occurs automatically during editing.
16. Previously generated CAD becomes stale correctly after a committed design change.
17. Old asynchronous validation responses cannot overwrite newer edits.
18. Existing 3D station inspection and airfoil comparison remain functional.
19. A real browser pointer-editing workflow passes.
20. A real STEP built from edited curve values passes final CAD validation.
21. The existing backend engineering regressions remain green.
22. Frontend tests and production build pass.
23. `00_research_archive` remains unchanged.

If any P0 engineering correctness condition fails, classify the sprint as PASS WITH LIMITATIONS or FAIL.

---

# STRICT SCOPE CONTROL

Do NOT implement in Sprint 03C:

- Dragging control points horizontally to change r/R.
- Drawing completely new arbitrary curves.
- Automatic insertion of control points by clicking the curve.
- Direct editing of airfoil geometry.
- Editing the generated STEP surface with the mouse.
- Automatic OpenVSP regeneration during dragging.
- Thrust or torque calculation.
- Aerodynamic optimization.
- Hub geometry.
- Complete multi-blade propellers.
- A replacement CAD engine.
- A large frontend redesign.

These features belong to future development.

---

# EXECUTION ORDER

**Phase 1 — Engineering Conversion & Transactions**

Implement tested unit conversion, candidate validation, and edit transaction management.

**Phase 2 — Pointer-Based Editing**

Add interactive markers, vertical dragging, cancellation, provisional readouts, and table synchronization.

**Phase 3 — Canonical Preview & History**

Connect commit behavior to the canonical backend, and implement Undo/Redo with revision-safe asynchronous handling.

**Phase 4 — Thickness Safety & Accessibility**

Verify thickness consistency, keyboard editing, invalid-value rollback, and responsive behavior.

**Phase 5 — Acceptance**

Run unit tests, frontend integration, real Chromium pointer workflows, and existing CAD regressions.

Do not bypass a P0 engineering blocker to obtain an apparent UI success.

---

# FINAL INSTRUCTION

Implement Sprint 03C in the existing BladeGen workspace.

Do not stop after planning.

Do not change the validated geometry engine.

Do not automatically merge into main.

**The desired result is a trustworthy visual curve editor that lets an engineer manipulate spanwise blade parameters directly while preserving exact BladeSpec semantics, backend-authoritative interpolation, reliable Undo/Redo, and independently validated final STEP geometry.**