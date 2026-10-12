# Sprint 03C Acceptance Matrix

| Requirement | Evidence | Result |
| --- | --- | --- |
| Chord/Twist/Rake/Skew/Thickness visual controls | Shared `CURVES` definitions and `DistributionChart`; unit/integration tests | PASS |
| Vertical-only editing; stable r/R/order/count/interpolation | Candidate test verifies exact unchanged fields; real pointer test moves X while r/R stays fixed | PASS |
| One bidirectional unit module, no storage rounding | `curveEditing.ts`; D=400/D=720 tests | PASS |
| Pointer mapping under resize/letterbox/scroll/reversed Y | Pure coordinate tests plus real 1280/720/520 browser path | PASS |
| Large targets, hover/focus, pointer capture, draft readout | 28 px target, CSS states, pointer tests, screenshots | PASS |
| Escape/pointercancel/tab/unmount cancellation | Component cancellation handlers and validation revision invalidation | PASS |
| No requests during moves; one validation and one preview after commit | App acceptance mocks and Playwright request counters | PASS |
| Committed spec unchanged while draft/validation is active | Pending-validation test; preview call count remains unchanged | PASS |
| Invalid/cancelled/stale candidates cannot commit | Local rejection, backend rejection, and deferred stale-response tests | PASS |
| Positive chord/thickness; signed rake/skew | Pure candidate tests | PASS |
| Natural NACA/imported t/c protected | Lock tests and protected-thickness browser evidence | PASS |
| NACA explicit override is atomic | Full candidate test asserts distribution and station override both become 0.135 | PASS |
| Numeric table and chart use identical engineering semantics | Shared definitions/converters; app acceptance test | PASS |
| Bounded engineering undo/redo | 50-entry history implementation; undo/redo/conflict/redo-clear tests | PASS |
| History includes numeric/structure/interpolation edits | All table mutation paths use `commitCurveCandidate` | PASS |
| New/load/import/reset baseline and unrelated-edit invalidation | `load` and non-curve `update` clear/cancel history; conflict test | PASS |
| Keyboard shortcuts avoid text fields/dialogs | Window handler target guard; unit/browser interaction tests | PASS |
| Marker Arrow/Shift increments | Chart keyboard test verifies Twist Shift+Arrow = +2.5° | PASS |
| Generate disabled during draft/validation; no build on edit/history | App state and Playwright build counter | PASS |
| Old CAD guides stay revision-safe | Existing Sprint 03B snapshot logic retained; prior tests pass | PASS |
| Canonical curve remains backend-generated | Chart consumes `/design-preview`; no frontend curve interpolation added | PASS |
| Real final CAD uses Chord≈64 mm and Twist≈27° | Downloaded `blade_spec.json`, run `6a78765…`; geometry PASS | PASS |
| Frontend unit/integration suite | 17 files, 87 tests | PASS |
| Frontend production build | `tsc -b && vite build` | PASS |
| Focused real Playwright Sprint 03C | 1 test, 1.7 min, actual OpenVSP/OCP build | PASS |
| Full backend regression | 92 passed in 400.25 s | PASS |
| Complete cross-sprint Playwright regression | 8 passed in 14.5 min | PASS |

All P0 requirements and all required regression gates passed.
