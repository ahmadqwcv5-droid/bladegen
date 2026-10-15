# X57-LOC-03 — Rib Placement, Section-Plane Semantics & Loft Verification

Repository: https://github.com/ahmadqwcv5-droid/bladegen

## Mission

Locate the first demonstrated divergence inside the remaining OpenVSP construction interval:

Prepared profile → positioned pseudo rib → surface built from those ribs.

Answer whether the airfoil shape is changed during preparation, placed in a different plane from the BladeGen definition, or not preserved by the subsequent surface construction.

The `m_ZRotate` hypothesis is NOT established. Observe the actual intermediate geometry first. If that evidence supports a specific mechanism, you may test one tightly controlled diagnostic intervention in an isolated build during this task. Do not stop merely at another correlation if a causal check is practical within this scope.

Do not modify the production application, its installed OpenVSP runtime, engineer inputs, or acceptance rules. A source-instrumented diagnostic executable is not a deployed product fix.

## 1. Evidence and fixed scope

Read the completed X57-LOC-02 report, summary, diagnostic source and evidence. Reuse the verified live-plane extraction and independent contour metric rather than starting another diagnostic framework.

Known evidence, within its measured scope:

- The approximately 0.523791 mm discrepancy at r/R=0.22302 exists on the live pre-export surface.
- The maximum live-to-STEP sampled difference across the three tested planes was 0.000029905 mm.
- No material export-time live-surface mutation was observed.
- The tested root-cap intervention did not materially change the discrepancy.
- Raw and OCP-final cuts agree at the previously tested planes.
- Original full validation completed 41 stations and failed seven contour gates.
- Input fidelity and interactive performance already passed.

Original failed job:
`a93b281c29b640afaa6bad698d64a61b`

Retained final STEP SHA-256:
`43c2cd72bebcd3949e0fe0b210aaac9ccbf6918952743fd109ecb0cac2e401d6`

Retained raw STEP SHA-256:
`85f798f74f672e4c78f3560e3413fcbdbba0ff7410424a840a5fc4e746d8b07f`

Last recorded HEAD:
`1cdb564a2eb92b0171acbab705b41ca63b57416c`, with preserved dirty work.

Inspect actual HEAD, relevant source hashes and the existing diff. Do not reset, clean, pull, switch branches, overwrite work, commit or merge automatically. Resolve any geometry-relevant identity mismatch before comparing results.

Verify and reuse the actual submitted BladeSpec, matching resolved vectors and original settings, including FLAT root/tip caps. Preserve all coordinates, thickness/TE intent, station counts, reference axis, curve representations, dimensions and export settings.

Keep the original failed job and all earlier evidence immutable. Write to a new directory:
`docs/evidence/sprint04b/x57/rib_placement_localization/<run_id>/`

No further cap trials, UI work, timeout-policy changes, performance rewrites, alternative CAD backends or NASA comparisons belong to this task.

## 2. Establish the section-plane contract

Write a short contract table from the existing BladeSpec documentation, adapter and frozen expected-geometry implementation:

- Requested global radial coordinate and physical section plane.
- Chord direction, thickness-normal direction and reference-axis placement.
- Meaning and frame of Rake/Skew and any auxiliary axial/tangential controls.
- Twist rotation and rotation order.
- Units and transformations between profile, model and global coordinates.

The current comparison uses physical planes Y=R*(r/R). Do not silently replace that contract with an airfoil plane normal to a curved reference axis to make validation pass.

Keep native OpenVSP semantics distinct from the product contract. A semantic mismatch may explain a product failure without proving that OpenVSP is mathematically defective.

If the product documentation is ambiguous, identify the ambiguity, but retain the existing expected geometry as the unchanged acceptance reference in this investigation.

## 3. Add an observation-only probe in an isolated matching runtime

Inspect the actual matching-version source around:

- `PropGeom::UpdateSurf`
- `InterpXSecCurve`
- `PropPositioner`
- `SkinCubicSpline`

Verify names and boundaries against the source actually built; do not invent public API flags or assume internal members are exposed through Python.

