# FP-01 managed fixed-plane runtime integration report

## Decision

**FP01_INTEGRATION_PASS.** BladeGen now has a maintained, project-local OpenVSP build flavor that implements `bladegen.fixed-radial-sections.v1`, is loaded through the real Python binding, is selected fail-closed by the adapter/CLI/API, and produces the previously qualified X-57 geometry through the normal production pipeline.

This is a phase-one integration result. It is not an automatic merge, a system-wide runtime replacement, a speed improvement, broad product qualification, or external NASA validation.

## Source and worktree identity

- Application HEAD: `1cdb564a2eb92b0171acbab705b41ca63b57416c`.
- Branch: `integration/fp01-managed-fixed-plane-runtime`.
- Branch creation was recorded by Git at `2026-10-14 23:52:49 +0300`, carrying the existing dirty worktree from `sprint/04b-efficient-engineering-input` without a checkout reset.
- The preserved pre-FP01 tracked set (the two Sprint 04B documents and seven listed frontend files) has canonical `git diff --binary` SHA-256 `d48e56c52997586cc6a17a80afaac89d445c710f9cdb998e615980b5c688b5a6` at closure.
- The preserved pre-FP01 untracked audit/prompts/evidence/fixtures/browser-test/diagnostic scope contains 901 files (2564440645 bytes); its sorted relative-path/SHA-256 manifest has aggregate SHA-256 `48c5ddec3f7d00f32979eb06eb6e64d8aaf5cb44913572a6cc813c610c2c9f06`. Those paths were not edited by FP01.
- Starting and final worktrees are dirty by design. Existing staged, unstaged, and untracked Sprint 04B/X-57 evidence was preserved; no reset, clean, stash, commit, or merge was performed.
- OpenVSP baseline: version 3.54.0, commit `db6c6fe8f4eca27d7517f4ae0b2078abdd3fd927`.
- Source archive: 210326824 bytes, SHA-256 `0b72cf30b68ae5b4845fd61d6cfebfa2033c9ff9188c95e335b86b6cc543c2af`.
- Production patch: `vendor/openvsp_fixed_plane/patches/0001-bladegen-fixed-radial-sections.patch`, SHA-256 `0dd6f87b867ccaeb6518f8f01f7093e4e1a05f02d0c5a268c66cc1d157ed71d3`.
- Managed runtime fingerprint: `af69cfbeb477880fd7caf13c3fbdef3a2f69f40430dafe4e5a330d9bb7836edd`.
- Native `_vsp.so`: SHA-256 `e9c91cd48148ddf7017631770aed019f3fda44c25bba4fa556f58d243472baea`.
- Final FP01 implementation source-set manifest: `docs/FP01_SOURCE_SHA256.txt` (29 path/hash records), SHA-256 `d8888da1a8c478e1fd2152fd3f87c5330ccc2b644637abc68820d760bcaf1ef7`.

The installed `bladegen-runtime-manifest.json` and each run's `engine_manifest.json` contain the exact artifact/source hashes needed to distinguish this engine from legacy or stock OpenVSP. Missing historical metadata remains `legacy/unknown`, never current.

## Native implementation

The maintained patch introduces the compile-time `BLADEGEN_FIXED_RADIAL_SECTIONS` feature. The native derivative-driven angle continues to be calculated. In the dedicated BladeGen flavor, identity is applied at the one actual automatic `mat.rotateZ(m_ZRotate)` operation; with the feature disabled, the upstream rotation remains. Pivots, translations, following transforms, profile preparation, loft, caps, tolerances, and export settings were not altered.

The real compiled SWIG binding exposes:

- `GetBladeGenBuildID()` → `openvsp-3.54.0-bladegen-fixed-plane.1`
- `GetBladeGenConstructionContract()` → `bladegen.fixed-radial-sections.v1`
- `HasBladeGenFixedRadialSectionsV1()` → true

An inherited `BLADEGEN_BYPASS_AUTO_RIB_ROTATION` value has no effect on this build. The fixed-plane behavior applies uniformly to the applicable propeller positioning path; it contains no X-57/model/radius exception.

## Reproducible project-local runtime

`./scripts/setup_openvsp_fixed_plane.sh` checks Linux x86_64, Python 3.12 ABI/SOABI, compiler/build prerequisites, and locked identities before activation. It downloads the exact archive and pinned SWIG package, verifies size/SHA-256, rejects a non-exact patch application, builds Release/headless with Python wrappers, writes an artifact-hashed manifest, runs a fresh native identity probe, and runs a real production geometry smoke test. Only the verified staging payload is atomically activated below `.tooling/openvsp-3.54.0-bladegen-fixed-plane.1/`.

Observed setup history was retained honestly:

1. GNU-patch offset incompatibility during an early method was rejected.
2. A nested-repository `git --no-index` behavior was detected and manually stopped before activation.
3. A compiled staging build was rejected because the verifier expected the wrong native version formatting.
4. A build exposed an outer/inner parallel package-install copy race and was not activated.
5. The corrected clean staged build, native probe, and production geometry smoke passed and activated.

