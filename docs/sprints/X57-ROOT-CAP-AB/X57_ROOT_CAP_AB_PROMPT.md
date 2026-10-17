# X57-AB-01 — Controlled Root-End-Cap Experiment

Repository: https://github.com/ahmadqwcv5-droid/bladegen

## Objective and authorization

Execute the smallest controlled experiment recommended by the completed X-57 contour-isolation diagnostic.

Question: Does changing only the active OpenVSP root-end-cap treatment materially change the confirmed inboard contour discrepancy?

Root-cap influence is a hypothesis, not an established cause. A negative or inconclusive result is acceptable when supported by evidence.

Unlike the previous read-only investigation, this task explicitly permits fresh OpenVSP generation in disposable diagnostic outputs. It does NOT permit modifying production geometry code, the engineer's BladeSpec, acceptance rules, or retained artifacts.

Use the existing product construction path, with only a documented diagnostic intervention at the root-cap setting. Do not design a different blade or implement a production fix yet.

---

## 1. Preserve the existing evidence and working state

Read the completed contour-isolation report, summary, stage matrix, and diagnostic code before running experiments.

Original failed product job:
`a93b281c29b640afaa6bad698d64a61b`

Retained final STEP SHA-256:
`43c2cd72bebcd3949e0fe0b210aaac9ccbf6918952743fd109ecb0cac2e401d6`

Retained raw OpenVSP STEP SHA-256:
`85f798f74f672e4c78f3560e3413fcbdbba0ff7410424a840a5fc4e746d8b07f`

Latest supplied isolation evidence directory:
`docs/evidence/sprint04b/x57/contour_isolation/a93b281c_20261014T105834Z/`

Recorded HEAD:
`1cdb564a2eb92b0171acbab705b41ca63b57416c`

That diagnostic used a dirty worktree. Inspect actual HEAD and relevant source hashes; do not reset, clean, switch branches, or overwrite user work to force that revision. If geometry-relevant source differs from the recorded evidence, resolve the identity discrepancy before proceeding.

Verify the original STEP hashes and candidate/submitted/generated specification equivalence. Verify the retained resolved definition and its engineering vectors, not just the project name.

Record actual Git state, relevant source hashes, the installed OpenVSP binary/API identity, Python, OCP/OpenCascade, SciPy and NumPy versions. Keep runtime versions fixed across all arms; do not upgrade packages.

Create a new uniquely identified directory such as:
`docs/evidence/sprint04b/x57/root_cap_ab/<run_id>/`

Use subdirectories `A_original`, `B_root_cap_intervention`, and, when required, `A2_original_repeat`. Never reuse a failed-job output directory or relabel its job status.

---

## 2. Define the intervention before measuring its outcome

Inspect the actual adapter and the installed OpenVSP API/source definitions to identify:

- Which cap controls belong to the physical blade root, not the outer tip.
- The active root cap option and any dependent parameters.
- Their current values, units, legal enum names/values, and active status.
- When the adapter sets them relative to geometry update and export.

Do not assume that a particular U endpoint means the physical root without checking. Do not invent parameter names or use undocumented magic enum numbers.

Write `experiment_plan.json` before executing the comparison. Specify the exact single root-cap input to change, its A and B values, justification, invariants, measurements, and reproducibility criteria.

Prefer a verified supported no-root-cap setting for B if A genuinely uses an active cap treatment. This must change boundary construction, not merely hide cap faces during STEP export.

Do not simultaneously change cap mode, length, strength, offset and tip treatment. A mode change may alter dependent active states; record those consequences and distinguish them from additional user-controlled interventions.

If A already has no active root-cap influence, or no meaningful single-control intervention is available, report that limitation. Do not manufacture an inactive A/B comparison or sweep unrelated settings to obtain a better result.

---

## 3. Hold all nonexperimental inputs fixed

All arms must use the same complete BladeSpec and the same canonical resolved engineering data, including:

- Both airfoil stations and all upper/lower coordinates.
- Chord, twist, rake, skew and thickness controls.
- Resolved vectors, curve types and interpolation representation.
- Diameter, root radius, reference axis, rotation and placement.
- TE requirements and profile modifiers.
- Tip-end treatment.
- Tessellation, clustering and other geometry-construction settings.
- STEP units, tolerances, splitting, merging, surface-selection and conversion settings.

Do not compensate the known datum angle or change the source/product thickness choice. Do not add airfoil stations or simplify dense curves.

Read back accepted OpenVSP values, not just values passed into setter calls. Compare readbacks with intended adapter data and compare A against B using semantic parameter names/groups rather than transient IDs.

Keep generated outcomes, such as surface counts or knot structure, separate from controlled inputs: those outcomes may legitimately change because of the intervention. Any unexpected change to an unrelated authored parameter must be treated as a confound.

