# FP02-C1 — Close Q02–Q04 and Complete Level 1 Qualification

Repository: https://github.com/ahmadqwcv5-droid/bladegen

## 1. Mission and explicit authority

Continue FP-02 in the existing workspace. Resolve its three recorded blockers,
then complete the already-defined qualification and user-trial handoff in this
same task when the evidence permits.

This is a bounded corrective follow-up, not another general OpenVSP investigation.

You are authorized to:
- Revise the inconsistent Q04 positive-test fixture exactly as specified below.
- Investigate Q02/Q03 using their retained inputs and CAD.
- Implement a small GENERAL Python-side correction in canonical preparation,
  adapter translation or expected/measurement calculations when supported by
  the existing engineering contract and independent evidence.
- Update affected implementation identities, tests, reports and trial packages.
- Continue through fresh CAD and final browser qualification without requesting
  another prompt after each ordinary step.

Do not stop at a hypothesis when a bounded, supported correction can be tested.
Conversely, do not manufacture acceptance by changing what the engineer requested.

Not authorized: changes to the managed native fixed-plane patch/runtime, a new
BladeSpec schema or construction convention, new UI design features, a general
loft rewrite, performance optimization, relaxed tolerances, changed cap/export
settings, or automatic commit/merge/push.

A demonstrated need for a native/contract change is a specific blocker requiring
another decision, not permission to silently expand this task.

## 2. Starting facts and evidence identity

Read the actual workspace copies of:
- docs/FP02_REPORT.md and docs/FP02_ACCEPTANCE_MATRIX.md.
- docs/LEVEL1_USER_TRIAL_AR.md and the frozen FP02 plan/case manifest.
- qualification/fp02/evidence/matrix/fp02_20261015T072300Z/.
- Existing FP02 hardening tests and completion/provenance code.
- The independent FP02 review, if available, as read-only evidence.

The reported matrix is 5 PASS, 2 FAIL, 1 REJECTED. The completed browser workflows
U1/U2 and the 15-test browser run are historical successes, not substitutes for
requalification after a relevant code change.

Q02 job: e6f029a7d0c742e2a425ee4176b40c6d
Q03 job: e20845cd8930418fad31a9dc9f4cba30
Q04: rejected before queueing; no CAD job.

Recorded Q02/Q03 failures, in millimetres:

Case | sampled r/R | Contour RMS | P95      | sampled max | TE absolute error
Q02  | 0.30        | 0.116576    | 0.197971 | 0.199864    | 0.047620
Q02  | 0.35        | 0.100795    | 0.171000 | 0.172756    | 0.042181
Q03  | 0.30        | 0.116597    | 0.197961 | 0.199834    | 0.047620
Q03  | 0.35        | 0.100795    | 0.171000 | 0.172756    | 0.042181

RMS, P95 and TE failed; the sampled-maximum contour gate passed. Both cases
completed 11/11 planned sections and retained valid closed solids. Verify the
full records and flags rather than inferring them from rounded values here.

Q04's first reported conflict is thickness ratio 0.150000 at r/R=0.18 against
imported-coordinate geometric thickness approximately 0.130553.

Recorded managed runtime:
- Build: openvsp-3.54.0-bladegen-fixed-plane.1
- Contract: bladegen.fixed-radial-sections.v1
- Fingerprint: af69cfbeb477880fd7caf13c3fbdef3a2f69f40430dafe4e5a330d9bb7836edd
- Native patch SHA-256:
  0dd6f87b867ccaeb6518f8f01f7093e4e1a05f02d0c5a268c66cc1d157ed71d3

The prior report records base HEAD 39ffb7229c834d9c1e19eab03b529a83f1e366a3
with a dirty worktree. Inspect actual HEAD, branch and source/runtime identities.
Do not reset, clean, auto-stash or switch over existing user changes. Work on a
safe branch such as patch/fp02-c1-thickness-te-qualification, preserving the
current candidate and its unrelated changes.

Locate each case's EXACT frozen JSON, submitted input, generated specification,
resolved data, raw STEP, final STEP and available logs/manifests. Verify hashes
and semantic equivalence using the established canonicalization. Record missing
files honestly. The compact review ZIP did not include the full Q02–Q04 inputs
or Q02/Q03 STEPs; their absence from that ZIP is not evidence they are absent
from the original workspace.

Never reconstruct Q02/Q03 from rounded prose or assume Q06's embedded blade is
identical. Keep originals and all previous results immutable. Write new evidence
under qualification/fp02_c1/<run_id>/ with baseline and corrected outputs separate.

## 3. Q04: the fixture-authority decision is now approved

