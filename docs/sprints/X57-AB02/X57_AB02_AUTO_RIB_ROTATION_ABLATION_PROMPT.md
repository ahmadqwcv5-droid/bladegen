# X57-AB-02 — Explicit Auto-Rib-Rotation Ablation and Candidate Qualification

Repository: https://github.com/ahmadqwcv5-droid/bladegen

## 1. Explicit authorization — this replaces the previous sole-cause restriction

Execute the controlled m_ZRotate ablation recommended after X57-LOC-03.

**You are expressly authorized to test the rotation intervention even though the unchanged profile-preparation residual exists and its earlier refinement target was not met.** The rotation does NOT have to be the only contribution.

The experimental question is:

> With every engineer input and the profile-preparation operation unchanged, what happens to the physical-plane section errors when ONLY the automatic derivative-driven rib rotation is disabled?

Hold the small preparation discrepancy fixed as a background contribution. Measure and report it separately; do not subtract it from final errors, repair it, or use it as a reason to leave this candidate NOT_TESTED.

The authorization covers an isolated native-library experiment, not a production deployment. Do not alter the installed product runtime, production source, BladeSpec contract, validator, or tolerances.

Run A → B → A2. If B passes the three selected production section gates, continue in this same task through unchanged OCP finalization, STEP re-import, and complete 41-station validation. Do not stop to request another prompt for that already-authorized continuation.

No positive outcome is presumed. A measured failure or partial improvement is useful evidence.

## 2. Reuse the established evidence and preserve working state

Read X57-LOC-03 and its manifest, probe diff, runtime identity, native snapshots and analysis code. Reuse the qualified diagnostic source/build and measurement tools; do not start a new observation-only investigation.

Relevant prior outputs:
- X57_RIB_PLACEMENT_DECISION.md
- decision_summary.json and evidence_manifest.json
- openvsp_probe.diff and runtime_identity.json
- probe_rib_inventory.csv and probe_rib_surface_audit.csv
- input_blade_spec.json and resolved_blade_spec.json
- The completed 41-station production measurements and plan.

Original failed product job:
`a93b281c29b640afaa6bad698d64a61b`

Retained final STEP SHA-256:
`43c2cd72bebcd3949e0fe0b210aaac9ccbf6918952743fd109ecb0cac2e401d6`

Retained raw STEP SHA-256:
`85f798f74f672e4c78f3560e3413fcbdbba0ff7410424a840a5fc4e746d8b07f`

Recorded project HEAD:
`1cdb564a2eb92b0171acbab705b41ca63b57416c`, with a dirty worktree.

Recorded native source: OpenVSP_3.54.0, commit
`db6c6fe8f4eca27d7517f4ae0b2078abdd3fd927`.

Inspect actual identities. Preserve existing work; do not reset, clean, pull, switch the user's branch, commit or merge. Do not require a clean worktree or an old HEAD when equivalent geometry source is demonstrably preserved. Resolve genuine geometry-source or artifact mismatches before interpretation.

Create a new directory:
`docs/evidence/sprint04b/x57/rotation_ablation/<run_id>/`

Use separate A_native, B_rotation_bypassed, and A2_native_recovery directories. Record hashes before/after for immutable inputs, retained evidence, production geometry source and installed runtime. Store the exact dirty-source identity, commands, executable paths and dependency versions.

Preserve the original failed job and its status. Never overwrite its STEP or create a retroactive success report in that job directory.

## 3. Implement one diagnostic switch in the isolated native build

Use the same matching-version instrumented executable for A, B and A2, differing only in an explicit diagnostic switch read before model construction/update:

- A: original automatic rib rotation applied.
- B: only that automatic rotation bypassed.
- A2: original automatic rotation applied again.

This is a custom diagnostic facility, NOT a claimed public OpenVSP option or a new BladeSpec field. Default it to the original behavior and record the effective mode in the native output.

Inspect the observed transform chain and choose the smallest verified intervention at the automatic rotation application. Retain the calculation of the original derivative-driven angle for logging, but apply a zero angle in B at that operation only. Preserve the same pivot and paired translation operations; replacing a rotation with identity must not introduce a translation.

Do not zero the engineer's Rake/Axial curves, replace their derivatives, adjust Twist, or post-transform the completed blade. Do not apply a compensating global-Z rotation: the observed operation acts about the transformed chord.

