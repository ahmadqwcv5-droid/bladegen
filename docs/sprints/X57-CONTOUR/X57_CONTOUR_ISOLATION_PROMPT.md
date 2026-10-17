# X-57 — Isolate the Contour Discrepancy Before Changing Production Code

Repository: https://github.com/ahmadqwcv5-droid/bladegen

## Mission

Continue the existing X-57 investigation. Determine whether the reported inboard contour discrepancy originates in the generated geometry, the expected-profile construction/coordinate conventions, or the measurement representation and distance calculation.

This is a bounded diagnostic task, not a new feature sprint and not an instruction to “fix the loft.” Do not assume either the generator or the validator is correct merely because previous tests passed.

Use the retained CAD and the actual submitted BladeSpec. Produce reproducible geometric evidence, then recommend the smallest justified correction. Do not implement a production correction during this task.

## 1. Established facts and evidence identity

Failed product job:
`a93b281c29b640afaa6bad698d64a61b`

Retained `blade_solid.step` SHA-256:
`43c2cd72bebcd3949e0fe0b210aaac9ccbf6918952743fd109ecb0cac2e401d6`

The completed diagnostic reported:
- One valid closed solid, one shell, six faces, zero non-degenerate free edges.
- All 41 planned stations completed.
- All stations passed chord, twist, reference-axis, TE and wire checks.
- Seven stations failed only contour gates.
- Worst station: requested/sampled r/R = 0.22302.
- Worst RMS/P95/sampled maximum: 0.253757227408 / 0.503101705327 / 0.523742097408 mm.
- Production section measurement took 310.984923051 seconds; OCP section extraction accounted for 295.244370509 seconds.
- External NASA geometry fidelity remains UNVERIFIED.

Last recorded HEAD was `1cdb564a2eb92b0171acbab705b41ca63b57416c`, with a dirty worktree. Inspect actual HEAD and local files; do not reset or check out that revision over existing work.

Read the existing:
- X57_VALIDATION_DIAGNOSIS.md
- diagnostic_summary.json
- completed_measurements.json
- validation_timings.csv
- diagnostic.log
- scripts/diagnose_x57_validation.py
- Retained job BladeSpec, resolved definition, CAD and logs.
- Exported candidate and immutable X-57 fixtures.

Use `output/runs/<job_id>/` and the recorded `docs/evidence/sprint04b/x57/` paths. Locate artifacts by their manifests and hashes, not by choosing a convenient file with the same name.

Record input hashes, actual HEAD, dirty diff identity, relevant source hashes, runtime versions, exact commands, and present/missing intermediate artifacts. Use the same JSON canonicalization method when comparing canonical hashes. Stop on a retained-STEP hash mismatch.

Create a uniquely named diagnostic output directory. Preserve the original failed job, its status, and all previous evidence. Do not create or overwrite an official product validation.json in that job.

## 2. Strict boundary for this investigation

Allowed:
- Read-only inspection of retained CAD, specifications, source code and intermediate files.
- Diagnostic scripts, tests, exact section-wire exports, coordinate tables and data-derived plots in a separate directory.
- Reuse of extracted sections within this diagnostic, keyed by STEP hash, exact plane and extraction settings.

Not allowed:
- Changing production generator, validator, policies, or timeout configuration.
- Changing airfoil coordinates, thickness, TE, radial controls, interpolation, root/tip treatment, or engineering tolerances.
- Repairing, simplifying, refitting, or regenerating the retained blade.
- Starting a new UI build or launching OpenVSP in the initial investigation.
- Reducing the final 41-station acceptance plan or declaring full acceptance from a diagnostic subset.
- Using STL as the authoritative geometry reference.
- Writing X-57-specific compensation into production code.
- Modifying 00_research_archive, committing, or merging automatically.

Loading a saved VSP3 can recompute geometry. Do not describe such a recomputation as inspection of a frozen pre-export surface. If that later becomes necessary, identify it as a proposed separate controlled experiment and stop for review first.

## 3. Reproduce three selected stations, not another full blind run

Start with these exact requested/sampled radii:

| r/R | Diagnostic role | Recorded RMS/P95/max mm |
| --- | --- | --- |
| 0.22302 | Worst failure | 0.253757227408 / 0.503101705327 / 0.523742097408 |
| 0.29061 | Passing station within the affected inboard region | 0.0193048321053 / 0.0323074200908 / 0.0362918307779 |
| 0.50345 | Passing station farther outboard | 0.00742495986712 / 0.0125984810839 / 0.0144823624182 |

Use the same production section plane, expected-profile preparation, sampling, and metrics to reproduce their recorded results first. Locate the actual functions in `measure_sections.py`, `expected_geometry.py`, and associated modules; do not replace this baseline with a new checker.

