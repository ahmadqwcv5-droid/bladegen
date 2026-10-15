# Independent source review — BladeGen Sprint 04B

## Revision and scope

Reviewed revision: `1549e988acc2f6c3713cef82149547d9fb3d5903` (main merge PR #13).
Implementation branch tip: `1cdb564a2eb92b0171acbab705b41ca63b57416c`.
The delivery summary/report's uncommitted-working-tree statement predates the published merge.

Assessment: **PASS WITH LIMITATIONS / conditional acceptance**. Bulk ingestion and prepared evaluation are substantive improvements. Final acceptance still requires the original X-57 UI workflow, a pending-Apply cancellation fix/test, stricter malformed-CSV handling, and end-to-end interaction timing rather than treating dialog-open time as commit latency.

## Independently executed evidence

Six source files or unchanged dependencies were copied into this audit environment and checked against their Git blob SHA-1. See `results/fingerprints.json`.

- 24 ordinary Node checks passed on the actual distribution-import, station-setup, and history helper implementations.
- 11 prepared-curve evaluator checks passed with real NumPy/SciPy, including deterministic random curves, exact knots, near knots, endpoints, 5001 dense locations, domain rejection, constructor reuse, and the real X-57 fixture's four distributions.
- These are **35 passing ordinary checks**, not a full repository suite. Exploratory probes below are deliberately not counted as successful requirements.

The X-57 CSV fixture was taken from the previously supplied `SPRINT_04B_Efficient_Input_Agent_Pack.zip`, not invented or downloaded as a different reference revision. The parser read all 40 rows; the candidate builder preserved all 160 mapped values/radii under the documented physical-to-normalized conversions, the two source airfoil assignments, and the unchanged two-point thickness definition. The input snapshot was assembled by this audit harness. It was NOT entered through React and is NOT evidence of an end-user UI import, semantic preflight completion, STEP generation, or NASA geometry fidelity.

PCHIP and Linear comparisons produced zero difference for the tested queries relative to the respective direct SciPy/NumPy evaluations with explicit source-knot restoration. This is not a comparison against the original OpenVSP PCHIP implementation or the NASA surface.

## Finding 1 — Cancel during pending Apply does not invalidate the transaction

**P1.** In `frontend/src/App.tsx`, the DistributionImportDialog Cancel callback only clears `distributionImportSnapshot`; the station-setup Cancel similarly clears its dialog snapshot. Neither invalidates the outstanding `curveValidationRevision` token. `commitCurveCandidate()` remains alive in App and commits on successful validation if that token and the underlying BladeSpec still match.

The dialog's Cancel buttons remain enabled during validation. Therefore closing the dialog is not equivalent to canceling its pending edit.

`probe_cancel.cjs` reproduces the published callback control flow with recording state setters and a deferred validation response. Sequence: Apply -> pending validation -> Cancel closes dialog -> successful response. Result: dialog closed, candidate accepted, chord changed from 0.30 to 0.32, one history entry. This is an **isolated callback/control-flow reproduction, not a mounted React or Playwright run**.

Required closure test: delay `/api/validate`, click Apply Once, click Cancel, release a successful response, then assert the committed BladeSpec/history are unchanged and the editor is usable. Repeat for station setup. Invalidate only the owned transaction and guard late responses; closing a dialog alone is insufficient.

The repository's Sprint04B component Cancel test exercises cancellation before Apply, so it does not cover this case.

## Finding 2 — malformed numeric CSV fields can be silently transformed

**P2.** The custom CSV lexer accepts a quote embedded in an unquoted field. For example:

```
r_over_R,chord_mm
0.20238,6"4"
1,30
```

The actual `parseDelimitedTable()` and `buildDistributionCandidate()` accept this and produce 64 mm. This is not a valid ordinary quoted numeric field; it should produce a row/column parsing error, not a salvaged value. An ordinary correctly quoted `"64"` must remain supported. The exploratory results also record acceptance of JavaScript hexadecimal numeric syntax (`0x40`); define the documented accepted numeric grammar explicitly rather than silently relying on every form accepted by Number().

These exploratory malformed cases do not occur in the provided X-57 fixture.

## Finding 3 — timing evidence does not yet measure the complete user operation

The reported UI acknowledgement p95 of 71.929 ms times opening the Import Distributions dialog. It does not measure Add Control Point or Apply -> validated data -> current canonical preview -> ready-to-edit.

The 28.509/47.175 ms validation-plus-preview figures use FastAPI TestClient sequential requests. They exclude browser events, debouncing, transfer, and React rendering. The parser benchmark is likewise a helper microbenchmark, not a full review-render timing.

The prepared evaluator is genuinely improved, and the independent numerical checks support correctness. Still, record browser end-to-end cold/median/p95/max timings on the real 40-row fixture and a 200-row stress case, including repeated single-point editing, before claiming the interactive latency targets are completely qualified. Do not infer that the user still experiences slowness from this evidence gap alone.

## Missing-fixture handoff

The original supplied agent ZIP **contains** `fixtures/x57_manual_reference/` and its six files. All seven entries in its top-level manifest (prompt plus fixtures) match their recorded hashes. We cannot determine why that folder was absent from the agent's workspace; the report's refusal to invent replacement NASA data was correct.

A fixture-only ZIP was created with the exact same fixture bytes and paths:
`/mnt/data/X57_Fixtures_For_Sprint04B.zip`.

After extraction at repository root, verify from `fixtures/x57_manual_reference` with `sha256sum -c SHA256SUMS.txt`. Then execute the actual source-airfoil upload, bulk station setup, actual 40-row import/review/Apply, exported-candidate comparison, and explicit CAD build. Record failure evidence as faithfully as success. Do not substitute the synthetic linear-gradient fixture for NASA qualification.

## Repository-reported evidence (not rerun here)

- Backend: 149 passed, 11 deselected.
- CAD integration: 11 passed, 149 deselected.
- Frontend: 156 passed.
- Playwright: 12/12 passed, zero skips/retries, 25.2 min.
- Production build and Ruff passed.
- Synthetic blade: one solid, one shell, 8 faces, closed/valid, zero free edges; reported volume 43173.686527240505 mm3.
- Synthetic three-blade propeller: one solid, one shell, 28 faces, closed/valid, zero free edges; reported volume 406699.16175732994 mm3.

These are generic synthetic-case results, not X-57 fidelity measurements.

## Limitations of this review

A pinned-revision archive download failed due to DNS resolution, so this review used connector-read source and targeted byte-verified modules. The entire repository, React/Vitest/Playwright application, OpenVSP generation, and new STEP files were not run or measured independently here. No old uploaded STEP was substituted for a current build result. Timing targets were not independently qualified on the user's machine.

Environment and per-case outputs are under `results/`.

## Reproduction

```
NODE_PATH=$(npm root -g) node run_helpers.cjs
python run_curves.py
node probe_cancel.cjs
```

The helper scripts use mounted source fixtures under `/mnt/data` in this audit environment; adjust those explicit fixture paths when running elsewhere. TypeScript transpilation and the Python package init files are audit harness plumbing, not claimed as repository production code.

## Recommendation

Retain the new architecture. Do not restart Sprint 04B or the CAD engine. Make the narrow cancellation/parser corrections, supply the already-existing fixture pack, and complete the end-user X-57 workflow and full interaction timing on one pinned final revision. Keep four conclusions separate: bulk input usability, numerical correctness, CAD validity, and external NASA fidelity.
