# FP02-C1 qualification closure report

Decision: **FP02_READY_FOR_USER_TRIAL** under the existing Level 1 trial
launcher and 900-second per-design profile.

Run ID: `fp02_c1_20261015T075331Z`  
Branch: `patch/fp02-c1-thickness-te-qualification`  
Base HEAD: `39ffb7229c834d9c1e19eab03b529a83f1e366a3`  
Worktree: dirty; no commit, merge, push, reset, clean, or stash was performed.

## 1. Q02/Q03 cause and correction

Q02 and Q03 CAD was correct for the submitted definitions. The independent
expected-contour calculation was not: between explicit airfoil stations it
linearly blended the two already-resolved control profiles but omitted the
independent PCHIP Thickness curve's post-blend scale. That made both the full
expected contour and its finite trailing edge too thick.

The unchanged contract is now evaluated in this order:

1. build each control profile, including its physical TE;
2. linearly interpolate the neighboring profiles by radial station fraction;
3. independently evaluate the declared Thickness curve at that station;
4. scale chord-normal half-thickness about the camber line by
   `target_thickness / blended_control_thickness`.

This is an expected-geometry correction only. It does not alter generation,
BladeSpec inputs, tolerances, station plans, contour sampling, caps, STEP export,
or the managed native runtime.

| r/R | Linear profile ratio | PCHIP target | Scale | Old expected TE mm | Corrected expected TE mm | Measured TE mm |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.30 | 0.135000000 | 0.129375000 | 0.958333333 | 1.112945566 | 1.066572834 | 1.065325229 |
| 0.35 | 0.127500000 | 0.122578125 | 0.961397059 | 1.062543377 | 1.021526077 | 1.020362858 |

The retained Q02 section at 0.30 changed from independent 5000-point/edge
legacy RMS/P95/sampled-max 0.116397/0.197839/0.199274 mm to
0.006222/0.012065/0.017607 mm. At 0.35 it changed from
0.100591/0.170809/0.172261 mm to 0.005409/0.010461/0.015070 mm. Q03 reproduced
the same mechanism. Passing controls at 0.40 and 0.50 had scale 1 and remained
unchanged.

Further proof:

- frozen Q02/Q03 submitted, canonical, resolved, and STEP evidence was retained;
- old production failures were reproduced to sub-0.001 mm diagnostic deltas;
- overlays, TE close-ups, CSVs and section BRePs use the same physical planes;
- revalidation of the immutable old STEPs passed 11/11 with the corrected
  reference, but the old jobs remain failed and were not relabeled;
- fresh normal-pipeline Q02 and Q03 passed 11/11;
- an analytical regression checks the PCHIP scale and TE equation, while a
  deliberately unscaled contour remains rejected by the original gates.

The detailed contract table is
`qualification/fp02_c1/fp02_c1_20261015T075331Z/diagnostics/contract_operation_table.md`.

## 2. Q04.R1 and Reverse measurement

Q04.R1 is the approved versioned positive fixture, not a retroactive change to
Q04. All eight profiles were proven byte-canonically identical: 74 upper and 67
lower points, one coordinate-profile SHA-256, and full-precision natural
thickness `0.1305533776828919` under the existing 2001-sample canonical policy.

Only these fields changed:

- name: `FP02_Q04_imported_coordinates_eight_station` to
  `FP02_Q04_R1_coordinate_authority`;
- the eight existing Thickness control values, formerly
  `0.15, 0.12, 0.12, 0.12, 0.10, 0.09, 0.08, 0.08`, to the same full-precision
  natural ratio `0.1305533776828919`.

Coordinates/order, profile assignments, eight nonuniform radii, all grids and
interpolations, Chord/Twist/Rake/Skew, TE inputs, globals, reference axis and
Reverse direction are unchanged. A 10,001-sample domain check found zero
Thickness compatibility error. The frozen pre-CAD file SHA-256 is
`e5e1f8510993af7bb6a5f171d67ca1b64b80a5970413aaca18f6a7f90cb25b03`.

The first fresh Q04.R1 CAD run produced a valid solid but exposed a second,
bounded validator defect: the expected section frame and twist extraction still
assumed Normal direction. The native Reverse contract reflects only the global
tangential Z coordinate while leaving BladeSpec curve semantics unchanged.
The expected reference/chord/normal vectors now apply `[1, -1]`, and measured
Reverse twist uses `90 + atan2(z, x)`. The first run remains retained as a failed
diagnostic; revalidation after the correction passed 26/26, and the final fresh
matrix run also passed 26/26.

Original Q04 remains rejected with HTTP 422 before CAD queueing. Both component
and real-browser tests verify the field-specific 0.150000/0.130553 conflict and
no build operation.

## 3. Final qualification

