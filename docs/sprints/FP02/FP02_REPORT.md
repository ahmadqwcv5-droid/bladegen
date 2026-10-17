# FP-02 Level 1 qualification report

## Decision

**Verdict: `FP02_BLOCKED`. The candidate is not ready for the user's formal Level 1 trial.**

The named `level1-trial` execution profile is operational on the tested Linux environment and gives every design a 900-second worker budget. Both real browser workflows passed, including a complete 41-station X-57 blade in 369.7 seconds. However, the frozen eight-case matrix did not meet its mandatory 8/8 gate: Q02 and Q03 failed unchanged geometry acceptance at two sections, and Q04 was rejected before CAD because its frozen thickness distribution conflicts with the imported profile's measured thickness. The honest matrix result is 5 PASS, 2 FAIL, 1 REJECTED.

No native geometry code, fixed-plane patch, tolerance, station plan, cap/export setting, or immutable X-57 fixture was changed. The failed cases were not tuned after execution.

`user_hands_on_acceptance = PENDING`

## Tested candidate and environment

- Branch: `qualification/fp02-level1-user-trial`
- Base HEAD: `39ffb7229c834d9c1e19eab03b529a83f1e366a3`
- Worktree: deliberately dirty and uncommitted; this is not a clean tested commit.
- Final browser source capture: base HEAD above, tracked binary patch SHA-256 `ec1acb7cbcf9be50149e91d93dadd994d736a600cd8d2b70c0b709778837aed8`.
- Final worktree after all 15 browser tests: tracked binary patch SHA-256 `ca1426766fcbcb1f644235e0274ecd2bcbae0bd5f66b3278b7693edcd49f0812`; exact status is retained in `qualification/fp02/evidence/verification/final_git_status.txt`.
- Final X-57 test source SHA-256: `5cc575dbfd749837551192aef6adc62fbee32aed5354ea666484e3f366bd3620`.
- Production source-set schema: `bladegen.production-core-source-set.v1`; aggregate SHA-256 `0027501806ebcf39e9dc60914ae18d468f9b5cc82268369a5a22985af8f8f0e3`.
- Managed build: `openvsp-3.54.0-bladegen-fixed-plane.1`.
- Construction contract: `bladegen.fixed-radial-sections.v1`.
- Runtime fingerprint: `af69cfbeb477880fd7caf13c3fbdef3a2f69f40430dafe4e5a330d9bb7836edd`.
- Pinned upstream commit: `db6c6fe8f4eca27d7517f4ae0b2078abdd3fd927`.
- Native patch SHA-256: `0dd6f87b867ccaeb6518f8f01f7093e4e1a05f02d0c5a268c66cc1d157ed71d3`.
- Python 3.12.3; OCP 7.9.3.1; NumPy 2.5.3; SciPy 1.18.1.

The final U2 evidence contains the complete pre-reporting `git status --short`, source hashes, submitted/exported/generated definition identities, runtime identity, and artifact hashes. Reporting-only files and ZIP packages were written after executable testing; they do not alter the qualified executable source.

## Work package A — bounded hardening

### A1. Complete implementation identity — implemented and tested

[`identity.py`](../backend/bladegen/runtime/identity.py) defines a sorted, versioned 29-file production source set. It covers models, canonical airfoil and curve preparation, adapter, blade/propeller pipelines, assembly and solidification, runtime/provenance, result verification, section measurement, expected geometry, station plan, policy, and validation dependencies. It records repository-relative file hashes plus one aggregate hash, rejects any missing required file, and excludes generated output, timestamps, absolute paths, tests, caches, and diagnostics. Native runtime identity remains separately bound.

Regression evidence proves that changing an omitted policy/measurement dependency changes the aggregate and that removing a required file raises an identity error.

### A2. Strong completed-result verification — implemented and tested

[`result_verification.py`](../backend/api/services/result_verification.py) now runs at the worker boundary before a NEW job becomes `succeeded`. It requires:

- zero child exit and fresh, nonempty artifacts from this attempt;
- supported, parseable report/provenance structures with literal successful status;
- exact build type, job/run, canonical submitted definition, normalized model, runtime, contract, timeout, and implementation identities;
- nonempty, count-consistent completed section records and every applicable existing acceptance flag;
- passing topology and STEP round-trip;
- for propellers, the reference blade plus placement, overlaps, collisions, fusion, hub, bore, final topology, and round-trip evidence.

