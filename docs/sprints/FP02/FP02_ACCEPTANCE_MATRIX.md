# FP-02 acceptance matrix

Overall: **FAIL — `FP02_BLOCKED`**. Frozen primary cases: 5 PASS, 2 FAIL, 1 REJECTED. The mandatory 8/8 criterion is not met.

Execution profile: `level1-trial`, 900-second worker budget per design. Runtime fingerprint: `af69cfbeb477880fd7caf13c3fbdef3a2f69f40430dafe4e5a330d9bb7836edd`. Production source-set aggregate: `0027501806ebcf39e9dc60914ae18d468f9b5cc82268369a5a22985af8f8f0e3`.

## Frozen geometric cases

| Case | Coverage | Planned / completed | Job ID | Worker | Result | CAD/topology evidence |
|---|---|---:|---|---:|---|---|
| Q01 | Three NACA 0012 stations, Linear, zero rake/skew/TE | 5 / 5 | `9668a1f1296f48d9a7372e74c24fcb0e` | 8.1 s | PASS | 1 solid, 1 shell, 0 free edges, closed/valid; 26453.336576 mm³ |
| Q02 | Five mixed/cambered NACA stations, positive rake, finite TE, PCHIP | 11 / 11 | `e6f029a7d0c742e2a425ee4176b40c6d` | 84.0 s | **FAIL** | Retained STEP topology valid, but contour RMS/P95 and TE fail at r/R 0.30 and 0.35 |
| Q03 | Q02-derived negative rake and signed skew | 11 / 11 | `e20845cd8930418fad31a9dc9f4cba30` | 82.3 s | **FAIL** | Retained STEP topology valid, but the same section gates fail at r/R 0.30 and 0.35 |
| Q04 | Eight imported-coordinate stations, independent grids, explicit thickness, Reverse | 26 / 0 | none | n/a | **REJECTED** | Input validation: 0.150000 thickness conflicts with measured coordinate thickness 0.130553 |
| Q05 | Source-derived X-57, two profiles, 40 controls, full plan | 41 / 41 | `dbb4b182944245c9bb579b12babb190b` | 438.6 s | PASS | 1 solid, 1 shell, 0 free edges, closed/valid; 46373.243510 mm³ |
| Q06 | Supported two-blade propeller | 11 / 11 | `8efa7d2e56734d9aa6cceddcfa017487` | 91.1 s | PASS | 2 requested/placed; final 1 solid, closed/valid; 355402.948431 mm³ |
| Q07 | Supported three-blade propeller | 11 / 11 | `19a8ae9942804a19bf5a4400146c1fce` | 85.0 s | PASS | 3 requested/placed; final 1 solid, closed/valid; 392510.297262 mm³ |
| Q08 | Supported four-blade propeller | 11 / 11 | `f5e33401a852420189796d311049f2b1` | 100.2 s | PASS | 4 requested/placed; final 1 solid, closed/valid; 429617.646450 mm³ |

### Q02/Q03 failure detail

| Case | r/R | Failed flags | RMS mm | P95 mm | Maximum mm | TE error mm |
|---|---:|---|---:|---:|---:|---:|
| Q02 | 0.30 | contour RMS, contour P95, TE | 0.116576 | 0.197971 | 0.199864 | 0.047620 |
| Q02 | 0.35 | contour RMS, contour P95, TE | 0.100795 | 0.171000 | 0.172756 | 0.042181 |
| Q03 | 0.30 | contour RMS, contour P95, TE | 0.116597 | 0.197961 | 0.199834 | 0.047620 |
| Q03 | 0.35 | contour RMS, contour P95, TE | 0.100795 | 0.171000 | 0.172756 | 0.042181 |

No failed input, station, tolerance, or policy was changed after these observations. Full measurement JSON is retained under `qualification/fp02/evidence/matrix/fp02_20261015T072300Z/`.

## Browser acceptance

| Workflow | Result | Evidence |
|---|---|---|
| U1 Q01 visible authoring, Generate, save/open in isolated context | PASS | Job `45f79b86e57e410f9af8e19c37bf8daf`; 5/5; worker 7.2 s |
| U1 frozen Twist edit and explicit rebuild | PASS | Job `1dc14de8d0424afea21772247dceb806`; measured +3.000000000002°; worker 8.9 s |
| U1 supported Q06 propeller through UI | PASS | Job `654cecad2ec3430686470ae66d62e4c3`; worker 97.3 s |
| U2 actual X-57 profile/distribution UI import and candidate export | PASS | Exact source conversion fidelity; documented thickness representation difference |
| U2 Apply-to-current-preview | PASS | Cold 535.2 ms; warm median 546.15 ms, P95 600.225 ms, max 604.5 ms; zero builds on Apply |
| U2 explicit X-57 Generate and downloads | PASS | Job `fe7aa0576c894a84a3b2f196d7c4a09d`; 41/41; worker 369.7 s; required artifacts current-job scoped |
| U2 internal STEP validation | PASS | 1 solid/shell, 6 faces, 0 free edges, closed and BRep-valid; volume 46373.243509611435 mm³ |
| External NASA surface fidelity | **UNVERIFIED** | No official NASA VSP3/STEP geometry was supplied for an external surface comparison |

## Software qualification gates

| Gate | Result |
|---|---|
| Complete implementation identity and missing-file rejection | PASS |
| Strict completed-result verification | PASS |
| One effective timeout value across supervisor/worker/manifest | PASS |
| Managed-runtime doctor | PASS |
| Backend full suite | PASS — 190 tests, 0 skipped |
| Focused hardening regressions | PASS — 14 tests |
| Frontend unit suite | PASS — 160 tests |
| Frontend production build | PASS |
| Ruff lint | PASS |
| Ruff format check | LIMITATION — 3 files would be reformatted; frozen code not mutated after CAD evidence |
| Shell syntax | PASS |
| Consolidated Playwright | PASS — 15/15, 0 skipped, 0 retries, 36.1 min |
| Eight frozen primary cases | **FAIL — 5/8 PASS** |
| User hands-on acceptance | PENDING |

Machine authority: [`case_manifest.json`](../qualification/fp02/case_manifest.json), [`matrix_results.json`](../qualification/fp02/evidence/matrix/fp02_20261015T072300Z/matrix_results.json), and final [`U2 evidence_summary.json`](../qualification/fp02/evidence/browser/fp02_20261015T055954Z/U2/evidence_summary.json).
