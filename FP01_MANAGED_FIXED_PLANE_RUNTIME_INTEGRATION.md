# FP-01 — Managed Fixed-Plane Runtime & Backend Integration

Repository: https://github.com/ahmadqwcv5-droid/bladegen

## Mission and authorization

Implement the FIRST production-integration phase of the successful X57-AB-02 correction.

Move from a disposable diagnostic OpenVSP executable to a reproducibly built, explicitly identified runtime that the EXISTING BladeGen Python adapter, CLI and API worker can actually use.

Production integration code, build scripts and a minimal maintained native patch are now authorized on a dedicated development branch. This is not another root-cause investigation.

This phase does NOT authorize a system-wide runtime replacement, automatic merge, broad CAD redesign, performance rewrite, desktop packaging, or a claim of complete product-wide qualification.

The required outcome is a maintained integration candidate, supported by fresh builds through the normal Python path. Do not deliver only a proposal, a copied /tmp executable, or another diagnostic script.

## 1. Evidence to preserve and reuse

Read X57_AUTO_ROTATION_AB_DECISION.md, its summary, intervention diff, environment identity and manifest.

Established evidence:
- X57-AB-02 applied only the automatic rib-rotation bypass in B.
- Engineering inputs, calculated derivatives/angles and profile preparation were unchanged.
- A2 recovered A.
- B passed the unchanged complete 41-station internal validation and OCP/STEP round-trip.
- The small profile-preparation discrepancy remains documented; its earlier diagnostic refinement target remains unmet.
- The prototype is not deployed. External NASA fidelity remains UNVERIFIED.

Pinned upstream baseline:
- OpenVSP 3.54.0.
- Source commit: db6c6fe8f4eca27d7517f4ae0b2078abdd3fd927.

Recorded application HEAD:
1cdb564a2eb92b0171acbab705b41ca63b57416c, with a dirty worktree.

Accepted diagnostic candidate STEP SHA-256:
87c750ce53dab112f1a02becf7ff5c4c7f49ff9a74caf3dfd3d1e1884b6091c8

Its size was 86,046,021 bytes. Its internal reference results include:
- 41 planned/completed/passed stations; zero failed.
- One closed valid solid, one shell, six faces, zero non-degenerate free edges.
- Largest all-station production contour maximum: approximately 0.020165335 mm.
- Production contour maximum at r/R=0.22302: approximately 0.012279071 mm.
- Adaptive volume: approximately 46373.243509611 mm^3.

These are recorded reference measurements, not values to inject into new reports.

Inspect actual HEAD and preserve all staged, unstaged and untracked user work. Create:

integration/fp01-managed-fixed-plane-runtime

Do not reset, clean, force-checkout, auto-stash, commit or merge. If branch creation conflicts, retain the work and use a safe uniquely named branch. Record the exact starting state and source/diff hashes, not merely an old commit name.

Keep original failed job a93b281c29b640afaa6bad698d64a61b and all diagnostic evidence immutable. Do not modify 00_research_archive.

## 2. Inspect existing integration points

Review the actual workspace versions of:
- backend/bladegen/adapters/openvsp_adapter.py, especially _load_openvsp.
- backend/bladegen/pipeline.py and propeller_pipeline.py.
- backend/bladegen/cli.py.
- backend/api/services/jobs.py and blade/propeller build routes.
- scripts/setup_openvsp.sh, openvsp_env.sh, start_backend.sh and test launchers.
- Geometry conventions, validation policy, runtime configuration and artifact schemas.

The recorded loader first attempted an import and only then consulted OPENVSP_ROOT. The recorded shell environment also searched stock and temporary installations. Correct runtime selection must cover BOTH paths, not just change one launcher.

The published source may differ from the preserved local worktree. Inspect before editing; do not assume the recorded implementation is still exact.

## 3. Fixed product contract, not an X-57 exception

Document the versioned construction contract, with a proposed identifier:

bladegen.fixed-radial-sections.v1

For the reference blade's local engineering frame:
- Radial location is Y = R * r/R.
- The requested section lies in the corresponding fixed-Y plane.
- Chord, Twist, Rake, Skew, thickness, TE and reference-axis meanings remain those of the existing BladeSpec contract.
- Rake changes the specified axial placement; its derivative must not introduce an additional unrequested automatic rib-plane tilt.
- Subsequent whole-blade placement/assembly transforms remain unchanged.

Preserve BladeSpec v0.2 and PropellerSpec v0.1 engineering fields. Do not add a user-facing switch named after m_ZRotate or OpenVSP internals. This phase supports the existing fixed-plane contract, not a second native-plane design mode.

Record a new runtime/adapter implementation revision because old builds of the same JSON can differ. Do not rewrite old JSON or old results and pretend they were generated with the corrected runtime.

