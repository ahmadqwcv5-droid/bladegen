# Patch 03C.1 — Continuous Curve Editing and History Integrity

## Outcome

Patch 03C.1 fixes the repeated-drag lock and eliminates no-op curve transactions without changing BladeSpec v0.2, the canonical SciPy interpolation path, OpenVSP/OCP, or any engineering tolerance. Work is on `patch/03c.1-continuous-curve-editing`, based on reviewed `main` SHA `ea769e0ab979b300b1199615964ec10376ae4c20`.

## Reproduced defect and root cause

The Sprint 03C chart initialized `mounted.current` to `true`, then used an Effect cleanup that set it to `false` but never restored it during Effect setup. React development StrictMode deliberately runs an extra setup/cleanup/setup cycle. The replay therefore left the live chart with `mounted.current === false`.

After the first successful async commit, `finish()` returned at its mounted check and skipped local `validating=false` plus the parent `idle` notification. The marker then rejected another pointer-down until changing distribution tabs remounted the chart.

An explicit `<StrictMode>` regression now performs three consecutive same-marker drags and waits for idle after every commit. It fails with the old lifecycle and passes with the patch.

## Lifecycle and pointer correction

- Every mount Effect setup explicitly restores `mounted.current = true`.
- Unmount cleanup marks the instance obsolete, increments the local operation identity, and releases capture without updating parent React state.
- `finish()` uses `try/catch/finally`; success, rejection, and thrown/network failures return a live current operation to idle.
- Each async finish has an operation identity. A cancellation or newer operation invalidates older completion work.
- Pointer capture is owned by the marker group and released through one guarded path on release, Escape, pointercancel, explicit parent cancellation, or unmount.
- Parent cancellation has an explicit version signal for tab changes, load/new/reset, conflicts, and superseded validation.
- History buttons and Ctrl/Cmd shortcuts use the same deterministic policy: they are disabled/ignored while drafting or validating.

No tab-remount workaround was added.

## No-op policy

No-op protection is layered deliberately:

1. Pointer interaction requires at least 3 CSS pixels of movement before becoming a drag. A click or sub-threshold movement returns to idle without validation.
2. `NumericInput` records whether text was actually edited. Focus/blur, `60` → `60.0`, and clear/restore skip the callback.
3. When a precise stored/display value formats to a shorter readable value, re-entering that displayed identity preserves the original precise value.
4. `commitCurveCandidate()` compares the neutral full BladeSpec serialization before local/backend validation. An unchanged candidate returns successfully without a request, state update, preview invalidation, or history mutation.

This policy does not round BladeSpec. A genuinely distinct high-precision numeric entry is still committed exactly. Curve inputs display up to three decimals for chord/twist/rake/skew and four for thickness percent; precise values remain in exported/saved BladeSpec.

## Undo/redo integrity

The browser acceptance sequence committed Chord 64 mm, undid to 63 mm after the repeated-edit sequence, then performed a marker click and two unchanged numeric blurs. Backend validation remained at five calls and Redo stayed available. Redo restored 64 mm without validation or CAD generation.

Thickness distribution plus explicit station override continues to be one full-spec history transaction, so both values undo together.

## Real StrictMode browser results

Playwright ran against the Vite development application and actual `<React.StrictMode>` root.

Desktop Chord at `r/R=0.50` completed five consecutive edits without a tab change:

`60 → 64 → 62 → 66 → 63 → 64 mm`

Narrow-layout Twist at `r/R=0.65` completed the required five-edit sequence and a final engineering value:

`23 → 27 → 30 → 25 → 28 → 24 → 27°`

For every meaningful drag:

- Ready returned before the next drag.
- Exactly one `/api/validate` request occurred.
- Exactly one post-commit `/api/design-preview` request occurred.
- No validation or preview request occurred during movement.
- No `/api/build` request occurred.

Totals before explicit Generate were 11 validation requests for 11 meaningful drags, zero requests for the no-op interactions, and zero builds.

## Real CAD regression

The clean full-suite Generate action created run `8793aaaf225b43e98e1649d3d802d0bd`. Submitted values were Chord `0.32000000991821287 × 200 = 64.0000019836 mm` and Twist `26.999998316955566°`; the long values are retained in neutral BladeSpec while the table presents readable engineering text.

| Measurement | Result |
| --- | ---: |
| Shape / solids / shells / faces | SOLID / 1 / 1 / 8 |
| Free edges | 0 |
| Closed shell / BRep valid | true / true |
| Volume | 39747.15897454975 mm³ |
| STEP round-trip volume delta | 6.63e-9 mm³ |
| STEP round-trip bbox max delta | 6.43e-12 mm |
| Independent geometry | PASS |
| Max chord / twist error | 0.004420 mm / 0.001522° |
| Max TE error | 0.016732 mm |
| Contour RMS / P95 / max | 0.015673 / 0.032184 / 0.034931 mm |

## Evidence

- [Active draft](screenshots/patch03c1/active_draft.png)
- [Five consecutive Chord edits](screenshots/patch03c1/five_consecutive_chord_edits.png)
- [Six consecutive Twist edits, narrow layout](screenshots/patch03c1/six_consecutive_twist_edits_narrow.png)
- [No-op preserves Redo](screenshots/patch03c1/noop_preserves_redo.png)
- [Final validated CAD](screenshots/patch03c1/final_cad.png)

## Verification

- Focused lifecycle/no-op/history tests: 25 passed.
- Complete frontend unit/integration suite: 18 files, 96 tests passed.
- Production TypeScript/Vite build: passed.
- Focused real Vite/StrictMode/CAD Playwright test: passed in 2.4 minutes.
- Complete backend suite: 92 tests passed in 6 minutes 31 seconds (one dependency deprecation warning).
- Complete cross-sprint Playwright suite: 8 tests passed in 15.7 minutes.

## Remaining limitations

- Display formatting intentionally hides insignificant pointer-coordinate noise; exported BladeSpec is the precise source of truth.
- Curve editing remains vertical-only; horizontal control relocation is outside this corrective patch.
- CAD remains explicit through Generate and is never triggered automatically by editing.