For this imported-profile qualification case, the imported coordinates are the
authoritative shape. The conflicting 15% thickness control is not an instruction
to rescale the profile.

Create a versioned Q04.R1. This is an explicit positive-fixture correction, NOT
a retroactive PASS for Q04 and NOT a change to real user data.

Requirements:
- Preserve every imported upper/lower coordinate, ordering and profile assignment.
- Preserve eight nonuniform stations, their radii, Reverse direction, reference
  axis, globals, all non-thickness distributions, independent grids and TE inputs.
- Derive compatible thickness values using the existing documented imported-
  profile semantics and full-precision canonical calculation, not rounded 0.13.
- Preserve the original thickness control locations and interpolation when they
  can represent that intent. Verify compatibility at ALL assigned profiles and
  across the supported domain, not only the first rejected root value.
- If every station uses the same profile, first prove that identity, then use
  its same natural ratio at the existing thickness controls. Do not assume
  identical profiles without inspecting the file.
- Do not introduce a thickness override, normalize or rescale coordinates,
  remove stations, merge independent grids or switch Reverse to Normal.

Freeze Q04.R1 and its field-level diff/hash BEFORE running CAD. Allow only
explicit fixture revision metadata and the necessary thickness-value changes.
If unchanged grids and assignments cannot represent the approved coordinate
intent under current semantics, report that exact constraint instead of making
further silent fixture changes.

Retain original Q04 as a negative-input regression: it must still be rejected
with the conflicting field identified and without queueing CAD. List its old
REJECTED outcome separately.

The revised positive matrix is:
Q01, Q02, Q03, Q04.R1, Q05, Q06, Q07, Q08.

It still requires 8/8 positive CAD passes. Q04's negative test is additional and
must not be counted as Q04.R1 CAD acceptance. Reverse/eight-station coverage
remains unverified until Q04.R1 actually builds and passes.

## 4. Q02/Q03: resolve the shared intermediate-section question

Start with retained geometry and inexpensive numerical/source inspection.
Do not rerun cap experiments or automatic-rotation diagnostics.

The independent review identified an EXPLORATORY lead, not a proven cause:
using only Q06's bundled thickness controls, Linear and PCHIP produce different
intermediate ratios, and the PCHIP values are close to Q02's recorded measurements.

For that exploratory Q06 calculation only:
r/R=0.30: Linear 0.135000; PCHIP 0.129375; recorded Q02 measured 0.129407385.
r/R=0.35: Linear 0.127500; PCHIP 0.122578125; recorded Q02 measured 0.122606362.

Those figures do NOT establish Q02's input identity or its correct full contour.
Verify its actual definition first. Do not change Q02/Q03 to Linear to obtain PASS.

### 4A. Establish the intended calculation before changing code

Trace the existing documented semantics, actual code and frozen inputs for:
- Airfoil interpolation between explicit stations and its parameterization.
- Nominal NACA thickness, explicit overrides and the independent Thickness curve.
- Canonical PCHIP versus its resolved backend representation.
- Chord evaluation and conversion between physical TE mm and normalized TE/c.
- The operation/order used to set thickness, and whether it scales camber,
  half-thickness, whole ordinates or another documented quantity.
- How finite TE is applied, interpolated and affected by later scaling.
- Imported-coordinate thickness rules, separately from NACA rules.
- The current expected-contour and TE evaluation used at intermediate planes.

Record this in a short contract/operation table before selecting a correction.
Do not silently invent a new intermediate-TE interpolation law or profile-
scaling convention. Distinguish explicit engineering requirements from
implementation choices and unresolved ambiguity.

A shape that matches the native output is not automatically the right reference.
The engineer's unchanged definition is authoritative. A genuinely undefined
choice that changes engineering intent must be reported as a specific contract
question, not decided by whichever operation produces a smaller residual.

### 4B. Reproduce and compare the same physical sections

For Q02 and Q03, inspect r/R=0.30 and 0.35, a passing explicit airfoil station
(such as 0.40 if confirmed in the plan), and a passing intermediate control
(such as 0.50 if confirmed). Verify the original planner's sampled locations.
Use original inward endpoint policy whenever an endpoint is involved.

First reproduce the old production measurements before editing their source.
Read retained STEP once per pass and cache exact extracted section curves with
STEP hash, plane/frame and extraction settings. Avoid repeated native cuts for
pure sampling/expected-shape experiments.

At these locations save:
- Submitted, canonical and resolved thickness values; effective interpolation.
- Bracketing profiles, interpolation weights, local chord and TE quantities.
- Expected contours before/after each relevant thickness and TE operation.
- Measured contours, thickness and TE from the retained STEP.
- Baseline flags and an independent measurement check.