Apply the intervention uniformly to every applicable rib of the test geometry, not just the measured locations. Log computed angle and actually applied angle separately. Verify all relevant positioning calls receive the intended mode, including any endpoint/profile positioning paths that affect the same blade.

Keep all other geometry operations unchanged. If the switch unexpectedly changes an unrelated authored value or pre-positioning profile, classify the comparison as confounded and fix the harness, not the design.

Keep the isolated source diff minimal and separate the preexisting observation hooks from the new intervention. Do not replace production binaries, alter global library paths or application launch scripts, or install a patched runtime into the product environment.

## 4. Controlled invariants and arm lifecycle

All arms use identical:
- Submitted BladeSpec and resolved engineering vectors.
- Both embedded airfoil profiles, their point order, and station radii.
- Chord, Twist, Rake, Skew, Thickness and auxiliary curves.
- Curve representation, derivative evaluation, and rib-selection logic.
- Reference axis, origins, pivots, other transforms and rotation order.
- Profile preparation, thickness operations, TE and normalization policy.
- Root/tip cap treatment, tessellation/clustering, and STEP settings.
- Canonical expected-contour definition and measurement policy.

The native computed angles and derivatives should remain unchanged. Only their application is disabled in B. Geometry-dependent outputs may change; record them as outcomes, not as extra authored interventions.

The prior run contained 619 pseudo-ribs. Compare the new inventory and correspondence, not merely its count. Do not change rib merging, insert stations, or repair the previously observed near-tip station equivalence in this experiment. Report an unexpected inventory change as a confound.

Read back actual accepted model values. Capture prepared profiles before positioning and prove A/B/A2 preparation is unchanged using actual curve data or matched native samples with demonstrated correspondence.

Start each arm in a fresh process/model. Reusing the same immutable saved VSP3 as a reproducible initialization is allowed only with its identity, accepted state and baseline reproduction verified; loading it is a new geometry computation, not a frozen old surface.

A saved VSP3 alone may not retain the diagnostic mode. Include the binary identity, switch value and replay command for every arm. Do not reload B with the unpatched production runtime and present its recomputed geometry as the candidate.

## 5. Freeze the comparison plan before B

Use the unchanged physical planes:
- r/R = 0.22302 — worst failed station.
- r/R = 0.29061 — passing inboard control.
- r/R = 0.50345 — passing farther-outboard control.

Use the recorded global-mm frame and fixed plane Y=R*(r/R). Native surface parameters must not be assumed equal to r/R. Reuse the qualified physical-plane solver, including coverage and branch checks for the new geometry.

Freeze in plan.json:
- The three-station subset from the real production station plan.
- Full 41-station plan, roles, endpoint policy and expected geometry.
- Production tolerances and their source hashes.
- Production and independent metric definitions and sampling policies.
- Baseline/recovery direct contour repeatability target: <=0.0001 mm.
- Repeatability of production RMS/P95/max: absolute changes <=0.0001 mm when comparing the same stage and method.
- Native plane residual target: <=1e-6 mm.
- Diagnostic sampled-max refinement stability target: <=0.0001 mm.
- Material A/B effect threshold: 0.001 mm direct sampled contour difference, provided measurement uncertainty is comfortably smaller.

These diagnostic thresholds do not replace product acceptance gates. Never compare statistics with different weighting or different representations as though they were repeated identical measurements.

## 6. A — reproduce the known failure

Generate the original configuration in the new switch-enabled diagnostic build. Capture live physical-plane cuts and export raw STEP with the original settings.

Reproduce the corresponding prior metrics:

| r/R | Production RMS mm | Production P95 mm | Production sampled max mm | Independent live sampled max mm |
|---|---:|---:|---:|---:|
| 0.22302 | 0.253757227408 | 0.503101705327 | 0.523742097408 | 0.523791332424 |
| 0.29061 | 0.0193048321053 | 0.0323074200908 | 0.0362918307779 | 0.0325858524 |
| 0.50345 | 0.00742495986712 | 0.0125984810839 | 0.0144823624182 | 0.00464159414 |

The production values concern STEP measurements; the independent column concerns live-surface measurements. Reproduce each with its own original method and compare actual contours directly with matching retained evidence.

