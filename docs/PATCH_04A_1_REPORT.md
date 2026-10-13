# Patch 04A.1 — Assembly Validation, Result Clarity, and Project Save/Open

> **Patch 04A.2 correction:** The 04A.1 browser report called a second page in
> the same browser context a “fresh browser session,” and its generic result
> helper could observe an older successful result while a newer identical build
> was running. Patch 04A.2 preserves the historical measurements below but
> strengthens the proof with `browser.newContext()`, complete job IDs, exact-job
> polling, artifact ownership checks, and adversarial stale-result tests. See
> [the Patch 04A.2 report](PATCH_04A_2_REPORT.md).

## Outcome

Patch 04A.1 is a **PASS**. It preserves the Sprint 04A assembly engine and
single-blade geometry pipeline while closing four product-workflow gaps:

1. dynamic, actionable nominal hub/root guidance;
2. separate current-draft, active-generation, and historical-result state;
3. one early runtime blade-count capability policy; and
4. atomic, complete BladeSpec/PropellerSpec save/open behavior.

The implementation is on branch
patch/04a.1-assembly-validation-project-io, based on reviewed Sprint 04A merge
2b8d43eda89460409c5deaa24698e7b5c171ba2f. It has not been merged into main.
No path under 00_research_archive changed.

## Dynamic preflight and structured issues

The unchanged conservative nominal policy is:

~~~text
root_radius_mm = diameter_mm / 2 × root_radius_ratio
hub_radius_mm  = hub_diameter_mm / 2
require hub_radius_mm > root_radius_mm
~~~

For the 400 mm, root r/R 0.20 blade, a 60 mm hub reports root radius 40 mm,
hub radius 30 mm, radial gap 10 mm, and an exclusive required diameter bound
greater than 80 mm. An 80 mm hub is rejected; 81 mm passes only nominal
preflight. At 600 mm blade diameter the bound changes to 120 mm. Hub length is
reported as axial extent and is not used to disguise a radial gap.

The propeller preflight returns stable field-level issues. Covered codes include
hub_root_nominal_overlap_required, bore_smaller_than_hub_required,
positive_dimension_required, finite_number_required, blade_count_invalid,
blade_count_unsupported, and invalid_blade_spec. API failures retain a readable
detail string and add an issues array; Pydantic input dictionaries,
documentation URLs, internal paths, and stack traces are not exposed as the
normal operator message.

## Shared runtime capability

The assembly capabilities module is lightweight and has no OCP, FastAPI, or
React dependency. It keeps the contract range 2–8 distinct from the qualified
runtime tuple 2, 3, 4. The same tuple is enforced by:

- API validate and build submission;
- CLI/propeller pipeline before output creation and reference-blade generation;
- assembly builder as a defensive final gate; and
- frontend controls loaded from GET /api/propellers/capabilities.

Counts 5–8 therefore return “unsupported in this release” before queueing,
OpenVSP, or reference-blade construction. They are not described as
geometrically impossible.

## Result identity and validation revisions

The UI now presents three independent concepts:

- current design: modified, checking, checks passed, or checks failed;
- active generation: queued, running, or failed, with its job ID; and
- last successful result: completed job ID, submitted snapshot, artifacts, and
  whether it still matches current inputs.

Rejecting a new 60 × 30 mm draft displays “Current inputs are invalid. No new
CAD build was started.” while retaining and labeling the old result “Last
successful build — previous inputs.” Completed 100% progress is no longer shown
as if it belonged to the rejected request. Geometric build failures remain
separate from input-validation failures.

Every asynchronous validation captures a revision token and exact design
snapshot. Edits invalidate the token, so a delayed response cannot validate a
newer draft, clear its errors, change inputs, or enqueue a build.

## Complete project save/open

Open JSON identifies document type from structure rather than schema text:

- BladeSpec opens in Single Blade mode.
- PropellerSpec v0.1 opens in Full Propeller mode and restores the top-level
  name, complete nested blade, all assembly values, airfoil coordinates,
  distribution grids/interpolations, precise values, overrides, and physical
  trailing-edge requirements.

Import is parse → identify → backend validate → atomic replace. Ambiguous,
incomplete, unsupported, extra-field, or invalid documents preserve the current
project and report a separate import failure without falsely marking the
unchanged design invalid. Reset restores the complete successful import, new,
or example baseline. Mode switches preserve assembly settings. Export contains
no frontend row IDs or transient UI state.

## Real 2-blade 90 × 30 mm acceptance

