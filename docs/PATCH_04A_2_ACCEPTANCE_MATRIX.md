# Patch 04A.2 Acceptance Matrix

| Requirement | Evidence | Result |
| --- | --- | --- |
| NACA 4412 nominal mismatch rejected before CAD | Shared resolver regression, API 422, no `jobs.submit` | PASS |
| NACA 0000 positive-thickness mismatch rejected | Canonical mathematical/semantic regression | PASS |
| Valid explicit NACA override retained | 0.20 override with matching curve passes preflight | PASS |
| Override/curve disagreement rejected | Structured resolver and API tests | PASS |
| Coordinate natural-thickness policy retained | Mismatch rejects; valid coordinates accepted unchanged | PASS |
| Direct build cannot bypass semantics | `/build` returns 422 and submission spy remains unused | PASS |
| Python pipeline cannot bypass semantics | Rejects before output/reference-blade generation | PASS |
| Errors are structured and safe | `invalid_blade_spec`, field, station/airfoil/thickness context; no traceback/input dump | PASS |
| Preflight remains non-CAD | Section resolver only; no OpenVSP, OCP, files, or jobs | PASS |
| Missing azimuth becomes 0.0 | Backend normalization and frontend import tests | PASS |
| Explicit zero/nonzero preserved | 0 and 17.5 regression cases | PASS |
| Null/nonnumeric/nonfinite azimuth rejected | Raw preflight/parser regressions | PASS |
| Existing hub/count policy preserved | Hub/bore and unsupported 5–8 tests remain passing | PASS |
| New build captured by full job ID | Response listener installed before click; exact 202/queued ID captured | PASS |
| Exact job status controls acceptance | Poll `/api/jobs/{id}`; prompt failure; exact result data attribute | PASS |
| Artifacts belong to captured job | URLs plus `propeller_spec.json` and `validation.json` verified | PASS |
| Old A cannot satisfy pending B | Deterministic identical-input race test | PASS |
| Failed B cannot be masked by A | Historical A remains visible but acceptance remains unsatisfied | PASS |
| Delayed A cannot replace active B | Adversarial component test | PASS |
| Invalid 60 mm edit creates no build | Real browser sequence retains A and observes no build request | PASS |
| Save/open uses isolated frontend context | `browser.newContext()` with only downloaded JSON imported | PASS |
| Complete project restored | Mode, names, airfoils, distributions/interpolations, and assembly asserted | PASS |
| Rebuild C verified as a new job | Distinct C ID, exact result binding, job artifacts checked | PASS |
| Semantic-invalid import is atomic | Current project preserved and no CAD starts | PASS |
| Real 90×30 topology retained | 1 solid, 1 shell, 20 faces, closed, valid, 0 free edges | PASS |
| Root overlap/collision gates retained | Both overlaps ~1381.2065 mm³; outside-hub collision 0 | PASS |
| Bore and mass properties retained | 6 mm radius, zero residual, volume 261815.11278796682 mm³ | PASS |
| STEP round-trip retained | Volume delta 3.92e-8 mm³; bbox delta 7.44e-11 mm | PASS |
| Full backend non-integration suite | 147 passed, 11 deselected, 0 failed | PASS |
| Full CAD integration suite | 11 passed, 147 deselected, 0 failed | PASS |
| Frontend unit/build/lint | 122 tests, production build, and Ruff pass | PASS |
| Cross-sprint browser suite | Exact commit `21a0246157bae2f81cc485428656574a59f6c951`; one `npm run test:e2e` invocation; 11 collected, 11 passed, 0 failed/skipped/retried in 27.1 min | PASS |
| Historical archive unchanged | No path below `00_research_archive` modified | PASS |

Overall classification: **STRONG PASS**. All required product behavior has direct
evidence, and the previous consolidated-browser verification limitation is now
closed by a single final unchanged-commit 11/11 run with no retries. At closure,
the follow-up changes are limited to this matrix and the Patch 04A.2 report; no
tested product, geometry, UI, or test code changed.
