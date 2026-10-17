# FP02-C1 revised acceptance matrix

Status: **PASS — 8/8 positive cases**  
Evidence run: `fp02_c1_20261015T075331Z`  
Matrix run: `fp02_c1_matrix_20261015T083858Z`  
Base HEAD: `39ffb7229c834d9c1e19eab03b529a83f1e366a3`  
Candidate: dirty worktree, source-set SHA-256
`d39ad693843ce8c317d7c0fd7812a98029ace8f6282bfb766518c77e75dfddd4`

The original FP02 matrix remains historical at 5 PASS / 2 FAIL / 1 REJECTED.
This document is the versioned revised matrix; it does not relabel the old Q02,
Q03 jobs or original Q04.

## Revised positive matrix

| Case | Job ID | Result | Sections | Worker s | Solids / shells / free edges | Closed / valid | Volume mm³ |
| --- | --- | --- | ---: | ---: | --- | --- | ---: |
| Q01 | `90660af5736643059a5e5719c5e41b2e` | PASS | 5/5 | 5.2 | 1 / 1 / 0 | true / true | 26,453.336576 |
| Q02 | `469d862b6fe14422b2b80332e89b2097` | PASS | 11/11 | 57.2 | 1 / 1 / 0 | true / true | 38,122.379112 |
| Q03 | `a56429e42a0c441ca692cba184ab1a43` | PASS | 11/11 | 53.6 | 1 / 1 / 0 | true / true | 38,122.379112 |
| Q04.R1 | `35bea568993c4e39af847d58976ecf73` | PASS | 26/26 | 156.8 | 1 / 1 / 0 | true / true | 38,696.410632 |
| Q05 | `301edf710c7d4c96af7aee2829389987` | PASS | 41/41 | 337.8 | 1 / 1 / 0 | true / true | 46,373.243510 |
| Q06 | `8424714b8e9e49289e96224b14a69c30` | PASS | 11/11 | 57.3 | 1 / 1 / 0 | true / true | 355,402.948431 |
| Q07 | `911643344c1c4fb19cad81708897f394` | PASS | 11/11 | 65.7 | 1 / 1 / 0 | true / true | 392,510.297262 |
| Q08 | `1ab7c9e15c324070b747e0b61ee2f2c2` | PASS | 11/11 | 77.2 | 1 / 1 / 0 | true / true | 429,617.646450 |

Matrix wall time was 819.346 seconds. Every case used the 900-second trial
worker profile, reached strict `succeeded` completion, passed its unchanged full
station plan, final STEP re-import, topology, geometry, and artifact identity
checks. There were no matrix failures.

## Geometry maxima

| Case | Chord mm | Twist deg | Axis mm | Control contour RMS / P95 / sampled max mm | TE mm |
| --- | ---: | ---: | ---: | --- | ---: |
| Q02 | 0.004103 | 0.001669 | 0.004515 | 0.008649 / 0.016225 / 0.019166 | 0.001327 |
| Q03 | 0.004103 | 0.001669 | 0.004758 | 0.008734 / 0.016135 / 0.019113 | 0.001327 |
| Q04.R1 | 0.004866 | 0.032267 | 0.029363 | 0.007783 / 0.015072 / 0.018101 | 0.000218 |
| Q05 | 0.001667 | 0.031526 | 0.020021 | 0.005684 / 0.009408 / 0.010662 | 0.000000 |

All values passed the unchanged production policies. “Sampled max” is not
presented as a continuous mathematical maximum.

## Original Q04 negative regression

Original Q04 SHA-256 is
`c5185fcbf61acb58f8df37405396552329197da444dcf159a7e4fd6f1081d4ba`.
It still returns HTTP 422 before queueing CAD, identifying thickness 0.150000 at
`r/R=0.18` versus imported-coordinate geometric thickness 0.130553. The backend
regression asserts the job registry is unchanged; the real browser regression
also asserts no build request and preservation of the current Q02 project.

## Other gates

| Gate | Result |
| --- | --- |
| Backend suite | PASS, 197/197, 0 failed, 0 skipped, 572.73 s |
| FP02-C1 focused regressions | PASS, 7/7 |
| Frontend unit suite | PASS, 160/160 in 51/51 suites |
| Frontend production build | PASS; only the existing Vite chunk-size warning |
| Consolidated Playwright | PASS, 16/16, 0 failed, 0 skipped, 0 retries, 2346.93 s wall |
| Modified-scope Ruff check/format | PASS, six FP02-C1 Python files |
| Launcher shell syntax | PASS |
| Repository-wide Ruff format | 13 historical files would be reformatted; not changed after candidate qualification |

Machine-readable result:
`qualification/fp02_c1/fp02_c1_20261015T075331Z/decision_summary.json`.