Use a shared requested coordinate frame and physical plane. No best-fit scaling,
independent normalization or empirical offset compensation.

Compare contours bidirectionally using the existing qualified independent method
or another separately tested method. Do not derive expected shape from the STEP.
Measure TE with the existing physical definition; a generic shortest edge or
arbitrary vertex pair is not automatically TE thickness.

Refine the diagnostic sampling enough to distinguish the observed errors from
sampling uncertainty; keep production sampling and tolerances unchanged.
Label sampled maxima accurately. Save actual contour overlays and TE close-ups,
not only aggregate values or full-blade screenshots.

The explanation must account for BOTH contour and TE errors, and be consistent
with the passing controls and Q03. A correlation with thickness alone is not
sufficient proof.

## 5. Implement a narrow correction when the evidence supports it

This prompt authorizes a contract-preserving Python correction to whichever
side is demonstrated wrong: generation preparation/adapter translation,
expected-profile construction, measurement calculation, or a small combination.
There is no requirement that exactly one error or operation contributes.

Before implementing, record the failing mechanism, implicated function(s),
intended equation/order and predicted effect. Add a small reproducible failing
test that does not merely compare two calls to the same production helper.

For an expected-profile/validator defect:
- Establish correctness from the unchanged input contract with an independent
  calculation or analytically checkable fixture, not by copying native results.
- Preserve the old expected contours/metrics and show why they were incorrect.
- Re-evaluation of old CAD is diagnostic only; old failed jobs stay failed.
- Retain strict independent STEP measurement and every existing acceptance gate.
- Include a deliberately incorrect contour or TE example that the corrected
  validator still rejects. Do not make generator and validator agree by
  weakening both or sharing an untested assumption.

For a generation/adapter defect:
- Preserve Q02/Q03 JSON and requested interpolation exactly.
- Implement the smallest general correction to satisfy the existing semantics.
- Use the current managed fixed-plane runtime; no native patch is authorized.
- Inspect emitted/resolved values to avoid double application of thickness or TE.

For either branch:
- Maintain Chord/Twist/Rake/Skew, reference axis, endpoint policy, original
  validation stations, all control values, numerical thresholds and required
  pass/fail checks. Correcting a proven expected-geometry calculation defect
  is allowed as above; redefining the request to fit output is not.
- No case-name/radius-specific branches, hardcoded compensation factors,
  dropped checks, copied success files or changed input interpolations.
- No insertion of ad hoc design stations to fit the measured failures. If a
  substantially new shape resolver is required, identify that scope explicitly.
- Update implementation/provenance revision and source-set coverage so reports
  identify corrected logic without falsifying the unchanged native identity.
- Adjust affected assertions only for independently justified calculations;
  retain a readable before/after reason for each adjustment.

Test the mechanism with a small set of numerical cases covering the relevant
Linear/PCHIP difference, constant/varying thickness, zero/finite TE, and endpoint
identity. Reuse existing tests; do not create another broad design matrix.

If native modification, a new construction contract or broad resolver redesign
is genuinely necessary, stop that branch with precise evidence and one bounded
proposal. Do not spend the task rebuilding unrelated components.

## 6. Prove the affected fixes before running the long final suite

Generate fresh Q02, Q03 and Q04.R1 using the normal CLI/API product pipeline,
new job/output IDs and the managed runtime under the 900-second trial profile.
No diagnostic executable or post-generation CAD repair may supply acceptance.

Require complete original per-case section plans, final closed-solid topology,
existing round-trip rules and all applicable contour/TE/dimensional/wire checks.
Q02/Q03 originally planned 11 stations each; keep their unchanged plans.
Derive and verify Q04.R1's full plan; do not claim 26 measured stations from
Q04's earlier rejected preflight alone.

Report all stations and exact failures, not just the two previously bad cuts.
Do not tune Q02/Q03 inputs or revise Q04.R1 after seeing its CAD result.

If an affected case still fails, preserve it and address only a demonstrated
small in-scope defect. A remaining blocker must stay a blocker; do not start
an unrelated search or run the entire browser suite repeatedly during diagnosis.

If all affected cases pass, proceed automatically to final qualification.

## 7. Complete the revised FP02 qualification on one final candidate

Freeze executable source, tests, revised case manifest, native fingerprint and
trial configuration. Include staged/unstaged/untracked source identity; do not
pretend a dirty candidate is a clean tested commit.

On that candidate:
- Requalify the eight positive cases Q01/Q02/Q03/Q04.R1/Q05/Q06/Q07/Q08.
- Keep Q04 original as a separately passing rejection regression.
- Run the complete required backend/native suites, including FP02 hardening
  and new intermediate-profile regression tests.
