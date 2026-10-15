# X57-LOC-02 — Locate the Geometry Divergence and Test One Justified Correction

Repository: https://github.com/ahmadqwcv5-droid/bladegen

## Mission

Complete a decision-oriented investigation, not another arbitrary parameter trial.

Compare the actual live OpenVSP blade surface with the raw STEP produced from
THAT SAME model state, at the SAME physical section planes. Determine whether
the confirmed contour discrepancy already exists before export or enters the
conversion/export/read path.

If the evidence then identifies a specific mechanism and a small general
correction, you are authorized to test ONE correction in an isolated diagnostic
implementation. Do not modify or integrate production code in this task.

The user should not need to re-enter the design or approve every ordinary
measurement. Execute the measurement and the applicable conditional steps below.
Never force a conclusion when measurement quality or evidence is insufficient.

## 1. Established facts — do not reopen resolved work

Original failed job:
`a93b281c29b640afaa6bad698d64a61b`

Retained final STEP SHA-256:
`43c2cd72bebcd3949e0fe0b210aaac9ccbf6918952743fd109ecb0cac2e401d6`

Retained original raw STEP SHA-256:
`85f798f74f672e4c78f3560e3413fcbdbba0ff7410424a840a5fc4e746d8b07f`

Read the retained validation, contour-isolation, and root-cap A/B reports,
summaries, manifests and diagnostic runners already in the workspace.

Established within their documented scope:
- Input transfer and responsive bulk editing passed.
- Complete internal validation finished all 41 planned stations: seven contour
  failures; chord/twist/axis/TE/wire checks passed.
- Independent measurement confirmed the approximately 0.523791 mm worst sampled
  contour discrepancy at r/R = 0.22302.
- Raw STEP and OCP-final cuts agreed at the tested planes.
- Changing only FLAT_END_CAP to NO_END_CAP had no material contour effect at
  the three tested stations. Do not repeat this cap experiment.
- No live pre-export surface was captured in those investigations.
- The original product job remains FAILED; retained internal validation remains
  FAIL; external NASA surface fidelity remains UNVERIFIED.

Use the ORIGINAL configuration, including FLAT_END_CAP, for the new baseline.
Do not use the open no-cap experimental B as the new reference.

## 2. Preserve identity and run in isolation

Last recorded HEAD: `1cdb564a2eb92b0171acbab705b41ca63b57416c`, with a dirty
worktree. Inspect actual state and source hashes; do not reset, clean, pull,
switch branches, overwrite changes, commit, or merge automatically.

Verify the original evidence hashes and the actual submitted BladeSpec.
Preserve its complete resolved engineering vectors and all accepted adapter
settings. Compare semantic numerical content when serialization formats differ.

Record current HEAD, tracked diff identity, relevant source hashes, and actual
OpenVSP/Python/OCP/NumPy/SciPy versions. Keep the installed runtime fixed.

Use a new evidence directory, for example:
`docs/evidence/sprint04b/x57/live_surface_localization/<run_id>/`

Fresh disposable OpenVSP generation and diagnostic scripts are authorized.
Reuse the real production construction/update/export path via observational
hooks or a minimally changed, hash-identified diagnostic copy. Do not reconstruct
a different blade through an unrelated implementation.

Do not change source profiles, stations, physical TE, thickness intent, reference
axis, distributions, interpolation, cap treatment or export settings in the
baseline. Do not weaken validation or change the production timeout.

## 3. Inspect the actual surface API before measuring

Inspect the installed OpenVSP API and matching-version implementation. Identify
a supported way to evaluate the ACTUAL generated main blade surface in memory.
Record which geometry, surface/patch indices, domains, and transforms it uses.

Do not invent API names, surface meanings, or parameter mappings.

The following are NOT substitutes for a live surface measurement:
- Reading stored airfoil input coordinates or PCurve controls again.
- Calling only a section-definition helper instead of evaluating the generated
  blade surface.
- Reading the newly exported STEP and labelling it pre-export.
- Reloading VSP3 after export and calling it the earlier model state.
- A screenshot, STL, or unconverged visual tessellation.

Establish how the queried main surface relates to surfaces processed by the
exporter. If export uses transformed/copied/converted surfaces, document that
boundary rather than assuming identical indices or parameterizations.

Prefer the runtime's native surface evaluator. If unavailable, a small
read-only, same-version diagnostic probe may expose the surface. It must not
change geometry semantics, and its generated baseline must still reproduce the
retained output. Do not turn this into a broad source build or alternate CAD
backend. Report a specific blocker if reliable access cannot be obtained.