The revised manifest SHA-256 is
`5219c3092377148c708927ccfde9d3ced82337fcdb4a89e65a23a6de4862b8c0`.
The fresh matrix passed 8/8 in 819.346 seconds with zero failures. Every final
artifact re-imported as one valid closed solid with one shell and zero free
edges. See `docs/FP02_C1_ACCEPTANCE_MATRIX.md` for per-job metrics.

The full supported browser command was run from `frontend` with one worker and
no retries:

```bash
FP02_EVIDENCE_RUN_ID=fp02_c1_consolidated_20261015T0905Z \
FP02_EVIDENCE_ROOT=../qualification/fp02_c1/fp02_c1_20261015T075331Z/verification/browser_consolidated \
npx playwright test --config=playwright.fp02.config.ts --workers=1 --retries=0
```

Result: 16/16 expected, 0 unexpected, 0 skipped, 0 flaky/retried; Playwright
duration 2346.347 seconds and `/usr/bin/time` wall duration 2346.93 seconds.
The suite retained:

- U1 isolated save/open, explicit 18° to 21° Twist edit, new Job ID, measured
  3.000000000002° delta, and a supported two-blade assembly;
- U2 real X-57 airfoil/distribution CSV import, 20 warm Apply/Undo cycles,
  candidate fidelity, explicit generation, 41/41 validation and same-job
  downloads;
- focused real-UI Q02 generation, original Q04 rejection/no build, and Q04.R1
  Reverse generation at 26/26 stations.

Backend: 197/197 tests passed, none failed/skipped, in 572.73 seconds. Frontend:
160/160 tests in 51/51 suites passed and the production build passed. Six
changed FP02-C1 Python files passed Ruff check and format; the launcher passed
`bash -n`. The repo-wide format check still reports 13 historical files and the
Vite build retains its existing chunk-size warning. Neither affects the
qualified correction, and executable files were not reformatted after the
candidate was frozen.

## 4. X-57 browser result and qualification boundary

The final browser X-57 job was `9976a8fa2edd4e0896f17a102cfc7cfe` and completed
in 381.7 worker seconds under the 900-second profile. It passed 41/41 sections;
the re-imported STEP has one solid, one closed shell, zero free edges, valid
BRep, area 22,170.680497 mm² and volume 46,373.243510 mm³. Candidate, submitted
and generated specifications were canonically equivalent.

Input fidelity passed: all 282 imported coordinate pairs were exact; all 40
Chord/Twist/Rake/Skew rows matched their documented physical conversions; warm
Apply-to-current-preview p95 was 435.715 ms. The source native thickness ratio
0.1305067267946498 and product coordinate-measurement ratio
0.1305533776828919 remain separately documented; this is a representation
difference, not silently equated data.

External NASA geometry fidelity remains **UNVERIFIED**. The supplied bundle did
not contain official NASA VSP3/STEP geometry for a surface comparison. Internal
input and CAD PASS is not presented as external fidelity.

The browser STEP is supplied separately at
`qualification/fp02_c1/artifacts/x57_hlp_final_browser.step`, SHA-256
`a50dfbff9da673bdabde10b48b33d5dbbf89b66b3435788b55c690d507cb5974`.

## 5. Identity, evidence and handoff

Runtime identity is unchanged:

- OpenVSP `3.54.0`, build `openvsp-3.54.0-bladegen-fixed-plane.1`;
- contract `bladegen.fixed-radial-sections.v1`;
- fingerprint `af69cfbeb477880fd7caf13c3fbdef3a2f69f40430dafe4e5a330d9bb7836edd`;
- native patch SHA-256
  `0dd6f87b867ccaeb6518f8f01f7093e4e1a05f02d0c5a268c66cc1d157ed71d3`;
- validator revision `bladegen.final-step-validation.3`;
- Python 3.12.3, OCP 7.9.3.1, NumPy 2.5.3, SciPy 1.18.1.

The candidate is identified by the immutable base HEAD plus dirty worktree
source manifests, not described as a clean tested commit. The executable
production source-set aggregate is
`d39ad693843ce8c317d7c0fd7812a98029ace8f6282bfb766518c77e75dfddd4`.

Run the user trial from the repository root:

```bash
./scripts/start_level1_trial.sh
```

This selects the qualified 900-second Level 1 profile. The ordinary 300-second
default remains unqualified for X-57. User hands-on acceptance remains
**PENDING** until the user completes the trial.

Packages:

- `qualification/fp02_c1/FP02_C1_LEVEL1_TRIAL_INPUTS.zip`;
- `qualification/fp02_c1/FP02_C1_COMPACT_EVIDENCE.zip`;
- `qualification/fp02_c1/SHA256SUMS.txt`.

The compact ZIP omits large full STEP/VSP3/STL files, Playwright traces, the
browser X-57 STEP, and the full matrix job trees. Their exact durable paths and
hashes are listed in the report/decision summary. Small section BRePs, CSVs,
plots, original definitions, Q04.R1, manifests and machine-readable results are
included.