Capture the expected contour and actual section geometry at the production call boundaries. A separate diagnostic runner may select these stations, but must not edit the production station-plan implementation or claim that this subset replaces full validation.

Read STEP once where possible and extract each selected plane once. Preserve the exact resulting wires/edges so repeated distance and sampling experiments do not unnecessarily repeat expensive intersections. Record any export/re-import error in diagnostic section files.

For every station save:
- Plane origin/normal, physical position, requested and sampled r/R.
- Exact section wire/edges in a BRep diagnostic file.
- Original production sample coordinates with order/edge identifiers.
- Expected contour coordinates before and after 3D placement.
- Chord, twist, reference axis, TE, and contour metrics.
- Difference from the previously recorded results and timing.

If baseline reproduction differs materially, investigate identity, versions or measurement settings before attributing a new cause. Do not overwrite the earlier measurements.

Important endpoint fact: requested root 0.20238 was sampled at 0.207365125; tip 1.0 was sampled at 0.9995014875. If these endpoints are inspected later, compare expected and actual at the same sampled location and retain the distinction in labels.

## 4. Audit the reference and coordinate frame independently

Establish exactly what “expected contour” means under the current BladeSpec contract.

Trace and record:
- Embedded input upper/lower coordinates.
- Canonical profile preparation and any documented normalization, thickness or TE operation.
- Resampling and interpolation between the two airfoil stations.
- Evaluated chord/twist/rake/skew/thickness at each selected radius.
- Reference-axis placement, rotation signs, origin, and local/global units.

Do not infer expected geometry from the measured STEP output or fit its dimensions to manufacture agreement.

Construct a small independent expected-profile audit from the documented input semantics. It may use the same numerical libraries, but must not simply call the production expected-contour helper and label its return value independent.

The submitted definition uses the same embedded coordinate profile at the two endpoint stations, constant thickness, and TE=0. Verify that equality from the actual file. Test whether interpolation preserves an identical prepared profile in this case. If another documented operation changes it, isolate and quantify that operation rather than assuming identity automatically.

Place both actual and expected curves in ONE common frame derived from the requested geometry. Preserve absolute mm coordinates for the principal comparison. For normalized diagnostic displays, use the same requested chord and origin for both curves.

Do not separately normalize each curve with its measured chord or best-fit transform and then present the smaller residual as absolute geometry accuracy.

Investigate the approximately -0.031-degree measured-minus-requested twist pattern as a hypothesis, not a proven cause. Check the original coordinate profile's LE-to-TE datum against its nominal local x-axis and quantify any predicted angular/positional effect under the actual convention. Do not subtract an empirically fitted offset from inputs.

Keep source-native versus product thickness representation differences separate. Quantify their possible contribution rather than assuming they explain the inboard error.

## 5. Audit distances and sampling with a genuinely separate calculation

Keep the production RMS/P95/max output unchanged as the baseline.

Implement at least one diagnostic distance computation that does not call the existing `symmetric_distances` helper. Examples include robust point-to-trimmed-curve projection or an independently implemented point-to-segment distance against converged contour approximations.

Requirements:
- Measure actual-to-expected AND expected-to-actual directions.
- Document how each aggregate is calculated, its weighting and sample counts.
- Respect trimmed edge domains, edge orientation, shared endpoints, closure, upper/lower surfaces and zero-length entities.
- Do not match point i to point i across differently parameterized curves.
- Do not claim a nearest-point-to-point result is an exact continuous curve distance.
- Label a sampled maximum as sampled; do not call it an exact continuous Hausdorff bound without supporting analysis.
- Compare baseline density, 2x and 4x diagnostic density, preferably with geometric arc-length sampling. Report convergence or lack of convergence.
- Keep diagnostic sampling changes separate from production policy; do not select a density simply because it lowers the error.

Test the independent metric with a small self-test set:
- Identical contour against itself.
- Same geometric contour with reversed traversal or shifted start point.
- Same contour sampled at different densities, accounting for discretization error.
- A controlled synthetic perturbation with an independently checkable distance.

A successful self-test is not proof of CAD fidelity, but prevents an unqualified new metric from becoming the new source of truth.

If production and independent metrics disagree, locate the specific representation, weighting or algorithm step. “The alternative gives a smaller number” is not a sufficient diagnosis.

## 6. Produce visible geometric evidence

For each of the three stations produce data-derived figures:

1. Actual versus expected contour overlay in the shared requested frame, with equal aspect ratio and labelled units.
2. Clearly labelled leading-edge, mid-chord or trailing-edge close-ups where the discrepancy occurs.
3. Residual-distance plot along a documented contour coordinate, including both distance directions where useful.
4. Thickness/camber comparison when the curve split and definition support it.