This is a BladeGen/backend semantic correction, not a claim that upstream OpenVSP's default behavior is wrong for every application.

## 4. Production native patch: small and deterministic

For this first integration, implement a DEDICATED fixed-plane build flavor, preferably through an explicit compile-time feature. A proposed build identity is:

openvsp-3.54.0-bladegen-fixed-plane.1

Names here are NEW project-defined identifiers, not claims that upstream provides these features.

The patch must reproduce the proven intervention at the actual automatic rotation application only:
- Continue calculating the native derivative-driven angle.
- In the fixed-plane flavor, apply identity/zero rotation at that operation.
- Preserve pivots, paired translations, other rotations and all following operations.
- Apply uniformly to the applicable propeller positioning paths, not to named models or selected radii.

Do not copy the diagnostic probe machinery into production. Remove the dependency on BLADEGEN_BYPASS_AUTO_RIB_ROTATION and other experimental environment flags. An inherited diagnostic flag must not change this build's geometry.

The compile-time feature OFF must retain upstream behavior in the source patch. The separate BladeGen flavor is built ON and clearly identifies itself; it does not masquerade as the unmodified upstream distribution.

Keep the native diff to the proven operation, feature definition, and minimal capability/build identification needed for integration. Do not change profile fitting, derivatives, rib selection/merging, caps, loft, tolerances, export options or the near-tip treatment.

Add a small read-only native capability/build query exposed through the REAL Python binding. A proposed capability is fixed_radial_sections_v1. Implement and document the new query; do not assume it already exists.

Capability evidence must originate from compiled native code, not just a Python constant or a hand-written manifest. Add a real geometry behavior smoke test as a separate check; a version string alone does not qualify geometry.

## 5. Reproducible source build and installation

Use a clean pinned upstream checkout, pinned submodule/dependency revisions where applicable, and the minimal reviewed production patch. Do not package the dirty diagnostic source tree.

Store a small lock/patch set in the repository, for example:

vendor/openvsp_fixed_plane/
    upstream.lock.json
    patches/
    README.md

Generated source/build/install trees belong in ignored, versioned directories, for example:

.tooling/openvsp-3.54.0-bladegen-fixed-plane.1/

Retain the stock installation side by side. Never overwrite /opt/OpenVSP, the previous .tooling runtime, or system packages.

Provide one documented setup entrypoint, adapting existing conventions where appropriate. It must:
- Check platform, compiler, Python ABI and prerequisites before modifying anything.
- Fetch exact locked sources and verify identities/checksums.
- Fail on patch mismatch; no fuzzy application or automatic upstream upgrade.
- Build Release/headless with the Python API wrappers REQUIRED by the real adapter.
- Install the native module, Python support modules and required runtime libraries coherently.
- Run import/capability and basic geometry checks from a fresh process.
- Use a staging directory; activate the install only after successful checks.
- Be idempotent and detect a partial/stale installation by manifest and hashes, not just directory existence.
- Record compiler, toolchain, dependencies, build options, source/patch hashes and artifact hashes.

The existing prototype's wrapper-disabled vspscript build is NOT an acceptable replacement for the Python runtime. Do not rewrite the adapter to drive vspscript merely to avoid building compatible bindings.

A dependency failure must leave the previous install untouched and return actionable diagnostics. No automatic sudo, global package upgrades or arbitrary deletion of directories. Declare finite build limits; preserve logs on failure.

Target the currently used Linux environment first. Do not claim Windows/macOS or desktop packaging qualification. Preserve required upstream/dependency notices and document that this is a modified distribution; do not invent an upstream endorsement.

Demonstrate a clean staging build/install that does not rely on /tmp diagnostic binaries or source trees. A subsequent unchanged setup run should safely reuse the verified install. Do not claim bit-for-bit reproducible binaries across toolchains unless actually tested.

## 6. Explicit runtime selection and rejection of incompatible engines

Use one shared runtime-selection policy for the adapter, CLI and API workers. Reuse OPENVSP_ROOT or introduce one clearly documented equivalent; do not create conflicting environment variables with different precedence in each entrypoint.

An explicitly selected root must be honored and validated. If it is invalid, do not silently fall back to another installation.

The managed default resolves to the qualified BladeGen flavor. Remove automatic fallback to stock /opt, temporary probes, or whichever pip-installed openvsp happens to import first for fixed-plane production generation.

Verify the actual imported Python module AND native extension/library paths, hashes, capability and build identity. Fail on mixed Python/native packages or unsupported ABI. Do not try to replace an already imported native module in the same process; request a fresh worker/restart.