Prefer an existing reliable read-only hook. If unavailable, explicitly authorized: build a matching-version OpenVSP diagnostic executable/library in a SEPARATE source/build/install prefix with narrowly scoped observation hooks.

Do not replace the production binary, alter the global Python environment, upgrade dependencies or redirect application launch scripts to this build. Record the upstream revision, dependency/compiler identities, build options, executable/module paths, hashes, and exact instrumentation diff.

Observation hooks must copy/dump existing objects without changing call order, transform values, rib ordering, curve parameterization or geometry update behavior. Avoid calling setters or another Update merely to inspect data. Record update sequence and geometry identity so intermediate/transient updates cannot be confused with the final accepted model state.

A source rebuild can differ from the installed binary. Therefore qualify the instrumented baseline against the retained/native baseline before trusting its interior measurements.

## 4. Capture the real stages, not a reconstruction labelled as observation

For each actual pseudo rib, save compact metadata; preserve detailed geometry for the three target neighborhoods and every rib influencing those intervals:

- r/R and native rib/skin parameter.
- Why the rib exists: airfoil station, particular resolved-curve control, or another construction reason.
- Profile interpolation identities and fraction.
- Shape after profile preparation but BEFORE positioning.
- Shape immediately BEFORE and AFTER the suspected rotation, where separable.
- Fully transformed rib immediately BEFORE `SkinCubicSpline`.
- Rib parameter correspondence and the completed surface immediately AFTER skinning, before later caps/modifiers where accessible.
- Corresponding final live main surface.

Preserve actual curve definitions/control data or faithful sampled XYZ with native parameters and demonstrated convergence. Logging only the original upper/lower input arrays is insufficient.

Capture neighboring ribs, not just the rib whose reference radius equals the selected plane: a physical plane can intersect a surface generated across several tilted ribs.

Use actual runtime correspondence to identify support and surface parameters. Do not invent nearest-rib equivalence or assume a rib index/native u is r/R. Record whether each target radius is actually a rib; do not insert a rib to make inspection easier. Capture all compact metadata first; detailed dumps may be limited to verified contributing neighborhoods, without assuming that a globally coupled spline has only two relevant ribs.

For the positioning chain record:

- Scale/stretch operations, translations, pivots and rotations in order.
- Local-to-global transformation or the equivalent ordered operations.
- Frame in which each rotation acts and the resulting global axis.
- `m_ZRotate` in radians and degrees, and the actual values used to compute it.
- Rake/Axial values and actual `Compdt` results at each rib radius.
- Any dependent compensation applied during positioning.

Do not assume positioning is entirely rigid or that a variable named Z means rotation about the final global Z axis. Measure and document the actual operations.

## 5. Reproduce the surface before causal interpretation

Use the primary planes:

- 0.22302 — worst failure.
- 0.29061 — passing inboard control.
- 0.50345 — passing outboard control.

The prior independent expected-to-live sampled maxima were:

- 0.523791332 mm
- 0.0325858524 mm
- 0.00464159414 mm

Compare the instrumented final live surface to the saved matching live data, and check the same-plane geometry against the retained raw reference.

Predeclare targets before examining a candidate:

- Baseline repeatability: direct sampled contour difference <=0.0001 mm at each selected plane, and reproduction of corresponding recorded metrics under the SAME metric/density.
- Same-plane extraction residual <=1e-6 mm.
- Diagnostic refinement stability <=1e-4 mm for the reported sampled maxima.
- Stage/operation agreement threshold 0.001 mm only when numerical uncertainty is comfortably smaller.

These are diagnostic measurement criteria, NOT replacement product tolerances. Keep production and independent metrics separate.

If the source-instrumented baseline cannot reproduce the original discrepancy, report `BASELINE_NOT_REPRODUCED` with the source/runtime or observation mismatch. Do not use a nonmatching source build to claim a cause or an improvement.

Do not rerun a broad export experiment: that stage has already been localized. Reuse retained reference cuts and the same-run live evaluator where possible.

## 6. Distinguish intrinsic shape, placement and skinning

For each target neighborhood, perform three DIFFERENT comparisons.

### A. Intrinsic profile preparation

Compare the prepared pre-positioning curve with the submitted/canonical profile in the documented local frame. Quantify fitting, resampling, TE and thickness effects if present.