- Run frontend tests/build and modified-scope lint/shell checks.
- Run the full consolidated supported Playwright suite, including U1 and U2,
  with zero automatic retries and no required skips.

Add a focused real-UI open/validate/generate check for original Q02 and corrected
Q04.R1 as needed so new behavior is reached through the normal product interface.
Opening their frozen JSON through the application's actual file input is valid;
injecting React state or fabricating API success is not.

U2 must retain actual X-57 profile/distribution CSV import, candidate comparison,
explicit generation, full 41-station validation and same-job downloads. U1 must
retain save/open in an isolated browser context, the intended Twist edit and
explicit regeneration. Do not rewrite these successes into weaker smoke tests.

A genuine final browser build may also supply its matrix case evidence when
inputs, source, runtime and required checks match. Avoid duplicate heavy builds
solely to populate separate report tables. List executions and reuse explicitly.
Old results from before a relevant correction do not count as fresh final passes.

Retain exact commands/counts/deselections/durations/traces and any first failure.
A focused rerun is not a consolidated PASS. After a relevant synchronization or
code fix, rerun the affected qualification and the final consolidated browser
suite on the corrected frozen candidate. Do not combine partial runs.

Use the existing ./scripts/start_level1_trial.sh. Preserve the 900-second worker
budget for every design and the ordinary 300-second default. Browser supervision
must allow the real worker limit; stop only owned processes and retain partial
logs on timeout. Do not repeatedly increase limits or remove verification work.

No speed target beyond the existing trial acceptance is added here. Unrelated
historical lint findings, external NASA fidelity and the old small profile-
preparation refinement limitation do not reopen this task when required gates pass.

## 8. Reviewable artifacts and honest closure

Deliver:
- FP02_C1_REPORT.md and a machine-readable decision summary.
- Exact original Q02/Q03/Q04 JSON plus Q04.R1, with hashes and field-level diff.
- Retained and corrected Q02/Q03 resolved inputs and measurement records.
- Root-cause/operation comparison, independent checks, section BRePs/CSV and plots.
- Retained failed Q02 STEP and new successful affected-case STEPs at durable
  accessible paths with hashes; include small cuts in the compact ZIP.
- Minimal production/test diff and final implementation/runtime identity.
- Revised matrix manifest and final eight-case results tied to exact runs.
- Final consolidated verification evidence and tested launcher instructions.
- Updated Arabic user guide and trial-input ZIP, package checksums and compact
  evidence ZIP. Provide the final browser-generated X-57 STEP separately.

Do not omit the Q02–Q04 original definitions again. They are small and necessary
for independent review. Large full CAD/traces may be supplied separately, with
omissions explicitly listed; file paths alone do not make them part of a ZIP.

Preserve the original FP02 blocked report and matrix as historical evidence.
Publish a clearly versioned revised matrix with Q04.R1 and link it to the
original rejection. Update current handoff documents only after their claims
are supported. No retroactive success for old jobs or old Q04.

Keep these statuses separate:
- Original FP02 matrix: historical 5 PASS / 2 FAIL / 1 REJECTED.
- Revised positive matrix: actual result for eight cases including Q04.R1.
- Q04 negative-input regression: actual rejection result.
- User hands-on acceptance: PENDING.
- External NASA surface fidelity: UNVERIFIED.
- Default-300-second X-57 operation: unqualified unless separately measured;
  the authorized trial target remains the 900-second profile.

FP02_READY_FOR_USER_TRIAL is permitted only after the revised 8/8 matrix,
required real browser workflows, software/native regressions and usable handoff
all pass on the identified candidate. Otherwise return FP02_BLOCKED or
FP02_INCOMPLETE with the exact remaining case, gate and supported next decision.

Do not automatically commit, merge, push, publish a release or start another
sprint. Preserve the research archive, original failed X-57 job, accepted native
patch and previous evidence.

## Final instruction

Execute now, not planning alone.

Q04's coordinate-authority revision is explicitly approved. Q02/Q03 require
an evidence-backed, input-preserving correction, not a switch to Linear or
larger tolerances. Their shared Thickness/TE hypothesis is a lead to test,
not a conclusion to assume.

Continue from diagnosis to a justified in-scope fix and final qualification
within this task. Do not request another prompt merely because two related
Python calculations need correction.

Start the final response with:
1. What caused Q02/Q03's failures, and what evidence proves the correction?
2. What exactly changed in Q04.R1, and does original Q04 remain rejected?
3. Did the revised eight-case matrix and consolidated browser suite pass?
4. Is the candidate ready for the user's trial, under which command/profile?

The user should receive a working, honestly qualified trial or one precise
remaining blocker—not another generic recommendation to investigate OpenVSP.