The verifier rejects truthy strings, nonfinite values, missing flags, vacuous station arrays, stale artifacts, FAIL reports, wrong job/spec/runtime, and a passing blade nested inside a failed assembly. A failed new job cannot relabel an older successful preview.

Definition identity is centralized in [`definitions.py`](../backend/bladegen/runtime/definitions.py). Propellers bind both the overall PropellerSpec and embedded reference BladeSpec. Current reports use additive `bladegen.completion-context.v1`; legacy results are not relabeled.

### A3. One effective timeout — implemented and tested

[`execution.py`](../backend/bladegen/runtime/execution.py) resolves one positive finite timeout. Constructor/configuration override takes precedence, then `BLADEGEN_BUILD_TIMEOUT`, then the unchanged 300-second default. The selected value is snapshotted for the attempt and passed consistently to the supervisor, child environment, completion context, and manifest. Queue wait and worker execution durations are separate API fields.

The `level1-trial` launcher selects 900 seconds for all designs, runs the managed-runtime doctor, prints addresses, and stops only its owned backend/frontend processes.

## Frozen matrix result

The authoritative machine result is [`matrix_results.json`](../qualification/fp02/evidence/matrix/fp02_20261015T072300Z/matrix_results.json). Detailed rows are in [`FP02_ACCEPTANCE_MATRIX.md`](FP02_ACCEPTANCE_MATRIX.md).

- PASS: Q01, Q05, Q06, Q07, Q08.
- FAIL: Q02 and Q03. Both completed all 11 planned stations and produced a valid closed solid, but existing contour RMS/P95 and trailing-edge gates failed at requested/sampled `r/R = 0.30` and `0.35`.
- REJECTED: Q04. No job was queued because thickness `0.150000` at `r/R = 0.18` conflicts with imported-profile geometric thickness `0.130553`.

Q02's worst failing values were contour RMS 0.116576 mm, P95 0.197971 mm, maximum 0.199864 mm, and TE absolute error 0.047620 mm. Q03 produced materially the same localized failure: RMS 0.116597 mm, P95 0.197961 mm, maximum 0.199834 mm, and TE error 0.047620 mm. These are measured geometry failures, not topology failures: both retained STEPs contain one solid, one closed shell, zero free edges, and valid BRep topology.

## Browser workflows

### U1 — PASS

Final consolidated evidence ID: `fp02_20261015T055954Z`.

- Q01 authored using visible controls and ordinary CSV input; no application-state injection.
- Initial job `45f79b86e57e410f9af8e19c37bf8daf`: PASS, 5/5 stations, worker 7.2 s, click-to-terminal 8.03 s.
- Export/save and open in a new isolated browser context: complete definition equivalent.
- Frozen edit at `r/R = 0.625`: Twist 18° to 21°; UI identified old CAD as previous/stale and did not auto-build.
- Regeneration job `1dc14de8d0424afea21772247dceb806`: PASS, worker 8.9 s; measured Twist changed from 18.000000000002° to 21.000000000004°, delta 3.000000000002°.
- Q06 UI propeller job `654cecad2ec3430686470ae66d62e4c3`: PASS, worker 97.3 s; two requested/two placed blades and valid final solid.

### U2 — PASS

- Actual `x57_hlp_airfoil.csv` and 40-row `x57_hlp_control_points_mm.csv` entered through the UI; no prepared BladeSpec was injected.
- Fixture checksums passed.
- Exported, submitted, and generated definitions are equivalent at SHA-256 `775e7bd571c815ea88aa8086208f50eb4663375d5953414178f7e753d5425d10`.
- Input fidelity: 282/282 airfoil coordinate pairs exact; all 40 physical-radius and converted values exact for Chord/Twist/Rake/Skew within floating representation; documented source/product thickness difference only (`0.1305067268` versus `0.1305533777`, delta 0.0046651 percentage points).
- Apply did not build CAD. Cold Apply-to-current-preview was 535.2 ms; 20 warm operations had median 546.15 ms, P95 600.225 ms, maximum 604.5 ms. Each Apply issued exactly one validation, one preview, and zero build requests.
- X-57 job `fe7aa0576c894a84a3b2f196d7c4a09d`: PASS, worker 369.7 s, 41/41 stations.
- Re-imported STEP: one solid, one shell, six faces, zero free edges, closed shell, valid BRep, volume 46373.243509611435 mm³.
- Round-trip: volume delta `1.0063e-8` mm³; bounding-box maximum absolute delta `8.6970e-12` mm.
- STEP SHA-256: `06469e570930ddf41442b9a9d5b98ec9fd2f7ef5fee633676a3b219857604efd`.
- External NASA surface fidelity: **UNVERIFIED**. Internal input fidelity and CAD validation are not an external NASA geometry comparison.

