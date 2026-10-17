# FP-02 — Bounded Level 1 Qualification and User-Trial Handoff

Repository: https://github.com/ahmadqwcv5-droid/bladegen

## 0. Mission and completion boundary

Implement and execute FP-02. Deliver a usable Level 1 trial candidate, not another open-ended OpenVSP investigation.

Product scope: the engineer supplies blade geometry; BladeGen accepts or imports it, produces verified blade/propeller CAD, saves the project, and supports editing and explicit regeneration. Aerodynamic design, performance prediction, structural certification and manufacturing approval are outside this task.

The fixed-plane correction and FP-01 integration are the accepted foundation. Reuse them. Do not repeat rotation ablations, cap experiments, live-surface localization or native source instrumentation.

This sprint has exactly three work packages:
1. Close the three identified result/provenance hardening gaps.
2. Qualify a frozen matrix of eight representative cases and the real browser workflows below.
3. Provide a verified launch procedure and an Arabic checklist for the user's hands-on trial.

Completion target: `FP02_READY_FOR_USER_TRIAL`, explicitly scoped to the tested Linux/Python environment, the eight-case matrix and a named 900-second trial execution profile. The user's personal acceptance remains pending until they actually use it.

No native geometry changes, new design features, broad refactoring or extraction-speed optimization are authorized. Small application, integration, test, documentation and launch changes necessary for these three packages are authorized. Implement them and continue through testing without requesting approval for each ordinary step.

If a new confirmed geometry defect requires changing the accepted native patch, construction semantics or acceptance tolerances, preserve a reproducible case and report a blocker. Do not turn this sprint into another unrestricted geometry investigation or declare PASS anyway.

## 1. Starting identity, evidence and working-state safety

Last reviewed merged application commit:
`7094a5983777d50da3c5da02169491dc82fe899d` — FP-01, PR #14.

This is a historical anchor, not an instruction to reset the current workspace. Inspect actual HEAD, branch, staged/unstaged/untracked work and runtime identity. Preserve unrelated changes. Create a safe development branch such as `qualification/fp02-level1-user-trial`; do not force-checkout, reset, clean, auto-stash, commit, merge or publish automatically.

Read the actual workspace versions of:
- `docs/FP01_INTEGRATION_REPORT.md`
- `docs/FP01_ACCEPTANCE_MATRIX.md`
- `docs/FIXED_PLANE_RUNTIME.md`
- Runtime manager/provenance, job manager, blade/propeller pipelines, current validation schemas, launchers and browser tests.

Use the independent FP-01 review ZIP/report if present as read-only reproduction evidence. Do not copy its source snapshots over production code. Its absence does not block reproducing the three precisely specified gaps below.

Required existing foundation:
- Build: `openvsp-3.54.0-bladegen-fixed-plane.1`
- Contract: `bladegen.fixed-radial-sections.v1`
- Pinned upstream commit: `db6c6fe8f4eca27d7517f4ae0b2078abdd3fd927`
- Native patch SHA-256: `0dd6f87b867ccaeb6518f8f01f7093e4e1a05f02d0c5a268c66cc1d157ed71d3`

Verify the installed managed runtime through the real Python path. Reuse its verified installation; do not unnecessarily rebuild it or change dependencies. If missing, use the existing supported setup, preserving old installations and logs.

Do not alter `00_research_archive`, original failed job `a93b281c29b640afaa6bad698d64a61b`, historical evidence or immutable X-57 fixtures. Write new runs under new IDs and new evidence paths.

## 2. Work package A — Close three bounded hardening gaps

### A1. Complete implementation identity

The reviewed `implementation_hashes()` covered the adapter, resolver and `geometry_validation.py`, but not all code implementing physical section measurement and acceptance.

Record a deterministic, versioned implementation source set covering at least:
- Models and semantic preparation used by the build.
- Canonical airfoil/curve preparation and adapter.
- Blade and propeller pipelines, assembly and OCP finalization.
- `measure_sections.py`, `expected_geometry.py`, `station_plan.py`, `policy.py` and their production measurement dependencies.
- Result-completion verification and provenance implementation.

A sorted content-hash manifest of the small production core is acceptable; do not build a general dependency-tracing framework. Use repository-relative paths and an aggregate hash. Exclude generated output, timestamps, absolute paths, caches, tests and historical diagnostics from the implementation fingerprint. Native identity remains separately bound by FP-01.

Include required-file presence checks. Document exactly what the source-set identity covers. Add an additive metadata version where necessary; do not relabel legacy results.

Test that changing only a previously omitted measurement/policy file changes the implementation identity, and that missing required files cannot silently yield a valid partial identity. Use temporary test copies, not changes to the real geometry code for this test.

### A2. Stronger completed-result verification

At present, zero child exit plus expected file presence and a completed engine manifest can be accepted without inspecting `validation.json`. Reproduce this at the worker boundary with synthetic artifacts, then close it.

