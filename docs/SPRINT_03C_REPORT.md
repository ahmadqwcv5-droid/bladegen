# Sprint 03C — Visual Curve Editing and Engineering Undo/Redo

## Outcome

Sprint 03C adds transactional vertical editing for Chord, Twist, Rake, Skew, and Thickness without changing the BladeSpec schema, backend CAD engine, canonical interpolator, or validation tolerances. The work is on `sprint/03c-visual-curve-editing`, based on reviewed `main` SHA `96f7b408cdbd181f668f82adc7dd2ad36fd2e79b`.

The chart continues to draw the backend `/design-preview` samples. Frontend code draws and edits only the BladeSpec control markers; it does not implement a second PCHIP evaluator. A pointer gesture changes only a selected ordinate. Its `r/R`, point order/count, and interpolation mode remain fixed.

## Engineering units

One shared conversion module is used by the chart and numeric tables. Values are not rounded on storage.

| Curve | Display | BladeSpec storage |
| --- | --- | --- |
| Chord | mm | `chord_over_R = mm / (diameter_mm / 2)` |
| Twist | deg | `twist_deg` |
| Rake | mm | `rake_over_R = mm / (diameter_mm / 2)` |
| Skew | mm | `skew_over_R = mm / (diameter_mm / 2)` |
| Thickness | % t/c | `thickness_ratio = percent / 100` |

Tests cover D=400 mm, D=720 mm, signed rake/skew, and diameter-dependent physical display semantics. The real acceptance run committed Chord 64 mm at `r/R=0.5` as `0.32000000991821287` after pointer-coordinate precision, and Twist 27° at `r/R=0.65` as `26.999998316955566`.

## Transaction and validation model

During drag, the committed BladeSpec remains unchanged. The UI shows a provisional marker/readout while the previous backend canonical curve stays visible and is labeled as the previous committed curve when appropriate. Pointer moves issue no backend requests.

On release or keyboard adjustment:

1. A full candidate BladeSpec is created from the current committed revision.
2. Local finite/positive/thickness-coordination checks run.
3. Exactly one `/api/validate` request validates the complete candidate.
4. Only a successful, still-current response commits the candidate.
5. The normal revision effect performs exactly one canonical `/design-preview` refresh.

Revision tokens and a before-snapshot check discard late validation responses. Escape, pointer cancellation, distribution-tab changes, unmount, load/new/reset, and conflicting non-curve edits cancel the active transaction. Generate is disabled while drafting or validating. No edit, undo, or redo invokes `/api/build`.

## Undo/redo policy

Curve history stores at most 50 full before/after BladeSpec transactions. It covers chart gestures, keyboard marker edits, numeric ordinate/radius edits, control insertion/removal, and interpolation changes. One drag produces one entry; rejected or cancelled edits produce none. A new edit clears redo.

Ctrl/Cmd+Z, Ctrl/Cmd+Shift+Z, Ctrl+Y, and toolbar buttons are supported. Shortcuts do not intercept input, select, textarea, contenteditable, or dialog interaction. New/load/import/reset establish a new baseline. Any unrelated global or airfoil-station edit clears curve history; snapshot equality also prevents undo/redo from overwriting a conflicting revision.

## Thickness protection

- A control coincident with a NACA station without an explicit override is locked and explains how to enable the override.
- An explicit NACA override updates `thickness_distribution` and `thickness_override_ratio` atomically in the same candidate.
- A control coincident with imported coordinates is locked so natural geometric t/c is preserved.
- A noncoincident thickness control remains editable and is validated as part of the full candidate.
- No airfoil coordinates, trailing-edge definitions, station positions, or control-point radii are changed by vertical editing.

## Pointer and keyboard interaction

The SVG client-to-viewBox conversion handles `getScreenCTM`, `xMidYMid meet` letterboxing, resize, scroll offsets, and reversed SVG Y. The Y-axis domain is captured at pointer-down and remains stable for the gesture. Each marker has a 28 px hit target, visible hover/focus/draft states, pointer capture, live draft readout, and locked-state explanation. The hover overlay is non-interactive so it cannot mask the control hit area.

Focused markers use Arrow Up/Down, with Shift multiplying by ten: Chord 0.5 mm, Twist 0.25°, Rake/Skew 0.5 mm, and Thickness 0.1 percentage point.

## Measured real-CAD result

Playwright performed actual pointer drags at 1280 px and 720 px, checked the chart at 520 px, tested undo/redo and protected thickness, confirmed zero builds before Generate, and then submitted one real build. Run `6a78765b25534e5c87cf008ff829ca32` produced:

| Measurement | Result |
| --- | ---: |
| Shape / solids / shells / faces | SOLID / 1 / 1 / 8 |
| Free edges | 0 |
| Closed shell / BRep valid | true / true |
| Volume | 39747.15897454975 mm³ |
| STEP round-trip volume delta | 6.63e-9 mm³ |
| STEP round-trip bbox max delta | 6.43e-12 mm |
| Independent geometry result | PASS |
| Max chord / twist error | 0.004420 mm / 0.001522° |
| Contour RMS / P95 / max | 0.015673 / 0.032184 / 0.034931 mm |

## Evidence

- [Selected control](screenshots/sprint03c/selected_control.png)
- [Active draft](screenshots/sprint03c/active_draft.png)
- [Updated curve and table](screenshots/sprint03c/updated_curve_table.png)
- [Undo/redo](screenshots/sprint03c/undo_redo.png)
- [Protected thickness](screenshots/sprint03c/rejected_thickness.png)
- [Final validated CAD](screenshots/sprint03c/final_cad.png)

See [the acceptance matrix](SPRINT_03C_ACCEPTANCE_MATRIX.md) for requirement-level verification.

## Verification summary

- Frontend unit/integration: 17 files, 87 tests passed.
- Frontend production build: TypeScript and Vite passed.
- Backend: 92 tests passed in 400.25 seconds; one pre-existing Starlette deprecation warning.
- Focused Sprint 03C Playwright: passed with a real CAD build.
- Complete Playwright regression: 8 tests passed in 14.5 minutes, including all prior real-CAD workflows.