The reproducible input is
examples/propeller_two_blade_hub_90x30.json: diameter 400 mm, root r/R 0.20,
2 blades, hub 90 × 30 mm, bore 12 mm, and azimuth 0°.

The independent CLI path completed with PASS. Measurements after authoritative
STEP export and re-import were:

| Measurement | Result |
| --- | ---: |
| Actual placements / azimuths | 2 / 0°, 180° |
| Root/hub common volume | 1381.2065006890, 1381.2065006898 mm³ |
| Outside-hub blade collision | 0.0 mm³ |
| Final solids / shells / faces | 1 / 1 / 20 |
| Closed shell / BRep valid | true / true |
| Non-degenerate free edges | 0 |
| Through-bore radius / residual material | 6.0 mm / 0.0 mm³ |
| Surface area | 54132.84047780774 mm² |
| Adaptive volume | 261815.11278796682 mm³ |
| Bounding-box extent | 50.5737750189 × 400.0432202905 × 90.0000002 mm |
| STEP round-trip volume delta | 3.92028596252203e-8 mm³ |
| STEP round-trip bbox max delta | 7.440803528879769e-11 mm |

The inherited reference blade again passed its existing geometry policy:
maximum chord error 0.00404325 mm, maximum twist error 0.00159128°, maximum
reference-axis error 0.00452557 mm, control contour RMS/P95/max
0.01474434/0.02971030/0.03397422 mm, and maximum TE error 0.01673208 mm.
No blade geometry, assembly Boolean tolerance, overlap gate, collision gate,
bore gate, or STEP topology gate was weakened.

## Browser workflow and evidence

The live Playwright workflow performed:

~~~text
Load example → Full Propeller → successful 90×30 result A
→ edit to 60×30 → reject without build → retain A as historical
→ restore 90×30 → successful result B → export PropellerSpec
→ fresh browser session → import → verify all assembly identity
→ rebuild and validate
~~~

It issued exactly three build requests; the invalid 60 × 30 action issued none.
The workflow passed in 5.2 minutes using the real FastAPI worker,
OpenVSP 3.54.0, OCP Booleans, STEP re-import, and validation artifacts.

- [Initial 90×30 result](screenshots/patch04a1/assembly_a_90x30_success.png)
- [Rejected 60×30 draft with historical result](screenshots/patch04a1/invalid_60x30_historical_result.png)
- [Restored 90×30 result](screenshots/patch04a1/assembly_b_90x30_success.png)
- [Fresh-session import and rebuild](screenshots/patch04a1/fresh_session_import_rebuild.png)

## Verification

- Backend non-integration: **135 passed**, 11 integration tests deselected, one
  existing Starlette deprecation warning, in 43.66 s.
- Focused real 90×30 integration: **1 passed** in 60.03 s.
- Frontend: **22 files, 116 tests passed**.
- TypeScript/Vite production build: passed; 43 modules transformed. The existing
  large-chunk advisory remains.
- Backend Ruff: passed.
- Real 90×30 Playwright workflow: **1 passed** in 5.2 min.

Executed verification commands:

~~~bash
source scripts/openvsp_env.sh
.venv/bin/python -m bladegen.cli build-propeller \
  examples/propeller_two_blade_hub_90x30.json \
  --output output/runs/patch04a1_cli_90x30

.venv/bin/pytest backend/tests/test_propeller_assembly_acceptance.py::test_real_two_blade_90_by_30_regression -q
cd backend
../.venv/bin/pytest -m 'not integration' -q
../.venv/bin/ruff check bladegen api tests
cd ../frontend
npm test -- --run
npm run build
npm run test:e2e -- patch04a1.spec.ts
~~~

Generated CAD remains under the ignored output/runs area; source control
contains the neutral input, tests, report, and browser evidence.

## Remaining limitations

- Counts 5–8 remain representable by the neutral versioned contract but are not
  runtime-qualified and cannot be queued in this release.
- Nominal hub/root preflight does not certify Boolean success, connection
  strength, fatigue life, balance, or manufacturability.
- Spinner, fillets, keyways, bolt holes, flanges, advanced root fairings,
  per-blade pitch/geometry, and aero/structural analysis remain out of scope.
- The installed OpenVSP workflow is qualified on Linux; Windows and macOS still
  need separate runtime packaging and acceptance.
- The Vite production build retains its existing large-chunk advisory, and the
  backend suite retains one existing Starlette/httpx deprecation warning.