## 4. Capture before and after export in the same live process

In one fresh baseline run:

1. Build and finish the normal production updates with original settings.
2. Record accepted parameters/PCurves/airfoil data and relevant API errors.
3. Capture live surface evidence immediately before raw STEP export: L_before.
4. Export raw STEP using the unchanged production call/settings: T.
5. Without calling Update, reloading, or setting parameters, evaluate the same
   live surface and sentinel parameter locations again: L_after.
6. Record any changed parameters, surface domains/counts, sentinel coordinates,
   errors, and actual calls that occurred during capture/export.

Keep a durable record of L_before points before export; retaining only a live
object reference that could be mutated is insufficient.

For new raw STEP, reproduce the retained three-station geometry using the prior
independent direct-contour comparison and production metrics. Use the previous
0.0001 mm diagnostic repeatability target; do not relax it after seeing data.
New STEP hashes may differ due to metadata, so use geometry as well as hashes.
If baseline reproduction fails, repair instrumentation or identify the mismatch
before attributing the original defect to a stage.

Do not assume export is non-mutating: explicitly compare L_before and L_after.
Do not claim identical surfaces solely because a small sentinel set is stable;
use the actual same-plane contours as the principal comparison.

## 5. Obtain genuinely same-plane live contours

Measure these three sampled radial locations:

- 0.22302 — worst failure.
- 0.29061 — passing inboard control.
- 0.50345 — passing outboard control.

Use exact physical planes from the existing production station metadata and the
same global-mm coordinate frame. Do NOT equate native u/v/w parameters to r/R.

For a native surface S(u,v), the live section must satisfy the physical plane:
`n dot (S(u,v) - p0) = 0`.

Use a verified native intersection method or solve this condition against the
native evaluator with bracketing/continuation and adaptive refinement. A
constant-parameter iso-curve is acceptable only if its whole relevant curve is
verified to lie in the required plane and covers the required section.

Include all relevant upper/lower surface pieces and seams. Track separate
components, multiple roots and trimmed boundaries; do not force a single-valued
chordwise curve, bridge gaps, or project arbitrary off-plane points onto the
plane and call them an intersection.

Record for each live point: native parameters, surface/patch identity, global
XYZ, and plane residual. Report missing branches, failed solves, coverage and
continuity checks rather than silently dropping points.

Predeclare diagnostic quality targets in plan.json:
- Native solved-point plane residual target <= 1e-6 mm.
- Contour/metric refinement stability target <= 1e-4 mm at the worst station.
- A diagnostic stage-agreement threshold of 0.001 mm, used only when the
  measured numerical uncertainty is comfortably smaller.

These are experimental measurement targets, NOT new product tolerances or
claims of exact continuous bounds. If unmet, refine within the budget or report
INCONCLUSIVE for the affected comparison; do not round an unknown into zero.

Use baseline, 2x and 4x refinement at the worst station, with convergence checks
at the passing controls. Add small geometric self-tests for the live-plane
extraction method, including a checkable curved surface and a case where the
surface parameter is not the physical radial coordinate.

## 6. Produce the comparison that makes the decision

E = unchanged expected contour from the actual submitted specification.
L_before = native same-plane contour captured before export.
L_after = native same-plane contour after export, without another update.
T = same-plane cut of the newly exported raw STEP.

Report at each selected plane:
- E versus L_before.
- E versus T.
- L_before versus T.
- L_before versus L_after.
- L_after versus T.

Use the previously self-tested, component-preserving bidirectional distance
method, consistent arc weighting, and the same geometric sampling policy.
Keep production metrics separate. Report numerical uncertainty/convergence.

Preserve common requested origin, chord and orientation. No best-fit scaling,
per-curve normalization, nonrigid registration, or empirical datum correction.

Provide actual data overlays and residual plots, especially the upper-surface
region near requested x/c approximately 0.155. Save live XYZ/parameter CSVs,
expected contours, and exact STEP section BReps. Label maxima as sampled, not
continuous Hausdorff bounds.

Use the existing production gates to describe input agreement where applicable.
Do not turn the three diagnostic cuts into a full 41-station acceptance result.

Interpret conservatively:

A. L_before differs from E and matches T; L_after remains consistent:
   the discrepancy is already present before STEP export. Focus on adapter
   configuration and native surface construction, not STEP writing alone.