A is expected to reproduce FAIL at the worst station. Do not confuse successful baseline reproduction with geometry acceptance.

If A does not reproduce the prior geometry within the frozen criteria, stop causal interpretation, retain artifacts, and report BASELINE_NOT_REPRODUCED. Do not widen the criterion to admit B.

## 7. B — execute the authorized ablation now

Generate B with only automatic rotation application bypassed. The existing preparation residual and its unresolved refinement are explicitly NOT reasons to skip this run.

Verify from the native probe:
- Computed derivative-driven angles match A.
- Applied automatic angles are zero in B for all applicable ribs.
- Prepared profiles, rib radii, nonexperimental settings and inputs match A.
- Positioned rib planes and their radial departures are measured, not assumed correct.
- The generated surface still preserves its supplied ribs at the verified correspondence.

Capture fresh B live contours and export fresh B raw STEP. Every B result must be computed from B geometry. In particular, do not reuse the LOC-03 analysis code's saved LOC-02 final-contour results as candidate measurements; those reused arrays are historical baseline evidence only.

At all three physical planes compute:
1. E versus A, E versus B, and A versus B, where E is the unchanged expected contour.
2. Both production section metrics and the established independent bidirectional metric, clearly separated.
3. Chord, Twist, reference-axis, TE and section-wire checks, not just contour maxima.
4. Native live-to-raw STEP agreement on the candidate.
5. Plane orientation/departure and the upper-surface residual region near x/c approximately 0.155 at the worst station.

Show same-frame, true-scale overlays and residual plots from actual data. Preserve exact STEP section BReps and live/expected coordinates. No best-fit alignment, separate normalization or scaling to erase differences. Label maxima as sampled rather than exact continuous bounds.

Retain the small profile-preparation mismatch unchanged and report it separately. Better sampling may refine its diagnostic estimate, but no correction to the prepared profile is authorized. Incomplete convergence of that separate small metric does not veto a valid A/B comparison or the later unchanged product gates. A genuinely uncertain candidate section comparison must remain explicitly uncertain.

## 8. A2 — restore the original behavior

After B completes, run A2 in a fresh process using the SAME diagnostic binary with original rotation restored, whether B improved or did not materially change the result.

Verify A2 recovers A under the frozen repeatability criteria. Check native applied angles as well as the three live/STEP contours.

Failure of recovery means the causal experiment is not qualified, even if B looks better. Report it without tuning any additional geometry parameter.

## 9. Continue automatically to full candidate qualification when eligible

If A/A2 reproduction and A/B invariants pass, and all three B sections pass the ORIGINAL production gates with consistent independent evidence, continue without asking the user for new authorization.

Use the existing production OCP finalization on B's raw STEP. Then export the candidate solid STEP, re-import it and run the exact full production measurement/summary path with the unchanged submitted BladeSpec.

The original plan has 41 stations. Preserve requested radii, station roles and the SAME sampled endpoint locations, including:
- Requested root 0.20238 → sampled root 0.207365125.
- Requested tip 1.0 → sampled tip 0.9995014875.

Do not shift endpoint cuts to make B easier to measure, remove difficult stations, or accept native isocurves as replacements for the production fixed-plane cuts.

Require and report:
- One valid connected solid and closed-shell status.
- Zero non-degenerate free edges and valid BRep.
- Planned/completed/passed/failed station counts.
- Every original chord, twist, axis, TE, contour and wire check.
- Imported-profile-specific results where applicable.
- Unchanged STEP round-trip checks, including volume and bounding-box deltas.
- Adaptive volume and method, without treating volume as proof of shape fidelity.
- Stage and per-station timings.

Call the real production acceptance function, not a handwritten replacement boolean. Preserve any additional diagnostic fields separately.

Report the full station records even when they fail. Use a new file such as candidate_full_validation.json in B's evidence directory; never overwrite the old job's validation/status. If B cannot form a valid solid with existing finalization, record that failure; do not invent caps, change sewing tolerances or repair the shape in a second experiment.

If B fails one of the three initial gates, still complete the A/B/A2 report, retain B's output, and name the failed criteria. Report full validation as NOT_RUN with the reason; do not call a partial improvement a complete correction.

## 10. Keep process status and resource limits honest