For positioned ribs, inverse-apply only recorded, analytically known transforms to inspect intrinsic shape. Report any nonuniform scale/shear separately. Do not use a best-fit registration to invent the inverse transform.

Agreement after an inverse transform can establish local shape preservation. It does NOT establish that the rib was placed in the requested global plane.

### B. Rib placement

Determine each rib's actual plane from the known transformed basis, and verify planarity against its points. Report:

- Plane origin and normal in global mm.
- Angular difference from the requested section plane.
- Maximum and range of Y displacement relative to the requested Y=R*r/R plane.
- Chord/reference-axis displacement and orientation.
- Actual transform versus the transform implied by the fixed BladeSpec contract.

Global positioned-rib comparisons must retain XYZ and use three-dimensional distances. The existing XZ contour metric is appropriate only after both curves are proven coplanar in the same frame; silently discarding Y would hide the very effect being investigated.

Do NOT orthogonally project a tilted rib onto the requested plane and call that the requested airfoil.

Do NOT intersect a tilted one-dimensional rib curve with another plane and interpret the resulting isolated points as a complete airfoil section.

### C. Rib preservation by the surface

Verify that the post-skin surface contains each supplied transformed rib at its actual known skin parameter, including any parameter remapping. Use curve-to-surface/iso-curve checks with geometric refinement, not equal-index point matching without proof.

Then separately intersect the completed surface with the original PHYSICAL section planes using the already validated live-plane solver. This second contour is what the product validator measures.

A surface can preserve its tilted ribs while its fixed-Y cuts differ from the original profile. Conversely, correctly placed ribs can be altered by surface construction. Show which situation the captured geometry supports.

Do not assume that interpolation of two identical endpoint airfoils guarantees every physical cut is identical when positioning and spanwise geometry vary.

## 7. Test the derivative-rotation hypothesis quantitatively

Treat the reported formula
`m_ZRotate = atan(-RakeCurve.Compdt(r) - AxialCurve.Compdt(r))`
as a hypothesis to verify against the actual source and runtime values.

For the captured ribs:

- Verify derivative units and parameter domains.
- Record the actual derivative value selected at each control/knot.
- Inspect left/right slopes and the implementation's knot convention where the curve is piecewise linear. Do not substitute their average or a SciPy derivative for the value OpenVSP actually used.
- Compare with the canonical PCHIP derivative as explanatory evidence ONLY. Do not change the accepted resolved vectors or interpolation in this experiment.
- Independently reconstruct the complete known positioning transform and verify it against the captured positioned rib.
- Quantify how much mismatch is attributable to preparation, orientation and skinning, rather than claiming that a large rotation angle alone explains 0.524 mm.

A tilt angle that correlates with Rake slope is not yet causal proof of the physical-cut error. The explanation must be consistent with the failing station AND the passing controls, including neighboring-rib effects.

Small analytic transform self-tests with zero slope and positive/negative slope are appropriate. Label them synthetic method checks, not replacements for X-57 qualification.

## 8. Conditional single-variable causal check — permitted, not mandatory

After the observation-only baseline reproduces the retained geometry and identifies a specific mechanism, document one predicted intervention in the plan BEFORE executing it.

If the evidence implicates ONLY the automatically derived rib rotation, you may add an explicit diagnostic-only switch in the isolated source build that bypasses just that operation for ALL applicable ribs. Preserve every other transform, pivot, engineering input, rib location, curve, cap, update order and export setting.

Run baseline and intervention through the SAME diagnostic build, differing only in that switch. Read back/log its application. Do not obtain zero rotation by changing the engineer's Rake/Axial curves, and do not correct only the three measured ribs.

This intervention is an ablation to test causality; it is not automatically a valid product correction. Record collateral effects on positioning, shape and all three cut measurements.

If an inseparable coupled transform or a different first divergence is observed, do not force this ablation. Identify the implicated operation and propose the smallest correction consistent with the measurements; no unrelated parameter sweep is authorized.

If the intervention produces a meaningful improvement, repeat the original configuration in a fresh process to check recovery of the baseline. Budget: one qualified baseline, one justified intervention and one conditional baseline repeat; no unbounded full-model search.