B. L_before matches E within the relevant gates, remains stable after export,
   but T differs materially:
   localize to conversion/export/STEP interpretation. Do not blame a particular
   writer function without evidence of where its geometry first changes.

C. L_before and L_after differ materially:
   investigate export-time updates/mutation or evaluator-state confusion before
   claiming either A or B.

D. Mixed differences or insufficient live-contour accuracy:
   quantify the separate discrepancies or exact blocker; do not force one cause.

## 7. Continue to a useful next decision within this task

Do not stop at an unexplained label such as "OpenVSP problem" when the measured
boundary and matching source code allow one narrow follow-through.

After localization, inspect the relevant matching-version source/call path and
saved readbacks. Identify the smallest implicated operation or interval:
profile preparation, adapter transform, native rib/surface construction,
export-side surface conversion, serialization, or interpretation.

An input-dependent shape mismatch is not automatically an OpenVSP defect; test
whether our configuration or contract interpretation causes it.

If ONE specific general correction is justified by evidence, document the
mechanism and predicted effect BEFORE testing it. Then you may run ONE isolated
candidate using a diagnostic adapter/configuration copy. All engineer inputs
and acceptance gates remain fixed. The candidate must target the demonstrated
mechanism, not fit residuals at these three stations.

If the candidate improves the targeted discrepancy and does not damage the
controls, confirm it with ONE fresh repeat. Then apply the normal OCP closure
and full unchanged 41-station validation to the candidate with a bounded
standalone diagnostic time allowance. Report all dimensional/contour/topology
results, runtime and any remaining failures.

Maximum geometry-generation runs in this task: baseline, one justified
candidate, and one conditional repeat. No unbounded parameter search.

Do not add hand-tuned compensating coordinates, substitute a simpler airfoil,
remove radial controls, secretly add design stations, repair a shape to fit the
reference, or alter expected geometry to match the output.

If a general correction cannot be established, provide a compact reproducible
case, the implicated function/interval, and ONE concrete next action with the
precise missing evidence. A blocked/inconclusive conclusion is legitimate;
unsupported certainty is not.

## 8. Preserve scope and report evidence

No production patch, merge, backend replacement, UI work, performance rewrite,
cap sweep, timeout-policy change, or external NASA comparison is authorized.
The original failed job and retained validation status remain unchanged.

A successful isolated candidate is a PROTOTYPE result, not proof that the
current UI pipeline has been repaired. Record any diagnostic runtime extension;
it does not establish success under the product's current timeout.

Reuse existing diagnostics rather than creating another large reporting system.
Flush operation logs and use bounded worker timeouts (900 seconds per expensive
worker, with process termination and partial evidence preserved). Do not simply
increase limits repeatedly after failure. Avoid concurrent CAD runs.

Deliver a small reviewable bundle with:
- X57_SURFACE_TO_STEP_DECISION.md.
- plan.json, decision_summary.json and stage_comparison.csv.
- Native-surface API/source identity and state/readback changes.
- Live/expected coordinates, exact STEP cuts and data-derived overlays.
- Diagnostic code, commands, logs, convergence and self-test results.
- Optional isolated candidate diff and full validation, only if executed.
- Hash manifest; record paths/hashes for large STEP/VSP3 files without duplicating
  every old artifact in the ZIP.

Start the final report with four direct answers:
1. Is the discrepancy already present on the live pre-export surface?
2. Does export materially change that surface or its represented geometry?
3. Which operation/interval is demonstrated responsible, and with what evidence?
4. Is there a tested general correction, or exactly what prevents one?

Use an evidence-supported classification:
PRE_EXPORT_DISCREPANCY_LOCALIZED,
EXPORT_PATH_DISCREPANCY_LOCALIZED,
EXPORT_STATE_CHANGE_DETECTED,
MULTIPLE_STAGE_DISCREPANCIES,
or INCONCLUSIVE_WITH_SPECIFIC_BLOCKER.

Report any candidate separately as NOT_TESTED, FAILED, PARTIAL, or FULL_INTERNAL
DIAGNOSTIC_PASS. External NASA fidelity remains UNVERIFIED in every case here.

## Final instruction

Execute now in the existing workspace. Do not return planning alone.

Capture the missing live-surface evidence, compare it against the same-run STEP,
and follow the demonstrated branch to a bounded, actionable engineering decision.

The user must not be asked to repeat data entry or cycle through unrelated
settings. A measured limitation is acceptable; another speculative diagnosis
presented as certainty is not.
