# SPRINT 03C.1 — Continuous Curve Editing & History Integrity


## Objective

Fix the interaction reliability problems discovered in Sprint 03C Visual Curve Editing.

The user reported a reproducible usability defect:

**After dragging a curve control point and committing a change, the same point often cannot be dragged again. Switching to another distribution tab and returning restores editing.**

Source-code review identified a likely React lifecycle cause, along with a separate no-op editing/history defect.

This patch must resolve both problems and make consecutive curve editing reliable.

Do not introduce new design features.

Do not replace or modify the validated CAD engine.

---

# PART A — REPOSITORY PREPARATION

## 1. Inspect current project state

Review the latest Git state and preserve any uncommitted changes.

Last reviewed main commit:

`ea769e0ab979b300b1199615964ec10376ae4c20`

Verify the latest actual HEAD.

Create a dedicated branch:

`patch/03c.1-continuous-curve-editing`

Do not automatically merge into main.

Do not modify `00_research_archive`.

## 2. Relevant code

Inspect at minimum:

- `frontend/src/components/DistributionChart.tsx`
- `frontend/src/components/NumericInput.tsx`
- `frontend/src/components/DistributionTable.tsx`
- `frontend/src/editor/curveEditing.ts`
- `frontend/src/App.tsx`
- `frontend/src/Sprint03C.test.tsx`
- `frontend/src/components/DistributionChart.test.tsx`
- `frontend/e2e/sprint03c.spec.ts`
- `frontend/src/main.tsx`

Preserve BladeSpec v0.2, OpenVSP, OCP, SciPy PCHIP, and existing engineering tolerances.

---

# PART B — P0: FIX THE REPEATED-DRAG FAILURE

## 3. Investigate React StrictMode lifecycle

The current `DistributionChart.tsx` contains:

```tsx
const mounted = useRef(true)

useEffect(
  () => () => {
    mounted.current = false
    onInteractionChange?.('idle')
  },
  [onInteractionChange]
)
```

The application root uses:

```tsx
<React.StrictMode>
  <App />
</React.StrictMode>
```

React development StrictMode performs an additional Effect setup/cleanup cycle.

The current cleanup sets `mounted.current` to false, but the Effect setup does not restore it to true.

Consequently, after a successful `onCommit`, `finish()` may exit early:

```tsx
if (!mounted.current) return
```

This skips resetting local `validating` state and notifying the parent that editing returned to idle.

The point can remain effectively locked until `DistributionChart` is remounted by switching tabs.

**Confirm this lifecycle diagnosis through an executable regression test and correct the underlying cause.**

Do not simply force-remount the chart after each edit.

## 4. Correct mounted/unmounted handling

Ensure the lifecycle flag is correct after each real Effect setup, including StrictMode remount simulations.

A suitable pattern is:

```tsx
useEffect(() => {
  mounted.current = true

  return () => {
    mounted.current = false
  }
}, [])
```

However, review all existing cleanup logic before implementing.

Avoid causing parent-state updates from an unrelated Effect cleanup.

Use an explicit transaction cancellation mechanism for pending work.

The implementation must remain safe when:

- The component unmounts.
- A distribution tab changes.
- A request is superseded.
- The user loads another BladeSpec.
- An async validation fails.
- React StrictMode replays Effects.

## 5. Make validation completion exception-safe

Review the existing `finish()` operation.

Use robust `try/catch/finally` behavior.

Required:

- On success: return to idle.
- On rejected candidate: return to idle.
- On network failure: return to idle.
- On thrown or rejected Promise: return to idle.
- On cancellation: release interaction resources.
- On unmount: do not update an obsolete component.
- On superseded transaction: do not affect a newer interaction.

No unhandled Promise rejection may leave the editor locked.

Do not assume that `onCommit()` always returns successfully.

## 6. Repeated editing must work immediately

The engineer must be able to edit the same point several times consecutively without:

- Switching tabs.
- Clicking elsewhere.
- Reloading the page.
- Pressing Reset.
- Reopening the project.

Test the following:

```text
Open Twist chart

Control point at r/R = 0.65:

23° → 27°
27° → 30°
30° → 25°
25° → 28°
28° → 24°

All edits must succeed consecutively
without changing tabs.
```

Each successful edit should create one valid engineering history transaction.

The editor must return to Ready/idle after every successful validation.

---

# PART C — P0: PREVENT NO-OP EDITS

## 7. Current no-op problem

Source inspection found that releasing a point without meaningful movement can invoke the normal commit path.

Similarly, `NumericInput.tsx` calls `onCommit()` on blur even when the displayed number has not changed.

This can cause:

- Unnecessary backend validation.
- Unnecessary canonical-preview refresh.
- False stale-CAD detection.
- Redundant Undo entries.
- Accidental clearing of Redo history.

A no-op interaction must not become an engineering transaction.

## 8. Distinguish click from drag

Track the initial pointer location and the original engineering value.