If the candidate then passes all three original section gates and independent checks without new regressions, run the existing OCP finalization and the complete unchanged 41-station production validation on that candidate in the diagnostic directory. Keep endpoint sampling policy, contour/chord/twist/axis/TE/wire gates and STEP round-trip rules unchanged.

A failed or partially improved candidate is useful evidence. Do not widen tolerances or begin another compensation trial. Do not issue an official success result for the original failed job.

## 9. Produce a decision useful for the product

The report must distinguish:

- Intrinsic profile fidelity.
- Requested versus actual rib placement.
- Preservation of transformed ribs by skinning.
- Resulting fixed-plane section fidelity.
- Whether a causal intervention was tested and what it established.
- Whether a GENERAL deployable correction exists, not merely a diagnostic fork.

Possible primary classifications:

- PROFILE_PREPARATION_MISMATCH
- RIB_PLACEMENT_CONTRACT_MISMATCH
- RIB_TO_SURFACE_MISMATCH
- MULTIPLE_CONTRIBUTIONS
- BASELINE_NOT_REPRODUCED
- INCONCLUSIVE_WITH_SPECIFIC_BLOCKER

Candidate status is separate: NOT_TESTED, FAILED, PARTIAL, or FULL_INTERNAL_DIAGNOSTIC_PASS.

If a fixed-plane versus native tilted-plane interpretation is the explanation, call it a product/backend contract mismatch unless a distinct OpenVSP defect is demonstrated. Do not rewrite the validator to accept native tilt without explicit product approval.

If a corrected diagnostic fork works, say whether deployment requires an existing public setting, an adapter change, or a maintained/upstream native-library patch. Do not suggest a public flag exists when the source probe required custom C++.

State exactly what prevents a correction if none can be tested. Do not return only “investigate OpenVSP further.” Provide the last matching stage, first mismatching stage, measured evidence and one concrete next action.

## 10. Deliver evidence without expanding the task

Provide one reviewable ZIP containing:

- `X57_RIB_PLACEMENT_DECISION.md`
- `plan.json` and `decision_summary.json`
- `rib_inventory.csv`, `rib_transform_audit.csv`, `rib_surface_comparison.csv`
- Exact/faithful pre- and post-positioning curve data with frame/units/parameters.
- Same-plane surface contours and comparison measurements.
- Data-derived plots showing local profile shape, tilted versus requested planes, and actual fixed-plane residuals.
- Matching-version probe diff, build/run commands, logs, runtime identity and hashes.
- Optional intervention diff, comparisons and full candidate validation, when executed.
- SHA-256 manifest, with omitted large artifacts listed by path, size and hash.

Correct the previous diagnostic residual-plot direction/label mismatch from saved data and assert that expected-upper samples are nonempty. This is a plotting correction only; do not alter the measurement arrays or use an empty plot as evidence.

Use external bounded timeouts, flushed operation-start/end logs and partial output preservation for native work. Geometry/validation workers may use 900 seconds diagnostically; production timeout remains unchanged. Give any local source build its own declared finite budget and report a concrete build/dependency blocker rather than changing the production environment.

Do not rerun unrelated UI suites or optimize section extraction in this task. Original artifacts, input fixtures, production source/runtime and `00_research_archive` remain unchanged. Keep diagnostic build costs separate from geometry runtime.

The original job remains FAILED, retained complete validation remains FAIL, and external NASA fidelity remains UNVERIFIED. Any isolated candidate result is new evidence, not retroactive success or production deployment.

## Final instruction

Execute the applicable steps, not planning alone. The user does not need to re-enter or modify any parameters.

Open the final report with four direct answers:

1. Is the profile already wrong BEFORE positioning?
2. Is the positioned rib in the plane BladeGen promises, and what transformation explains any difference?
3. Does the surface preserve the supplied ribs, and why do its physical cuts disagree?
4. What causal check/correction was tested, or what precise evidence blocks one?

The goal is to move from “the live surface differs” to a demonstrated mechanism and a justified product decision, without replacing the engineer's request with a shape that merely passes a different test.