Capture resolved vectors, accepted PCurves and section data, relevant parameter dictionaries, API error records, and export settings. Make numerical readback limits explicit using existing policies; do not hide unexplained discrepancies.

---

## 4. Use a disposable harness, not a production patch

Reuse the actual production canonical preparation, adapter configuration and export sequence.

Prefer a diagnostic wrapper or isolated hook that overrides only the declared cap input before the normal geometry update/export stage. Preserve the same call order and observational hooks in every arm.

If no suitable hook exists, an isolated copy of the exact adapter is allowed in the diagnostic directory, with a minimal reviewed diff limited to readback/logging and the single experimental override. Do not reimplement unrelated construction logic. A must first establish that this instrumented path reproduces the retained geometry.

Do not edit the production adapter, validator, pipeline, UI or runtime timeout policy.

Start each arm in a fresh process with a fresh OpenVSP model, generated from the same submitted specification. Run arms sequentially and avoid concurrent product CAD builds using shared runtime state.

Do not load the retained VSP3 and call it frozen pre-export geometry: loading/updating can recompute a model. Newly saved VSP3 files are reproduction artifacts for the NEW runs, not evidence of the old in-memory surface.

Export and retain raw STEP before any OCP sewing or repair. The principal A/B comparison is between raw outputs. No new solidification strategy is authorized in this task.

Use bounded external worker timeouts with flushed stage logs; 900 seconds per arm is a diagnostic limit, not a new production setting. Preserve partial output on termination.

---

## 5. A — Reproduce the known discrepancy first

Generate A using the original cap configuration and all original settings.

At the same physical section planes, reproduce these recorded production results:

| Sampled r/R | RMS mm | P95 mm | Sampled max mm |
| --- | ---: | ---: | ---: |
| 0.22302 | 0.253757227408 | 0.503101705327 | 0.523742097408 |
| 0.29061 | 0.0193048321053 | 0.0323074200908 | 0.0362918307779 |
| 0.50345 | 0.00742495986712 | 0.0125984810839 | 0.0144823624182 |

Compare A's raw cuts directly with the matching retained raw cuts and with the unchanged expected contours.

Use these proposed experimental reproducibility criteria, recorded before B:

- A versus retained raw contour sampled maximum difference <= 0.0001 mm at each selected cut, using the established independent metric and density.
- Absolute change in each production RMS/P95/max metric <= 0.0001 mm.
- Record chord, axis, TE and twist deltas as additional checks.

These are diagnostic repeatability targets, NOT replacements for production acceptance tolerances. If a target is missed, report BASELINE_NOT_REPRODUCED and stop causal interpretation; do not widen it after seeing B.

A should reproduce the original contour failure. A is not required to pass the production shape gates for this experiment to be valid.

New STEP byte hashes may differ due to regenerated metadata. Preserve hashes for traceability but judge reproduction by inputs, accepted settings and measured geometry, not byte identity alone.

---

## 6. B — Change only the declared root-cap input

After A reproduces the retained discrepancy, generate B in a fresh process, changing only the predeclared root-cap input.

Verify the intervention was accepted and remained active as intended after the same update sequence. Preserve before/after readback and API errors.

If OpenVSP clamps, ignores or overrides the requested change, report an ineffective intervention. Do not interpret unchanged geometry as evidence against the hypothesis in that case.

Cut B at the same physical planes:
`r/R = 0.22302, 0.29061, 0.50345`.

Do not assume a native surface parameter equals r/R. Use the verified production plane positions and a shared requested reference frame.

Compare:

1. A versus retained raw geometry.
2. A versus the unchanged expected geometry.
3. B versus the SAME expected geometry.
4. A versus B directly.

Measure all section checks that remain applicable to raw surfaces, including contour, chord, twist, axis, TE and section-wire integrity. Report whole-output topology separately.

A B output with an open root may be a legitimate experimental surface. It is NOT an accepted closed-solid deliverable. Do not invent caps or sew in replacement geometry to turn this diagnostic into a product PASS.

If B cannot export or cannot be sectioned under otherwise unchanged settings, retain the error and classify that part as incomplete. Do not silently change export settings to rescue it.

---

## 7. Independent measurement and confirmation

Reuse both the unchanged production contour metric and the self-tested independent component-preserving, bidirectional point-to-segment metric from the isolation diagnostic.

Use the same sampling and weighting for A and B. Retain the known distinction between production and independent metrics; do not average them into one statistic.

At the worst station, retain the density-convergence check and verify whether the upper-surface deficit around requested x/c approximately 0.155 changes. Compare the contours themselves, not only their maxima.

