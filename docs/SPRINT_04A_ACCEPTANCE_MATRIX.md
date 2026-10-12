# Sprint 04A Acceptance Matrix

| Requirement | Evidence | Result |
| --- | --- | --- |
| Neutral versioned PropellerSpec with complete BladeSpec | Pydantic models, JSON Schema, contract tests, three full examples | PASS |
| BladeSpec v0.2 and existing blade path preserved | Existing endpoint/CLI unchanged; complete backend and frontend regressions pass | PASS |
| One OpenVSP reference blade per assembly | Separate propeller pipeline calls existing blade build once, then OCP transforms | PASS |
| Exact X-axis OCP placement | `gp_Trsf`/`BRepBuilderAPI_Transform`; independent direction tests for 2/3/4 and nonzero azimuth | PASS |
| Correct angular spacing | Real results 0/180, 0/120/240, and 0/90/180/270 | PASS |
| Blade geometry/volume preserved | No refit/regeneration; copy volume max delta ≤ 2.19e-11 mm³ | PASS |
| X-axis hub with requested dimensions | Primitive bbox and circular-edge measurements; 90 × 45 mm accepted hub | PASS |
| Genuine root overlap | ~1397.715592 mm³ per blade; threshold > 1e-5 mm³ | PASS |
| Unexpected blade collision rejected | Pairwise common-minus-hub measurement; accepted cases all 0.0 mm³ | PASS |
| True requested through-bore | Two measured 6.0 mm X-axis boundary radii; residual bore material 0.0 mm³ | PASS |
| One connected valid final STEP | All cases: 1 solid, 1 shell, closed, BRep valid, 0 free edges | PASS |
| STEP re-import and mass properties | Volume deltas 3.20e-9 to 2.45e-6 mm³; bbox deltas ≤ 7.48e-11 mm | PASS |
| Separate blade/assembly validation | `reference_blade_validation` and `assembly_validation`; JSON and CSV outputs | PASS |
| Dynamic count with honest qualification | Contract range 2–8; production gate and report qualify only measured 2–4 | PASS WITH LIMIT |
| Real 2/3/4 CAD acceptance | Parameterized OCP test and real browser generation for every count | PASS |
| Invalid bore/dimensions/contact/count | Model/API/real-geometry tests return controlled diagnostics | PASS |
| Fusion, bore-cut, and topology failures | Operation-specific Boolean and round-trip topology tests | PASS |
| Separate engine and CLI | `build_propeller()` and `bladegen build-propeller`; CLI tests and manual real build | PASS |
| API integration and shared serialization | Propeller validate/build endpoints; build type; same one-worker JobManager | PASS |
| Safe artifact allow-list | Required assembly/reference artifacts downloadable; arbitrary name rejected | PASS |
| Confirmed assembly progress and categorized failures | Engine callbacks write actual 40/55/60/70/80/90/95 stages; UI tests | PASS |
| Existing React application and blade editor | Mode switch preserves stations/distributions; prior UI tests pass | PASS |
| Assembly controls and no automatic CAD | Component/browser tests edit/validate with zero build requests until Generate | PASS |
| Actual final-solid STL viewer | Propeller STL artifact selected by result type; front/side/isometric/fit/expand | PASS |
| Result identity and stale behavior | Full submitted blade+assembly snapshot; parameter and mode changes tested | PASS |
| Single-blade guides not misleading | Guides disabled with explanation in propeller mode | PASS |
| Future desktop boundary documented | Core has no UI/API imports; explicit paths/CLI/runtime config; no framework selected | PASS |
| Backend regression | 125 passed in 526.29 s | PASS |
| Frontend regression/build | 19 files / 104 tests; production build passed | PASS |
| Real browser workflow and screenshots | 9/9 full-suite workflows in 21.2 min; Sprint 04A 2/3/4 builds in 6.2 min; seven real screenshots | PASS |
| Historical archive unchanged | No path under `00_research_archive` modified | PASS |

All P0 topology, axis, connection, bore, preservation, and regression gates pass
for the explicitly qualified 2–4 blade range. Counts 5–8 are not claimed as
production-ready in Sprint 04A.