Reuse the existing isolated build where possible. Use one declared finite build budget and separate externally supervised geometry/validation workers, with a 900-second diagnostic limit per expensive worker and partial-log preservation. This does not change the product timeout or demonstrate usability under that timeout.

Keep A, B and A2 sequential and avoid concurrent product CAD activity. Read STEP once per measurement pass where practical; do not rewrite extraction algorithms or reduce sampling for speed.

Record actual native and supervisor exit codes. The previous probe returned code 10 despite a completed observation; do not blanket-map nonzero codes to success. Prefer a clean, verified completion path. If a documented host exit convention still requires separate interpretation, retain its code, source-backed explanation, explicit completion markers and artifact checks, and label this separately from geometry acceptance. A timeout, crash or incomplete export is not a completed candidate run.

Budget the experiment as three model constructions: A, B, A2. Subsequent OCP work reuses B's generated raw STEP. Report any failed launch distinctly; no hidden retries, parameter sweeps or additional correction candidates.

## 11. Decision and scope of any success

Report causal outcome separately from candidate acceptance:

Causal outcome:
- ROTATION_EFFECT_REPRODUCED
- NO_MATERIAL_EFFECT_FOR_TESTED_ABLATION
- CONFOUNDED_OR_BASELINE_RECOVERY_FAILED
- BASELINE_NOT_REPRODUCED
- INCOMPLETE_WITH_SPECIFIC_BLOCKER

Candidate outcome:
- THREE_STATION_FAIL
- THREE_STATION_PASS_FULL_VALIDATION_INCOMPLETE
- FULL_INTERNAL_DIAGNOSTIC_FAIL
- FULL_INTERNAL_DIAGNOSTIC_PASS
- NOT_EVALUATED_WITH_SPECIFIC_REASON

A reproduced effect can be causal without being sufficient to repair every remaining error. Do not require this operation to be the only contribution. Do not claim the whole 0.524 mm discrepancy was explained merely because rib-plane tilt vanished.

If B passes all 41 stations and topology/round-trip gates, recommend the smallest deployment proposal, including whether it requires a maintained/upstream native-library change. Do not invent a public API switch or claim that every other blade is already qualified.

Even a full internal diagnostic PASS means compliance with BladeGen's existing fixed-plane contract for this case. It does not demonstrate faithful reproduction of the original NASA model's possibly different native construction semantics. External NASA fidelity remains UNVERIFIED.

No production integration, runtime replacement, UI rebuild, schema change, tolerance change, archive modification, unrelated regression campaign or auto-merge is authorized. Deployment and product-wide qualification are the next decision, not automatic consequences of this experiment.

## 12. Deliverables and final handoff

Deliver one compact review bundle containing:
- X57_AUTO_ROTATION_AB_DECISION.md
- Pre-run plan.json and experiment_summary.json
- A/B/A2 settings/readback and input-identity comparisons
- Minimal native intervention diff and observation-hook identity
- rib_plane_comparison.csv and station_comparison.csv
- A2 recovery results
- New live/expected coordinates, exact selected section files and overlays
- Candidate full validation/measurements and OCP results if executed
- Commands, actual exit codes, logs, environment identity and timings
- SHA-256 manifest distinguishing bundled files from omitted large artifacts

Retain each arm's raw STEP/VSP3 with its replay requirements. If B is finalized, provide the candidate solid STEP separately with size and hash. Do not bundle all historical large CAD files again.

Recheck production-source/runtime/input/prior-evidence integrity at the end.

Start the final report with direct answers:
1. Was B actually run, with only automatic rotation application bypassed?
2. Did A2 restore A, and were the prepared profiles/engineer inputs unchanged?
3. How did the three section results change, including every original gate?
4. Did the unchanged 41-station validation complete and pass? If not, exactly why?
5. Is the result a diagnostic effect, a qualified prototype, or a deployment-ready change? Do not conflate them.

The original failed job and retained blade validation remain FAILED/FAIL. Any candidate result belongs only to this new experiment.

## Final instruction

Execute A → B → A2 and the authorized conditional full qualification now, not another observation-only report.

The earlier “rotation must be the sole contribution” condition is explicitly withdrawn. Keep the small preparation residual fixed and visible; test the actual effect of removing automatic rib tilt without changing what the engineer requested.