Introduce an appropriate small pointer movement threshold, such as approximately 3 CSS pixels.

If the engineer merely clicks a marker and releases it without intentional movement:

- Do not submit validation.
- Do not modify BladeSpec.
- Do not add an Undo entry.
- Do not clear Redo.
- Do not mark CAD stale.
- Do not refresh the canonical curve unnecessarily.

The marker may remain selected/focused.

Do not use the threshold to limit precise numeric input.

## 9. Preserve numeric identity for no-op edits

Floating-point unit conversion may produce tiny differences even when the user has not intentionally changed the engineering value.

For example:

```text
Stored normalized Chord
    ↓
Displayed physical Chord in mm
    ↓
Converted back to normalized Chord
```

This round trip can create a tiny representation difference.

Implement a deliberate no-op detection policy.

Requirements:

- Preserve the original stored value if the user made no substantive change.
- Avoid false history entries from representation noise.
- Do not round all BladeSpec values merely for display.
- Do not discard legitimate high-precision edits entered numerically.
- Avoid globally applying an arbitrary large epsilon to engineering parameters.

Prefer detecting the unchanged edit before unnecessary unit reconversion when possible.

Use clearly documented, unit-aware comparison rules where unavoidable.

## 10. Fix NumericInput blur behavior

Update `NumericInput.tsx` so losing focus without a meaningful value change does not call the engineering commit callback.

Required cases:

- Focus and blur without typing.
- Re-enter the same numeric value.
- Enter an equivalent textual representation, such as `60.0` instead of `60`.
- Clear and restore the original value.
- Enter an actual different value.

Only the last case should create a new engineering transaction.

Preserve valid high-precision input.

---

# PART D — UNDO/REDO INTEGRITY

## 11. No-op history protection

Add a second defensive check at the transaction boundary in `App.tsx`.

Even if a child component accidentally submits an unchanged candidate, `commitCurveCandidate()` must reject it as a no-op without treating it as a failure.

No-op candidates must not:

- Call the backend unnecessarily.
- Update BladeSpec.
- Create Undo entries.
- Clear Redo entries.
- Invalidate the current design preview.
- Mark an existing matching CAD result stale.

Ensure that the transaction comparison is based on the actual neutral BladeSpec engineering values, not formatted UI text.

## 12. Preserve Redo after a no-op

Required acceptance sequence:

```text
Original Chord = 60 mm

Change to 64 mm
Undo → 60 mm

Click the same marker without moving
Focus/blur the numeric input without changing

Redo must still be available.

Redo → 64 mm
```

This sequence must be tested through actual React interactions.

## 13. Protect Undo during an active drag

Audit Ctrl/Cmd+Z behavior during:

- Active pointer dragging.
- Pending backend validation.
- An unfinished keyboard edit.

Do not allow an Undo operation to corrupt an active curve transaction.

Choose one explicit policy:

- Disable history actions until the transaction completes; or
- Cancel the current draft safely before executing history operations.

Prefer the simpler deterministic approach.

The toolbar and keyboard shortcuts must follow the same policy.

Test Escape cancellation separately.

## 14. Preserve atomic edits

One drag must still create exactly one history entry.

If a Thickness Override update changes both the distribution and a station override, Undo must restore both together.

Do not alter existing history semantics for legitimate changes.

---

# PART E — POINTER CAPTURE AND CONTINUOUS INTERACTION

## 15. Audit pointer event ownership

Review:

- `onPointerDown`
- `onPointerMove`
- `onPointerUp`
- `onPointerCancel`
- `setPointerCapture`
- `releasePointerCapture`

Ensure pointer capture is consistently owned and released.

Do not rely on changing distribution tabs to clear captured interaction state.

Verify:

- A released pointer can immediately start a new drag.
- Escape releases/cancels the active gesture.
- Pointer cancellation restores the original committed value.
- The marker remains editable after failed validation.
- Dragging beyond the marker's hit area works appropriately.
- Starting another gesture during pending validation is handled predictably.

Avoid duplicate commit events caused by event bubbling.

## 16. Avoid excessive re-render and request activity

Keep local pointer-draft updates responsive.

No `/api/validate` requests during pointer movement.

No `/api/design-preview` requests during pointer movement.

No `/api/build` requests from chart editing.

At most one validation request per meaningful committed drag.

Use the existing revision-safe canonical preview mechanism after success.

Do not add speculative timer-based geometry updates.

---

# PART F — NUMERIC DISPLAY READABILITY

## 17. Improve displayed engineering values

The current interface sometimes displays excessively long values, for example:

```text
64.00000198364258 mm
```

These values may result from pointer-coordinate precision.

Improve display formatting without altering stored precision.

Suggested display conventions:

- Chord/Rake/Skew: approximately 3 decimal places by default.
- Twist: approximately 3 decimal places.
- Thickness: approximately 3–4 decimal places in percent.

The engineer must retain access to the actual precise value through the saved BladeSpec or an appropriate detailed display.