Label sampled maxima as sampled. Do not claim continuous Hausdorff bounds. Do not use separate scaling or best-fit alignment to erase geometric differences.

Generate true-scale, equal-aspect overlays and residual plots from actual measured data. Provide exact section BRep files and CSV coordinates for independent review.

If B materially changes the discrepancy, generate A2 from a fresh process with the ORIGINAL root-cap configuration restored. It must reproduce A under the same repeatability criteria. This checks that the observed effect is reproducible rather than process state or unrelated drift.

Bound the initial experiment to A, B and the conditional A2. Do not begin an unbounded cap-parameter search.

Once a reproducible effect is observed, use the already-generated A/B files to check the remaining failed sampled planes:

- 0.207365125 — sampled root; requested root was 0.20238.
- 0.20949
- 0.24183
- 0.26472
- 0.31863
- 0.34811

Also check one previously passing outboard station and the sampled tip from the retained station plan. Requested tip 1.0 was sampled at 0.9995014875.

Retain the original station roles and acceptance policies; do not recompute easier endpoint offsets for B. These additional cuts investigate the spatial effect, not full 41-station or whole-blade acceptance.

---

## 8. What the experiment can and cannot establish

Separate these conclusions:

- A reproduces the known discrepancy.
- The declared root-cap intervention was accepted without confounding input changes.
- The intervention does or does not change the observed contour error.
- The exact internal mechanism is or is not localized further.
- A changed surface is or is not a usable closed solid.

If B improves the contours and A2 restores the original discrepancy, that supports a causal effect of this root-cap treatment on the EXPORTED geometry under this configuration. It does not, by itself, prove which internal surface-generation/export operation implements that effect or establish a general production fix.

If B does not materially change the error, report NO_MATERIAL_EFFECT_FOR_TESTED_INTERVENTION, not “all root boundary effects disproven.” Quantify the direct A/B difference relative to reproducibility noise.

If the results are mixed, report affected stations and new regressions rather than selecting only the best-looking station.

Where a documented, non-mutating API makes capture of the LIVE pre-export surface practical, save such evidence for the newly generated models without changing construction/export settings. Do not substitute coarse visual tessellation or an unverified iso-parameter mapping for an actual same-plane comparison.

This additional capture is optional: do not turn a small A/B test into an OpenVSP rewrite. If it is unavailable, report that the experiment observes the combined generation/export path.

If the hypothesis is unsupported, propose ONE smallest next experiment to distinguish remaining adapter/surface-generation/export possibilities. Do not execute a new multi-factor investigation in this task.

---

## 9. Evidence bundle and completion gate

Deliver one reviewable directory and ZIP containing:

- `X57_ROOT_CAP_AB_REPORT.md`
- `experiment_plan.json`
- `experiment_summary.json`
- `readback_diff.json`
- `station_comparison.csv`
- `timings.csv`
- Runner source, commands, logs and environment identity.
- Per-arm input/resolved hashes and parameter/readback snapshots.
- Per-station expected/actual coordinates, exact cuts and overlays.
- Manifest with SHA-256 verification results.

Retain every generated raw STEP and VSP3 in its arm directory. To avoid an unnecessarily large evidence ZIP, large full-model files may remain at explicitly recorded local paths with sizes/hashes; include the smaller exact section evidence and identify omitted large artifacts clearly.

Recheck that original failed-job artifacts, fixtures and production source files are unchanged.

The report must state one supported diagnostic outcome, such as:

- ROOT_CAP_EFFECT_REPRODUCED
- NO_MATERIAL_EFFECT_FOR_TESTED_INTERVENTION
- BASELINE_NOT_REPRODUCED
- CONFOUNDED_OR_INEFFECTIVE_INTERVENTION
- INCOMPLETE

Do not force a positive hypothesis result.

Keep the original product status unchanged:

- Original job: FAILED.
- Retained blade's full internal validation: FAIL.
- External NASA fidelity: UNVERIFIED.
- Experimental B: diagnostic only; no automatic full-CAD acceptance.

Recommend the smallest general correction only if evidence supports it. A cap-free surface cannot be the final fix by itself: preserving section shape AND achieving separately validated boundary closure would need qualification in a subsequent implementation task.

Do not implement that correction, change timeouts, optimize section extraction, rerun unrelated frontend suites, or merge code now.

## Final instruction

Execute the controlled experiment, not just a plan. Fresh disposable OpenVSP runs are now explicitly authorized within the limits above.

Reproduce A first; vary one accepted root-cap input for B; repeat A if an effect is observed; return the geometry and readback evidence.

The required answer is:
“Did this root-cap treatment cause a reproducible change in the inboard contour discrepancy, with the engineer's definition and other settings held fixed?”

It is not:
“We found a setting that produces a smaller number, so X-57 now passes.”