Before a NEW job becomes `succeeded`, require:
- Successful child exit and this attempt's required fresh, nonempty artifacts.
- Parseable supported result/provenance structures with literal successful statuses.
- Correct build type, current job/run identity, submitted-definition identity and loaded runtime fingerprint/contract.
- Completed, nonempty planned section records, consistent counts, and all applicable EXISTING acceptance flags passing.
- Passing topology and existing STEP round-trip results.
- For propellers: the reference-blade checks AND assembly/placement/hub/bore/final topology checks required by the existing contract, not just the nested blade PASS.

Use the actual blade/propeller report structures. Do not invent field names or search recursively for any convenient occurrence of `PASS`. Do not accept a vacuous `all([])`, a truthy string `"false"`, or a required flag missing from an incomplete report. Reject malformed/nonfinite acceptance data rather than interpreting it as successful.

Bind the report to the same submitted definition as the queued job. Distinguish the overall PropellerSpec from its embedded BladeSpec. Reuse a single documented canonicalization; separately label raw-byte hashes and normalized model hashes where needed. Add a small completion context to current reports if necessary, without changing engineering schema fields.

This is lightweight verification of the generated result, NOT a second CAD measurement engine. Reuse production acceptance semantics; do not create looser parallel rules or retroactively impose new geometric tolerances. Numeric diagnostics that the current policy merely reports must not be described as having passed an invented threshold.

Tests must cover zero exit with FAIL, malformed/missing/incomplete JSON, wrong job/spec/runtime, missing required evidence, and a propeller whose blade passes but assembly fails. Current valid blade and propeller results must still succeed. Timeout/nonzero exit must never become success due to old artifacts.

Keep the prior successful preview clearly identified as previous/stale if a new attempt fails. Never present it as the failed attempt's successful result.

### A3. One effective timeout value

The reviewed `JobManager(timeout_seconds=7)` could supervise for 7 seconds while provenance recorded the environment default 300.

Resolve and validate the positive finite timeout once, preserve existing constructor/configuration precedence, and pass the ACTUAL selected value to the worker/provenance. Snapshot it for the attempt; do not recompute it inconsistently from an inherited environment.

Test constructor override, environment configuration, the default and invalid values. Assert supervisor timeout, worker context and manifest agree.

Keep queue waiting separate from the worker execution limit, and label client/queue/worker durations accurately. Do not silently restart a timed-out job or reuse it as a new attempt.

## 3. Work package B — Named trial launch profile, not a speed project

Keep the ordinary application's existing default of 300 seconds unchanged.

Provide a documented project-local `level1-trial` launch profile using the existing `BLADEGEN_BUILD_TIMEOUT=900` configuration for ALL designs launched in that profile. No X-57-name, size or file-specific exception.

The trial launcher must select the verified managed runtime, print the effective profile/timeout and local addresses, and arrange a normal frontend/backend session using existing scripts. One command or two clearly named terminal commands is sufficient. Users must not edit Python/C++, remember hidden diagnostic flags or re-enter environment settings for each design.

Honor explicit configuration consistently; reject invalid configuration rather than silently selecting another runtime. Do not change global shell profiles or system installations.

Verify runtime readiness before inviting the user to generate. Do not unnecessarily disable data editing/save/open when generation is unavailable. A small status/error presentation is allowed; no UI redesign.

Use a fresh qualification backend whose process identity and configuration are recorded. Do not attach tests to an unidentified old server or terminate unrelated processes to claim a port. Stop only processes started by this task unless the user explicitly authorized otherwise.

Browser test timeouts must accommodate the real backend budget and multiple builds in a workflow. An outer browser timeout does not replace an inner backend watchdog. Native timeout handling must terminate the owned worker safely and retain logs.

Record Generate-click to terminal UI status, server queue/worker durations and available stage timings. During long validation show the truthful active stage and elapsed time; no timer-driven fake progress or premature 100% success.

A completed heavy build under 900 seconds qualifies this trial profile. It does NOT prove default-300-second acceptance or a speed improvement. Do not repeatedly increase the limit if a run exceeds it.

## 4. Freeze eight representative geometric cases before CAD results

Write `docs/FP02_PLAN.md` and a machine-readable case manifest before generating qualification geometry. Reuse existing examples and fixtures where possible. New variants are explicit synthetic test definitions, not new NASA source data.

Freeze exact inputs, hashes, intended coverage, expected success and the existing acceptance policy for these EIGHT primary cases:

| ID | Definition/coverage |
|---|---|
| Q01 | Simple three-station NACA blade; zero Rake slope; symmetric profile; zero physical TE; Linear distributions. This is the from-scratch browser case. |
| Q02 | Five-station cambered or mixed-NACA blade; modest measurable positive Rake slope; finite TE; PCHIP. |
| Q03 | Controlled Q02-derived blade with negative Rake slope and signed Skew, leaving unrelated inputs fixed. |
| Q04 | Eight nonuniform stations with existing imported-coordinate profile data and independent distribution grids; explicit thickness handling. |
| Q05 | Unchanged source-derived X-57 case: two imported airfoil stations, 40 controls each for Chord/Twist/Rake/Skew, full existing 41-station validation. This is the dense-data browser case. |
| Q06 | Two-blade propeller using a small known-valid reference blade and a documented valid hub/bore configuration. |
| Q07 | Same supported assembly family with three blades. |
| Q08 | Same supported assembly family with four blades. |

Include Normal rotation. Include Reverse in one non-X-57 case only if already declared supported by the current product; record that choice BEFORE results. Otherwise state that reverse-direction qualification is not added by this sprint. Do not change the supported contract after seeing failures.

For assembly cases, select the known supported hub and root-overlap parameters before execution. Do not assume the X-57 five-blade assembly is supported or invent its hub.

All eight must use the managed runtime and normal product build path, unchanged station planning, geometry tolerances, solidification and round-trip policy. Record each case's ACTUAL planned/completed counts; only Q05 is required to contain exactly 41 measurement stations.

For Q05, verify the existing `fixtures/x57_manual_reference/SHA256SUMS.txt` and retained submitted/exported definition. Do not silently reconstruct missing reference inputs from rounded prose or change their profile coordinates. Locate original files in the workspace first; report a genuine missing input as a blocker, not a synthetic substitute.

Do not compare every new variant with an unrelated old stock-runtime STEP. Judge it against its own requested definition. The accepted fixed-plane X-57 candidate may be used as a separately labelled internal regression reference, never as the generated result or external NASA truth.

Freeze one modest interior Twist edit of Q01 for the edit/rebuild browser workflow. It is a declared perturbation of Q01, not an unbounded ninth design family. Rebuild repetitions and malformed-input tests are likewise not additional matrix families.

Do not drop failed cases, tune source values after failure, or inflate station tolerances. Small supported-path application bugs may be fixed within this sprint with regression tests. A native/semantic geometry change requires a separate decision and must remain a reported blocker here.

## 5. Actual browser acceptance — complete both workflows

Use real Playwright/Chromium with the real backend, managed runtime, OCP and downloadable outputs. Exercise visible controls, ordinary file inputs and normal project actions. Do not inject React state, localStorage or a prepared BladeSpec to bypass the workflow being tested. Read-only API calls are allowed to verify job identity and downloaded evidence.

### Workflow U1 — Simple authoring, save/open, change and regenerate

1. Start a clean browser context and a new project.
2. Configure Q01 through visible controls, using bulk station setup and normal numeric inputs; no curve dragging is required.
3. Validate and explicitly Generate. Record the returned job ID, actual submitted definition, full result and successful viewer/download state.
4. Save/export the project through the UI. Open that downloaded file in a NEW isolated browser context and verify complete definition equivalence.
5. Apply the frozen interior Twist edit. Confirm the previous CAD is labelled stale/previous and no automatic build occurs.
6. Explicitly regenerate. Require a different job ID, correct new definition/provenance and a completed validated STEP. Confirm the measured section change agrees with the intended edit within existing tolerances, not merely that the JSON hash changed.
7. Complete a simple supported propeller build through the UI using Q06 and verify assembly settings and final artifacts. Reuse an already completed case result only when this exact browser-triggered build actually supplies its evidence.

### Workflow U2 — X-57 bulk input to a completed CAD result

1. Use a clean project/context. Enter the original globals, set up two airfoil stations, upload the actual profile with the documented normalization choice, and apply it to both stations.
2. Import the actual 40-row distribution CSV, review units/interpolation/counts and Apply once. Do not add 38 rows or type 160 values manually.
3. Verify that Apply does not start CAD. Export the candidate via the UI and compare its engineering content with the immutable reference definition, accounting only for documented conversions and the already established product thickness representation.
4. Click Generate once; allow the real trial-profile worker to finish. Require all 41 original stations, valid closed solid and round-trip acceptance, and matching completed result/provenance.
5. Download STEP, validation, engine manifest and project through links for THAT job. Verify hashes/identities and that the preview displays that job rather than an older result.

The successful U2 build may count as Q05. Do not perform a redundant heavy CLI build solely to populate the same matrix row. Similar reuse is allowed for other cases when the build, source snapshot, inputs and required evidence genuinely match; list each execution once.

Include focused failure/atomicity regressions using existing tests: malformed import, pending-Apply cancellation, runtime unavailable before queueing, and a failed new job while an older successful result exists. Fault injection is acceptable for these software-state tests only, clearly separated from real CAD acceptance. Wait for delayed operations to settle before asserting no state changes.