Configuration discovery and basic input editing should not import heavyweight OpenVSP into the FastAPI request thread. Perform native readiness checks in a bounded fresh subprocess. Cache readiness only against an immutable runtime fingerprint/configuration and recheck the identity in every CAD worker.

Reject missing, stock, incompatible or changed runtimes before starting a new geometry build. API generation should fail clearly before queueing when readiness is known invalid; the worker must independently enforce the same policy. Runtime changes while a job waits must cause an explicit mismatch/retry requirement, not silent use of another engine.

Preserve the serialized CAD worker. No process-global geometry flag may leak between jobs. Unit/data-only tests must remain runnable without a native installation; mocks are permitted there, but native qualification must use the real runtime.

Do not disable editing, project save/open or lightweight input validation merely because the generation runtime is unavailable. Expose generation readiness separately from input validity.

## 7. Integrate into the existing Python/CLI/API path

Keep:

BladeSpec -> canonical resolver -> production OpenVSP adapter
-> existing OCP finalization -> existing final-STEP validation

Do not call diagnostic runners, read prepared success files, or copy the accepted candidate STEP into a new output directory and label that generation.

Preserve current CLI build/build-propeller commands and their API worker entrypoints. Add a small command such as:

bladegen runtime-info --json
bladegen doctor

These names are proposals; use the existing CLI organization. The command must report actual selected native identity/capability and return nonzero when generation readiness fails.

Add a small read-only runtime-status API response if needed. No major frontend work is requested. Existing UI/API error presentation should explain a missing compatible runtime and point to the documented setup procedure.

No automatic CAD regeneration at startup, import, runtime-status polling or settings changes.

## 8. Per-run provenance and honest historical behavior

Write an additive engine_manifest.json for every new build attempt as early as practical. Distinguish REQUESTED and ACTUALLY LOADED runtime identity; an attempted manifest must not imply success.

Record at least:
- Manifest schema and fixed-plane contract ID.
- Runtime/build ID, upstream commit and minimal patch hash.
- Actual Python/native paths and binary hashes in private/local evidence.
- Native capability and effective construction policy.
- Adapter/resolver/validation implementation identity.
- Relevant Python, OpenVSP, OCP, NumPy and SciPy versions.
- Canonical submitted/resolved-definition hashes with documented serialization.
- Job/run identity and effective execution time limits.

Use stable identity fields for any existing result/cache fingerprint. A runtime change is not the same result just because BladeSpec JSON matches. Do not implement a large new caching system in this phase.

Expose safe identity fields through API/results and allow-list engine_manifest.json as an artifact. Do not dump secrets or the entire environment. Bind the new manifest and downloads to the correct job.

Missing metadata on legacy results means legacy/unknown engine, not the current fixed-plane engine. Preserve historical artifacts and statuses, including the original failed X-57 job. Same engineering JSON can be opened unchanged, but regeneration uses the explicitly recorded current contract/runtime.

Document that a saved VSP3 is not self-sufficient evidence of the fixed-plane behavior: opening/updating it in a stock runtime may recompute different geometry. Include replay requirements with the model/artifacts; STEP is the frozen generated shape. Do not claim an upstream viewer enforces custom runtime semantics.

Provide rollback instructions for the previous application/runtime pair without rewriting history. The new fixed-plane application must not silently accept a stock runtime as its fallback.

## 9. Process completion must be unambiguous

Use the real Python binding path; do not inherit the diagnostic void-main vspscript exit-code workaround.

A worker success requires:
- A clean successful process exit.
- Expected fresh artifacts belonging to this invocation.
- Completed existing geometry/round-trip acceptance.
- Matching actually loaded runtime metadata.

Test native import failure, API exception/error, runtime mismatch, timeout and missing/partial output. None may become success because an older STEP or completion marker exists.

Keep any failure artifacts identified as incomplete. Do not globally ignore nonzero statuses or convert arbitrary native host codes to success.

## 10. Focused tests required for this FIRST phase

A. Build/runtime tests:
- Fresh managed build/import, capability and actual module paths.
- Idempotent reinstall/check; no diagnostic-directory dependency.
- Missing runtime, stock runtime, wrong patch/capability, tampered artifact, mixed bindings and invalid explicit root.
- Stale readiness invalidation and worker-side mismatch rejection.
- Inherited diagnostic rotation flag cannot alter behavior.

B. Small semantic smoke tests:
- Zero-Rake-slope control.
- A nonzero-Rake-slope blade that actually exercises the corrected positioning.
- Verify fixed-plane behavior from generated geometry/known transforms, not just capability text.
- Preserve Chord, Twist, axis placement and input coordinates.

These qualify integration behavior, not every possible design.