## Verification record

| Check | Exact result |
|---|---|
| Complete backend suite | `BLADEGEN_BUILD_TIMEOUT=900 .venv/bin/python -m pytest -q backend/tests` → 190 passed, 1 warning, 0 skipped, 693.29 s |
| Focused FP02 hardening | `.venv/bin/python -m pytest -q backend/tests/test_fp02_hardening.py` → 14 passed in 2.56 s |
| Frontend unit suite | `npm test` → 26 files, 160 tests passed in 20.29 s |
| Frontend production build | `npm run build` → PASS; 48 modules; only the existing >500 kB chunk warning |
| Ruff lint, modified Python scope | PASS: `All checks passed!` |
| Ruff format check | Non-mutating check reports 3 files would be reformatted: `jobs.py`, `result_verification.py`, `test_fp02_hardening.py` |
| Shell syntax | `bash -n scripts/start_level1_trial.sh scripts/start_backend.sh scripts/openvsp_env.sh` → PASS |
| Actual trial launcher smoke | PASS — runtime READY; backend 8012 and frontend 5175 started; bounded TERM invoked the owned-process cleanup and both ports closed |
| Consolidated Playwright collection | 15 tests in 14 files |
| First final Playwright attempt | 14 passed, 1 failed, 0 skipped/retries in 40.4 min; failure was `spawnSync git ENOBUFS` after the binary evidence patch exceeded 20 MiB; trace/video/screenshot preserved |
| Corrected final Playwright | 15 passed, 0 failed, 0 skipped, 0 retries in 36.1 min (`real 2165.12 s`) |

The only post-failure harness change raised the evidence-capture buffer from 20 to 64 MiB. It continued hashing the complete binary Git patch and changed no product assertion or CAD behavior. The full 15-test suite was rerun after that change.

## Handoff artifacts

- Launcher: [`scripts/start_level1_trial.sh`](../scripts/start_level1_trial.sh)
- Arabic checklist: [`LEVEL1_USER_TRIAL_AR.md`](LEVEL1_USER_TRIAL_AR.md)
- Trial inputs: `qualification/fp02/trial_inputs/`
- Trial-input ZIP: `qualification/fp02/FP02_LEVEL1_TRIAL_INPUTS.zip`
- Final browser-generated X-57 STEP: `qualification/fp02/x57_hlp_internal_validation_pass.step`
- Compact evidence ZIP: `qualification/fp02/FP02_EVIDENCE_COMPACT.zip`
- Final browser evidence: `qualification/fp02/evidence/browser/fp02_20261015T055954Z/`
- Frozen matrix evidence: `qualification/fp02/evidence/matrix/fp02_20261015T072300Z/`
- Preserved first-failure trace: `qualification/fp02/evidence/browser/fp02_20261015T051720Z/failure_artifacts/`

The final STEP is separately labelled as an **internal validation PASS**, not NASA fidelity and not an overall FP02 release.

## Narrow next action

Do not release this candidate as `FP02_READY_FOR_USER_TRIAL`. Open a bounded geometry/fixture decision for the three frozen blockers:

1. Reproduce and explain the localized Q02/Q03 finite-TE/intermediate-section contour and TE failures without broadening tolerances or changing unrelated inputs.
2. Decide whether Q04's frozen 0.150000 thickness control or imported-coordinate geometric thickness 0.130553 is the intended authoritative input. Any corrected Q04 definition is a new frozen candidate, not a relabelled PASS.
3. After an authorized correction, rerun the affected cases and then the complete unchanged consolidated suite. Only an 8/8 matrix plus the already demonstrated workflow gates can yield `FP02_READY_FOR_USER_TRIAL`.

No further optimization, native patch change, release, commit, merge, or publication was performed.