Failure logs/staging evidence remain under ignored `.tooling/fp01-build-failures/` and failed staging paths. A subsequent unchanged invocation verified and reused the installation in 1.96 s (`user 8.88 s`, `sys 0.32 s`). This demonstrates safe idempotent reuse, not cross-toolchain bit-for-bit binary reproducibility.

Environment: Linux x86_64/glibc 2.39; Python 3.12.3/`cpython-312-x86_64-linux-gnu`; GCC 13.3.0; CMake 4.3.4; SWIG 4.2.0. Validation dependencies recorded in run provenance were OCP 7.9.3.1.1, NumPy 2.5.3, and SciPy 1.18.1.

## Runtime selection and product wiring

One runtime manager now serves the adapter, CLI, FastAPI preflight, and isolated worker. The managed flavor is the default. An explicit `OPENVSP_ROOT` must be absolute and must pass manifest, ABI, artifact-hash, compiled identity/capability, Python module path, and native module path checks. An empty, relative, missing, partial, tampered, mixed, stock, or stale root fails without fallback to `/opt`, pip, `/tmp`, or a different installation.

Readiness uses a bounded fresh subprocess so ordinary editing and lightweight validation do not import OpenVSP in the request thread. `bladegen doctor`, `bladegen runtime-info --json`, and `GET /api/runtime` expose readiness independently from input validity. Blade and propeller build routes reject an unavailable engine before a job ID/directory is allocated. The serialized worker pins the selected root/fingerprint and verifies it again; a runtime change while queued produces an explicit failure.

Each run writes `engine_manifest.json` early with separate requested, actually-loaded, rejected/completed states. A successful job additionally requires zero worker exit, fresh required artifacts, completed final validation, and matching worker provenance. The manifest records contract/build/upstream/patch/fingerprint, private paths and hashes, adapter/resolver/validation revisions, dependency versions, canonical input hashes, run/job identity, and effective time limits. It is an allow-listed job artifact.

## Native and regression tests

Real native integration command:

```bash
source scripts/openvsp_env.sh
/usr/bin/time -p .venv/bin/pytest -q -m integration backend/tests
```

Result: `13 passed, 163 deselected, 1 warning in 589.93s`; `/usr/bin/time`: real 591.73 s, user 620.59 s, sys 3.11 s. This covered fresh real binding identity, zero/nonzero rake behavior, preservation of chord/twist/axis/input coordinates, diagnostic-flag invariance, real blade CAD, and supported propeller generation.

Runtime/data unit coverage includes missing/stock/wrong capability or patch, tampered artifact, mixed binding, invalid explicit root, stale readiness, worker mismatch, failed/nonzero/timeout/missing-output cases, and API pre-queue rejection. Fixtures were adjusted only to provide the newly mandatory runtime readiness/provenance contract; geometry assertions were not weakened.

## Fresh X-57 production build

The final qualifying command was a fresh process using the unchanged retained submitted BladeSpec, the managed runtime, the normal CLI pipeline, and accepted AB-02 B only as a comparison reference:

```bash
/usr/bin/time -p timeout --signal=TERM --kill-after=30s 900s env OPENVSP_ROOT="$PWD/.tooling/openvsp-3.54.0-bladegen-fixed-plane.1/opt/OpenVSP" BLADEGEN_EXTERNAL_TIMEOUT_SECONDS=900 BLADEGEN_RUN_ID=fp01-x57-cli-20261014T223728Z .venv/bin/python -m bladegen.cli build docs/evidence/sprint04b/x57/job/submitted_blade_spec.json --output .tooling/fp01-qualification/fp01_20261014T223728Z/x57_cli --reference-step docs/evidence/sprint04b/x57/rotation_ablation/a93b281c_20261014T183843Z/B_rotation_bypassed/candidate_solid.step
```

Result: PASS in 365.16 s wall (`user 366.83 s`, `sys 2.98 s`), within the explicit 900 s bound. The final run followed one provenance-only rerun after correcting canonical submitted-hash recording; the earlier complete PASS was retained separately and is not combined with this result.

Input/provenance:

- Candidate, retained submitted input, and prior failed-job input canonical SHA-256: `44363e7004604e39b0adfc2c098e58d5e0f807ab836ec41c530cf0a0be0f8bb7`.
- Canonical resolved-definition SHA-256: `975a3cbf8a7442328c7183e588deedc759f080b1d721c0b1a65fc126db3cce00`.
- Engine manifest state: `COMPLETED`; requested, loaded, and completed timestamps were `2026-10-14T22:37:36.842209Z`, `22:37:36.912945Z`, and `22:43:40.253936Z`.

Complete internal geometry validation:

- 41 planned/completed/passed stations; 0 failed.
- Root requested/sampled r/R: 0.20238 / 0.207365125.
- Tip requested/sampled r/R: 1.0 / 0.9995014875.
- Maximum chord error: 0.0016667095678002397 mm.
- Maximum twist error: 0.0315259332887301°.
- Maximum reference-axis error: 0.02002123597237823 mm.
- Maximum trailing-edge error: 0.0 mm.
- Control contour RMS/P95/max maxima: 0.005684432627018182 / 0.009408408381038527 / 0.010661897529197004 mm.
- All-station contour RMS/P95/max maxima: 0.010325082523593652 / 0.017384440012382457 / 0.02016533455573772 mm.
- At r/R 0.22302, production contour RMS/P95/max: 0.006287147024449829 / 0.010585729466083374 / 0.012279071171707148 mm.

Final STEP after export/re-import: one solid, one shell, six faces, zero free edges, closed shell, valid BRep; surface area 22170.68049735742 mm²; adaptive volume 46373.243509611435 mm³. Bounding box min was `[-29.250630433616713, 58.277346564874996, -19.579086588854913]` mm and max `[46.40917486979203, 287.82682781045, 43.040468872263425]` mm. Round-trip volume delta was approximately `1.0063e-8` mm³ and maximum bounding-box delta approximately `8.697e-12` mm.

Direct accepted-B comparison used 10,086 surface samples. RMS, P95, maximum, bounding-box, root, tip, and surface-area differences were all 0.0. The new STEP SHA-256 is `e55f3e4ff6c1b8666a0ae8f1d580af8a413e9d484739a7378493f236d5c968b8`; the accepted reference remains 86,046,021 bytes with SHA-256 `87c750ce53dab112f1a02becf7ff5c4c7f49ff9a74caf3dfd3d1e1884b6091c8`. STEP byte identity was not an acceptance condition.

## API wiring smoke

A separate backend used the existing deployment override `BLADEGEN_BUILD_TIMEOUT=900` and port 8765; the product default remains 300 s. `GET /api/runtime` reported the exact managed identity.

- Real blade: `POST /api/build` with `examples/custom_multi_airfoil_finite_te.json`; job `0c23cc7aa9bb44bfa4adf0b1672bcd51`; `succeeded`, client wall 48.505 s / job elapsed 47.6 s; PASS; one valid closed solid, one shell, eight faces, zero free edges; matching `COMPLETED` runtime provenance.
- Propeller: `POST /api/propellers/build` with `examples/propeller_two_blade.json`; job `3946de3d51df40c48dd17919c713acfd`; `succeeded`, client wall 67.53 s / job elapsed 66.4 s; PASS; one valid closed solid, one shell, 20 faces, zero free edges, volume 355402.94843123347 mm³; matching `COMPLETED` runtime provenance.

The exact API log is retained at `.tooling/fp01-qualification/fp01_20261014T223728Z/api_smoke.log`; X-57 output/logs are in the same ignored evidence root.

## Other verification

```text
.venv/bin/pytest -q -m 'not integration' backend/tests
163 passed, 13 deselected, 1 warning in 1.05s

cd frontend && npm test -- --run
26 files, 160 tests passed; duration 17.02s

cd frontend && npm run build
PASS in 333ms; existing >500 kB chunk advisory only

.venv/bin/ruff check <FP01 Python source and tests>
All checks passed!

.venv/bin/ruff check backend scripts
29 existing findings in unrelated diagnostic/benchmark scripts
```

All FP01 shell entrypoints pass `bash -n`. No unrelated Ruff findings were auto-fixed because those files preserve prior diagnostic work outside this task.

## Operations, rollback, and remaining limits

Developers use `./scripts/setup_backend.sh`, or `./scripts/setup_openvsp_fixed_plane.sh` for the runtime alone, then `source scripts/openvsp_env.sh` and `bladegen doctor`. The stock install remains side by side. A VSP3 is not self-sufficient proof of this construction policy because a stock runtime can recompute it; replay requires the recorded BladeSpec, fixed-plane contract/fingerprint, and implementation identities. The final STEP is the frozen shape.

Rollback is explicit: return to the preceding application commit/branch and its documented stock-runtime pairing. This fixed-plane application must not be pointed at stock OpenVSP; it will reject it. Historical outputs are not rewritten.

Remaining limitations are explicit:

- Broader product-wide CAD regression is pending the next phase.
- Full X-57 UI acceptance under the unchanged default 300 s API watchdog is pending; the 900 s CLI qualification is not a speed claim.
- External NASA surface fidelity remains **UNVERIFIED**.
- The prior profile-preparation refinement limitation is unchanged.
- Original failed job `a93b281c29b640afaa6bad698d64a61b` is unchanged.
- Qualification is Linux x86_64/Python 3.12 only; Windows/macOS and desktop packaging are not qualified.

No research archive content, original failed-job artifact, accepted AB-02 evidence, system installation, or upstream repository was modified. No commit, merge, binary publication, issue, or pull request was made.
