# L1A-01 acceptance matrix

Overall decision: **L1A_BLADE_BASELINE_VERIFIED_AFTER_CLEANUP**. This is a stable single-blade baseline within the tested scope, not a whole-Level-1 or arbitrary-blade claim.

| Requirement | Evidence | Result |
| --- | --- | --- |
| Preserve dirty candidate before moving | Recoverable source-only checkpoint, original 433-entry status, original index/patch/hash inventory; unchanged HEAD on new branch | PASS |
| Move task documents without loss | 68/68 verified plan/map moves, 59/59 archival rehashes; immutable ZIPs intact | PASS |
| Keep historical reports navigable | 24 reversible pointers; 97/97 original relative links resolve locally | PASS |
| Preserve research/evidence/runtime and propeller implementation | Original archive/jobs/evidence/managed runtime untouched; active source roots retained | PASS |
| Exact supplied X-57 definition through visible UI Open JSON and explicit Generate | Final-suite fresh job `1d936f53c0f040b1b14a64267892cf3c`; raw, canonical and resolved identities equal original; 370.2 s worker | PASS |
| Full internal final-STEP validation | 41/41 stations and imported-profile gates; one closed valid solid, round-trip accepted | PASS |
| Same-blade geometry repeatability | All 41 full station records equal; direct STEP 10,086 samples with RMS/P95/max 0.0 mm; volume/area/bbox delta 0 | PASS |
| Established backend tests | First run 196/197, moved-policy path corrected; final complete run **197/197** in 555.54 s | PASS |
| Frontend unit tests/build and active lint/shell/doctor | Final full unit run 160/160; build, Ruff, shell syntax and runtime doctor passed | PASS |
| Complete 17-test cross-sprint browser suite on final harness | First run 15/17 (2 traces), focused correction 2/2; separate final complete run **17/17**, 0 failed/skipped/retries, 2,764,663.619 ms | PASS |
| External NASA surface fidelity | No external geometry comparison in this task | UNVERIFIED |
| User hands-on full-propeller acceptance | Implementation and automated tests preserved; personal assembly acceptance deferred | DEFERRED |

The [full report](L1A_01_REPORT.md) distinguishes first-run failures and the focused rerun from the final consolidated result. Final HEAD remains `39ffb7229c834d9c1e19eab03b529a83f1e366a3` on `maintenance/l1a-01-blade-baseline`, with 141 Git status entries and no staged files. No assertion, tolerance, input control or geometry algorithm was relaxed to obtain acceptance.