No post-generation manual file repair, diagnostic executable or old candidate STEP may satisfy these workflows.

## 6. Final verification on one frozen candidate

After bounded fixes, freeze the executable source, test source, runtime fingerprint, fixtures and configuration used for final acceptance.

Run:
- Existing non-CAD backend tests plus the three hardening regression groups.
- Existing native/CAD suite and the eight-case qualification coverage.
- Frontend tests and production build.
- FP-02/newly modified production-code lint and shell checks.
- One complete consolidated supported cross-sprint Playwright suite including the new workflows.

Inspect test collection and report actual counts; do not copy old 13/163/160 counts or historical browser totals into a new result. Missing native prerequisites or required skipped tests mean incomplete qualification, not a green native run.

Use zero automatic retries for the final browser run. Preserve traces and first failures. Correctly synchronized focused reruns can diagnose/fix a test, but a later consolidated PASS requires rerunning the consolidated suite on the unchanged corrected source. Do not add partial results to claim a single clean run.

Existing unrelated diagnostic Ruff findings are recorded separately. Do not edit historical evidence scripts merely to make an unrelated counter disappear.

Do not rerun every expensive case after a reporting-only prose edit; clearly separate evidence documentation from executed source. Any relevant code/configuration/test change requires rerunning the affected acceptance, and final consolidated browser evidence must match the handoff candidate.

Without permission to commit, record actual HEAD plus tracked/staged diffs and relevant untracked source hashes. Do not label a dirty candidate as a clean tested commit. Do not mix results from changing source/runtime states without identifying and requalifying the affected parts.

## 7. Deliver a trial the user can actually run

Provide:
- `docs/FP02_REPORT.md` and `docs/FP02_ACCEPTANCE_MATRIX.md`.
- The frozen eight-case definitions/manifest and evidence index with exact job IDs, source/runtime identities, counts and durations.
- A minimal tested trial launcher or clearly paired launch commands.
- `docs/LEVEL1_USER_TRIAL_AR.md`: a short Arabic checklist with exact current UI labels, start/stop instructions, tested input-file locations and expected checkpoints.
- A self-contained trial-input folder/ZIP with the simple-case values and exact X-57 CSV fixtures/checksums. Do not rely on inaccessible chat attachments or `/tmp` paths. Copy immutable fixture bytes, not rewritten source data.
- A compact evidence ZIP: reports, manifest, key logs, browser screenshots and metadata. Keep large CAD/traces at explicit durable paths with sizes/hashes; provide the user's final X-57 STEP separately. Do not duplicate the entire diagnostic archive.

The Arabic guide must distinguish:
1. Creating the simple blade and then modifying it.
2. Importing X-57 data in bulk and generating a blade.
3. Creating a supported simple propeller, not a five-blade NASA reproduction.

Explain that the trial uses a 900-second maximum worker budget; show measured times separately. No need for the user to rebuild native source or manage hidden switches between designs. Record verified readiness and how to restart after code/runtime changes.

Do not claim that an automated browser test proves the user's personal satisfaction. Set `user_hands_on_acceptance = PENDING` until they try it.

## 8. Exit rule — stop when the fixed scope is satisfied

`FP02_READY_FOR_USER_TRIAL` requires:
- All three hardening gaps closed with regressions.
- Eight frozen cases passing their existing relevant geometry/assembly gates.
- U1 and U2 completed through real visible UI and real CAD.
- Consolidated required tests passing on the identified candidate.
- Verified launch and complete handoff inputs/instructions.
- No open blocker affecting input fidelity, geometry correctness, truthful success state or completion under the declared trial profile.

If a required condition fails, report `FP02_BLOCKED` or `FP02_INCOMPLETE` with the exact reproduction and narrow remaining task. Do not reclassify a required failure as an optional limitation or issue a release merely to meet the roadmap.

The following are NOT reasons to restart research in this sprint when the existing product gates pass:
- The previously documented small profile-preparation refinement limitation.
- Faster-than-current generation as an aspirational goal.
- External NASA surface fidelity, which remains UNVERIFIED.
- Windows/macOS/desktop packaging, new airfoil families or out-of-scope designs.
- Old unrelated diagnostic lint/style issues.

Preserve the distinction between tested examples and universal design coverage. Report default-300-second X-57 usability as not qualified unless actually tested; the named 900-second profile is the authorized user-trial target.

After success, STOP adding tasks and hand over the candidate. Do not automatically start performance work, new features, another diagnostic sprint, merge/publish, or ask the user to perform the agent's unfinished setup work.

Start the final response with:
- Is the candidate ready for the user's trial, and under which exact profile?
- Which eight cases and two user workflows passed?
- What command(s) should the user run, and which files should they open?
- What is still explicitly unqualified?

Execute now. The goal is a bounded, verified path back to using BladeGen—not another sequence of speculative experiments.