C. Fresh X-57 build through the installed PRODUCTION Python pipeline:
- Use the actual unchanged exported/submitted BladeSpec retained from the UI workflow.
- Start a fresh CLI process with the managed runtime explicitly selected.
- Build from the JSON; no saved diagnostic model/STEP as a generation shortcut.
- Run unchanged solidification, STEP round-trip and ALL 41 production stations.
- Compare results with accepted AB-02 B and retain the newly generated artifacts.
- Use direct selected-contour comparisons under the established diagnostic repeatability policy where available. Do not assume STEP byte hashes must match.
- Report every original gate and exact endpoint samples; do not substitute three-station success for full validation.

D. API wiring smoke:
- Run one small real blade build and one existing supported propeller example via the normal API/job worker.
- Verify exact job IDs, actual runtime provenance, fresh artifacts and completed validation.
- Test that unavailable/incompatible runtime is rejected before a new CAD job is queued.

E. Run existing non-CAD backend tests, frontend tests/build and Ruff to detect integration regressions. Do not weaken them. Record any adjusted fixtures/assertions and why, especially newly required metadata/readiness checks.

A broad new slope/airfoil/rotation design matrix and a complete cross-sprint browser campaign belong to the next qualification phase. Do not claim they passed in this phase merely because older reports did.

## 11. Time budget: allow qualification, do not pretend performance is fixed

AB-02 validation alone took about 295 seconds, while the existing API whole-job default is 300 seconds. This task is NOT an extraction-speed optimization.

For the fresh X-57 CLI acceptance, use an explicitly recorded external 900-second bound around the normal CLI pipeline. The recorded CLI path is not the API whole-job watchdog; inspect the actual code before running.

If an API-based integration run requires more time, use the existing deployment configuration BLADEGEN_BUILD_TIMEOUT=900 in a separately launched qualification instance. Keep the default 300-second value unchanged and record that override in its run evidence. Do not add a special exception for the X-57 name, file or diameter.

An outer timeout does not override an inner 300-second watchdog. Configure the actual active supervisor explicitly instead of editing a running job or removing validation.

Use native-aware process supervision, finite limits and preserved logs. If it still times out, report it; do not repeatedly escalate limits or remove work to force success.

This phase may pass runtime integration using the documented qualification budget while default-budget X-57 usability remains NOT QUALIFIED. Never label the extended-budget result a speed improvement or completed default-UI acceptance.

## 12. Deliverables, success gate and handoff

Suggested small modules/files (adapt to repository conventions):

vendor/openvsp_fixed_plane/
scripts/setup_openvsp_fixed_plane.sh
backend/bladegen/runtime/
docs/FIXED_PLANE_RUNTIME.md
docs/FP01_INTEGRATION_REPORT.md
docs/FP01_ACCEPTANCE_MATRIX.md

Update existing setup/launch documentation so a new developer follows the managed-runtime path. Do not leave the old official-only setup message as the recommended way to build fixed-plane CAD.

Deliver:
- Minimal clean upstream patch and source/dependency/build lock.
- Reproducible setup commands and versioned installed-runtime manifest.
- Runtime resolver, native identity checks, CLI/API integration and tests.
- Per-job provenance and explicit stock-runtime rejection evidence.
- New X-57 full validation/STEP and one small blade/propeller API result.
- Exact final source identity, commands, counts, deselections, durations and retries.
- Rollback instructions and known limitations.

Large binaries/CAD may remain in documented ignored artifact locations with hashes rather than being committed into source. Code, patch and instructions must suffice to rebuild; a /tmp binary does not.

FP01_INTEGRATION_PASS requires reproducible installation, real Python loading, effective fixed-plane behavior, fail-closed runtime selection, new X-57 41/41 acceptance, coherent run metadata and successful small API wiring builds.

If a required gate fails, report INCOMPLETE or FAIL with the precise blocker. Do not replace it with the old diagnostic PASS.

Even a successful phase-one report must state separately:
- Broader product-wide CAD regression: pending next phase unless actually executed.
- Default-budget full X-57 UI acceptance: pending if only an extended budget was used.
- External NASA surface fidelity: UNVERIFIED.
- Profile-preparation refinement limitation: unchanged.
- Original failed job: unchanged.

Do not merge automatically, publish binaries externally, file upstream issues/PRs, or silently activate a system-wide runtime. Project-local installation, development-branch integration and explicitly configured test workers ARE authorized now.

## Final instruction

Implement this first integration phase now, not another observation-only report.

Keep the existing React/FastAPI application and independent Python engineering core. Build a maintained fixed-plane native runtime with real Python bindings, wire it into the normal product pipeline, and prove that this path generates the qualified geometry.

The user must not need to edit native source, remember a hidden diagnostic flag, re-enter the X-57 data, or depend on a disposable executable. The result must be an identifiable, rebuildable integration candidate whose capabilities and remaining qualification limits are explicit.
