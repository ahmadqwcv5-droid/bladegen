# Sprint 04B acceptance matrix

| Requirement | Evidence | Result |
| --- | --- | --- |
| Discoverable bulk input | Import Distributions beside distribution controls | PASS |
| Real CSV file upload | Playwright `setInputFiles` with 40-row CSV | PASS |
| Ordinary spreadsheet paste | Browser clipboard permission, write, focus, Control+V | PASS |
| Review before mutation | Source/rows/mapping/units/interpolation/domain/counts/preview; Cancel verified | PASS |
| Exact supplied header contract | `row,r_over_R,chord_mm,twist_deg,rake_mm,skew_mm` recognized | PASS |
| Informational `row` handling | Visible as not mapped to BladeSpec | PASS |
| Unknown columns explicit | Candidate rejected until mapped/excluded | PASS |
| Physical/normalized unit conversion | Chord/Rake/Skew radius conversion, Twist degrees, Thickness percent/ratio tests | PASS |
| Diameter snapshot safety | D=400/D=720 conversion tests plus stale-snapshot component test | PASS |
| Partial imports | Unselected curves, dimensions, stations, and assembly preserved | PASS |
| Independent grids | Separate operations retain distinct distribution radii | PASS |
| Precision/sign/scientific notation | Unit and component regressions; focused inputs show exact stored value | PASS |
| Input integrity | Duplicate, missing, nonfinite, decreasing, domain/root/tip errors tested | PASS |
| Explicit sort | Whole rows sorted; values neither changed nor merged | PASS |
| Safety limits | 5,000 distribution rows; 200-row performance/regression exercised | PASS |
| No per-row operations | Complete immutable candidate built locally; no point-callback loop | PASS |
| One engineering transaction | One validate, one preview, zero CAD, one Undo/Redo entry | PASS |
| No-op/cancel/error atomicity | Unit/component coverage retains state/history/artifacts | PASS |
| Exact individual editing | Full precision on focus; add/delete/radius/value workflows retained | PASS |
| Bulk station setup | Uniform 2/3/5/8 and explicit nonuniform tests | PASS |
| Profile assignment review | Existing profile and TE deliberately selected | PASS |
| Apply profile to selected stations | Batch NACA 0012 browser workflow | PASS |
| Thickness coordination explicit | Separate two-point-constant options; partial selection cannot rewrite global Thickness | PASS |
| Distribution/station counts distinct | 40×4 controls retain exactly two airfoil stations and two Thickness controls | PASS |
| Station/profile edit atomic | Stations, profiles, TE, and reviewed Thickness undo together | PASS |
| Canonical evaluator reuse | Prepared evaluator reused in probes, sections, preview, and 5,001 grid | PASS |
| Mathematical semantics unchanged | SciPy/NumPy comparisons at knots, near-knots, endpoints, random/dense locations | PASS |
| Constructor count | Five per five-PCHIP request vs 25,005 legacy dense phase | PASS |
| UI acknowledgement ≤100 ms | Final 20-run median 55.127 ms, p95 71.929 ms, max 75.054 ms | PASS |
| 40-row review ≤500 ms | Parse/candidate p95 0.179 ms | PASS |
| 40-control commit p95 ≤1 s | Validate+preview p95 28.509 ms | PASS |
| 200-control commit p95 ≤2 s | Validate+preview p95 47.175 ms | PASS |
| No CAD in interactive budget | Request count: 1 validate, 1 preview, 0 CAD | PASS |
| Export/open isolated context | Downloaded definition opened in `browser.newContext()` | PASS |
| Explicit generation only | No build on Apply; separate Generate Blade/Propeller clicks | PASS |
| Qualified custom blade | Exact job `25f9c4adf64f45a0b5baf311d3b41040`; 1 solid, valid/closed, 0 free edges | PASS |
| Qualified custom propeller | Exact job `a25f2d23a0db4857b88c85a35618895a`; 1 solid, valid/closed, 0 free edges | PASS |
| STEP round-trip | Blade/propeller volume and bbox deltas within existing gates | PASS |
| Backend non-integration | 149 passed, 11 deselected, 0 failed | PASS |
| Full CAD integration | 11 passed, 149 deselected, 0 failed | PASS |
| Frontend unit/build/lint | 156 tests, production build, Ruff all pass | PASS |
| Cross-sprint browser suite | One run: 12/12 passed, 0 skipped/retried, 25.2 min | PASS |
| Narrow layouts | Existing narrow table and narrow CAD viewer tests passed in consolidated run | PASS |
| Workflow screenshots | Five Sprint 04B evidence PNGs retained | PASS |
| Historical archive isolation | No implementation path targets or modifies `00_research_archive` | PASS |
| X-57 fixture hashes | `fixtures/x57_manual_reference` absent | BLOCKED — INPUT MISSING |
| Real X-57 UI import/export JSON | Exact source rows/profile unavailable; no substitute invented | BLOCKED — INPUT MISSING |
| Real X-57 CAD/failure evidence | Cannot submit a provenance-valid X-57 candidate without fixture | BLOCKED — INPUT MISSING |
| NASA geometry fidelity | Not inferred from synthetic workflow or prior archived data | NOT CLAIMED |
| User hands-on retest | Automation cannot establish subjective editing usability | PENDING USER |

Overall classification: **CONDITIONAL PASS — X-57 fixture qualification
pending**. The reusable product path, mathematical behavior, responsiveness,
generic blade/propeller CAD, and prior regressions pass. A strong final Sprint
04B acceptance requires the named source fixture pack and a provenance-valid
real X-57 UI run.