Show a full contour at true relative scale before any enlarged residual display. Clearly label amplification and additional diagnostic registration.

Mark where the largest discrepancies occur and export their coordinates. Do not provide only a full-blade screenshot or repeat the summary statistics.

Thickness/camber audit must state its chord datum and upper/lower pairing method. Do not force multivalued geometry into a single-valued curve or silently omit ambiguous intersections.

If a rigid registration is useful diagnostically, report the transform and the BEFORE/AFTER residuals separately. No scaling, shearing or nonrigid fitting. Registered agreement does not erase a placement error in the principal comparison.

## 7. Locate the first demonstrated divergence using retained stages

Inventory and compare available evidence along this sequence:

Input coordinates
→ canonical resolved profile
→ data supplied to the backend adapter
→ retained backend geometry, if genuinely available
→ raw exported OpenVSP STEP
→ OCP-final solid STEP
→ extracted section and production sampled representation
→ expected-profile/distance calculation.

Use only artifacts whose identity belongs to the failed job. Record missing stages explicitly; do not substitute earlier research or reference-model exports.

If the matching raw OpenVSP STEP exists, cut the same physical planes and compare it with the retained final solid. This tests whether the finalization stage introduced the discrepancy; it does not independently certify the original generated surface.

Do not identify a native surface parameter with r/R without proving the mapping. If a parameter-space iso-curve is not on the same physical section plane, it is not a valid substitute for the comparison.

Do not assert that sewing/export cannot change the result based only on what those operations are intended to do. Use measured stage comparisons where evidence is available.

If the last known matching stage and first known mismatching stage enclose an unobserved operation, report that interval. Do not claim a specific internal cause without evidence.

When essential intermediate geometry is absent, identify one smallest proposed controlled experiment. Do not silently regenerate a blade or reload/recompute an OpenVSP model to fill the gap in this read-only task.

## 8. Evidence-based conclusion and bounded stop

The final report must distinguish:
- Reproduced production contour failure.
- Independent measurement findings.
- Expected-profile/convention findings.
- Earliest demonstrated divergence or remaining localization interval.
- Confirmed causes, rejected hypotheses, and unresolved hypotheses.

Possible outcomes include actual geometry discrepancy, expected-reference defect, sampling/distance defect, multiple causes, or a localized but unresolved discrepancy. Do not force one conclusion for the sake of closure.

A claimed cause must explain the failing station and be consistent with the passing controls. Where useful, a small isolated counterexample or diagnostic-only A/B calculation can support causality. Do not modify production source to perform it.

If the initial three stations establish a consistent mechanism, confirm its spatial pattern using cached evidence or targeted cuts at the remaining failed locations:
0.207365125 (sampled root), 0.20949, 0.24183, 0.26472, 0.31863, 0.34811.
Do not require repeated full 41-station runs before this localization is understood.

Propose the smallest general correction and the regression test it would require. Do not implement that correction, performance changes, timeout changes or a new end-to-end UI build in this task.

The existing 94.94% extraction cost is a separate confirmed performance issue. Preserve its evidence; correctness localization takes priority here.

## 9. Deliverables and reporting

Provide one reviewable evidence directory and ZIP containing:
- X57_CONTOUR_ISOLATION_REPORT.md
- contour_isolation_summary.json
- station_comparison.csv
- metric_self_tests.json
- source_stage_matrix.csv (including missing stages)
- Per-station expected/actual CSV coordinates and exact section wires.
- Actual-versus-expected overlays and residual plots.
- Diagnostic source, commands, logs, hashes, and timings.

Do not duplicate the entire large blade STEP in the ZIP if its retained path and verified hash identify it reliably. Include small extracted section evidence where practical.

Use bounded external timeouts with partial-log preservation for native calls. A timeout or missing artifact is a limitation, not permission to reduce correctness checks.

Before finishing, recheck that retained artifacts and production source hashes are unchanged. Report actual Git state and version identity.

Keep these conclusions separate:
- Input fidelity: previously passed, not retested by manual entry.
- Original product job: still failed.
- Existing complete internal validator: FAIL unless/until separately revised and requalified in a future task.
- This task: diagnostic completion/localization, not a new CAD acceptance PASS.
- External NASA fidelity: UNVERIFIED; no external comparison is requested here.

## Final instruction

Execute this investigation, not just a plan. Start with the retained STEP and the three selected stations. Return the contour evidence and the smallest justified next action.

The desired answer is not “six faces are valid” or “increase the timeout.” It is: where do the actual and requested section shapes first diverge, which measurement independently confirms it, and what narrowly scoped general correction should be tested next?