Do not force-round the neutral BladeSpec unless that change is explicitly part of a documented user operation.

Do not make Undo restore a formatted approximation instead of the original engineering value.

---

# PART G — REQUIRED TESTING

## 18. StrictMode regression tests

Add an explicit React.StrictMode test.

Verify that:

1. The chart mounts under StrictMode.
2. A first drag completes.
3. Validation succeeds.
4. The component returns to idle.
5. A second drag on the same marker succeeds.
6. A third drag also succeeds.
7. No tab switching is necessary.
8. No lingering mounted/validating state remains.

Do not test only a single edit.

## 19. Repeated browser dragging

Run Playwright against the real Vite development application, not only a production bundle.

Use the actual React StrictMode application.

Execute at least five consecutive edits to the same Twist point.

After each edit:

- Wait for Ready.
- Confirm the actual value changed.
- Confirm only one validation request was issued.
- Confirm the canonical preview is current.
- Confirm the next drag starts normally.

Run the same scenario with Chord.

Test both desktop and narrow layouts.

## 20. No-op regression tests

Cover:

- Pointer-down/up without motion.
- Pointer movement below the drag threshold.
- Input focus/blur without change.
- Equivalent numeric text.
- Undo, followed by no-op, followed by Redo.
- Floating-point display/storage conversion round trips.
- Multiple consecutive no-ops.

Assert zero unnecessary validation requests and zero history additions for no-ops.

## 21. Cancellation and failure tests

Cover:

- Escape.
- Pointercancel.
- Backend validation rejection.
- Network failure.
- Component unmount.
- Tab change.
- Late response from superseded validation.
- Active Undo/Redo shortcut during a drag.

Every completed or cancelled interaction must leave the chart ready for future editing.

## 22. Real engineering regression

Preserve existing curve-value semantics.

Test:

```text
Diameter: 400 mm

Chord:
r/R 0.50
60 mm → 64 mm

Twist:
r/R 0.65
23° → 27°
```

Verify the committed values in neutral BladeSpec.

Then generate a real STEP using the explicit Generate action.

Require the existing:

- One valid solid.
- Closed shell.
- Zero free edges.
- BRep validity.
- STEP round-trip.
- Chord/twist/TE/contour tolerances.

Do not modify the geometry engine to fix UI interaction issues.

## 23. Full regression suite

Run:

```bash
./scripts/test_backend.sh

cd frontend
npm test
npm run build
npm run test:e2e
```

Add the focused StrictMode development-mode Playwright test to the suite.

Report actual pass/fail/skip numbers.

---

# PART H — DELIVERABLES

## 24. Documentation

Create:

`docs/PATCH_03C_1_REPORT.md`

Include:

- Reproduced repeated-drag failure.
- Root cause and StrictMode behavior.
- Corrected lifecycle and pointer handling.
- No-op detection policy.
- Undo/Redo preservation.
- Numerical display formatting.
- Real browser request counts.
- Results of five consecutive same-point edits.
- Existing CAD regression results.
- Screenshots of repeated successful editing.
- Remaining limitations.

## 25. Acceptance requirements

This patch is STRONG PASS only if:

1. The same control point can be dragged repeatedly without switching tabs.
2. Validation success returns the editor to idle.
3. Validation failure returns the editor to idle.
4. React StrictMode does not leave stale mounted state.
5. Clicking without moving does not commit an edit.
6. Focusing/blurring unchanged numeric input does not commit.
7. Floating-point round trips do not create false engineering changes.
8. No-op edits preserve Redo.
9. Undo/Redo is safe during active gestures.
10. Pointer capture is reliably released.
11. No additional backend requests occur during movement.
12. A meaningful drag generates one history transaction.
13. Existing thickness protections still work.
14. Frontend/browser regressions pass.
15. Final STEP engineering regression passes.
16. Historical archive files remain untouched.

Do not claim STRONG PASS if the test requires changing tabs between consecutive drags.

---

# STRICT SCOPE CONTROL

Do NOT implement:

- Horizontal control-point dragging.
- New interpolation algorithms.
- Automatic CAD regeneration.
- New airfoil families.
- Hub or multi-blade geometry.
- Aerodynamic analysis.
- Major frontend redesign.
- Changes to OpenVSP/OCP.
- Changes to engineering tolerances.

This is a corrective patch.

---

# EXECUTION PRIORITY

1. Reproduce and fix the StrictMode repeated-drag lifecycle defect.
2. Correct async completion and pointer capture.
3. Eliminate no-op commits and preserve history.
4. Improve numeric display formatting.
5. Run repeated-interaction browser tests.
6. Run all frontend/backend/CAD regressions.
7. Document reproducible results.

# FINAL INSTRUCTION

Implement the patch immediately in the existing BladeGen workspace.

Do not stop after planning.

Do not automatically merge into main.

**The engineer must be able to modify the same curve point repeatedly and naturally, with no tab-switch workaround, no phantom history transactions, no stale validation state, and no loss of engineering accuracy.**