# PATCH 04A.2 — Semantic Preflight & Job-Scoped Verification

Repository:
https://github.com/ahmadqwcv5-droid/bladegen

## Objective

Close the specific validation and test-evidence gaps found in the
independent audit of Patch 04A.1.

Preserve the working full-propeller workflow:
- Dynamic hub/root guidance.
- Structured validation issues.
- Qualified blade counts 2, 3, and 4.
- Complete BladeSpec/PropellerSpec project save/open/reset.
- Independent current-draft and historical-CAD state.
- Existing OpenVSP/OCP geometry generation.

This patch has four goals:

1. Reject inconsistent nested blade definitions before queueing CAD work.
2. Align omitted initial-azimuth handling with the existing model default.
3. Make browser acceptance prove completion of each NEW job.
4. Rerun and accurately report the relevant full regression suites.

This is a focused corrective patch, not a new feature sprint.

---

## 1. Preparation and scope

The last independently audited revision was:

8b7ab930289df1e66f2c4b34720644136aa93b41

Patch 04A.1 was merged through PR #11.
Inspect current HEAD and preserve any newer or uncommitted work.

Create a branch:

patch/04a.2-semantic-preflight-job-verification

Do not automatically merge into main.
Do not modify 00_research_archive.
Do not replace the existing application or geometry engine.

Review at minimum:

- backend/bladegen/validation/propeller_preflight.py
- backend/bladegen/assembly/capabilities.py
- backend/bladegen/models/blade_spec.py
- backend/bladegen/models/propeller_spec.py
- backend/bladegen/curves/resolver.py
- backend/bladegen/airfoils/canonical.py
- backend/bladegen/propeller_pipeline.py
- backend/api/routes/blades.py
- backend/api/routes/propellers.py
- frontend/src/editor/projectDocument.ts
- frontend/src/App.tsx
- frontend/src/Patch04A1.test.tsx
- frontend/e2e/patch04a1.spec.ts
- Existing preflight, project, API, CLI, and integration tests.

If available in the workspace, use the independent audit report and test
bundle as reproduction aids. Do not assume those files are already in
the repository.

---

# PART A — COMPLETE NON-CAD BLADE VALIDATION

## 2. Reproduce the semantic-preflight gap

The independent audit observed these requests returning:

HTTP 200
valid: true

through POST /api/propellers/validate:

Case A:
- Use an otherwise valid PropellerSpec.
- Keep NACA 4412 at an explicit airfoil station.
- Leave thickness_override_ratio absent or null.
- Set the coincident thickness_distribution control to 0.20.

Case B:
- Replace an airfoil with NACA 0000.
- Leave thickness_override_ratio absent or null.
- Keep a positive thickness distribution at that station.

These test cases concern compatibility with the existing canonical
airfoil rules. Do not invent a new general ban on NACA codes that the
current generator otherwise supports under valid conditions.

Current cause:

validate_propeller_payload() parses the Pydantic contract but does not
perform all the blade semantic checks already enforced later by
resolve_airfoil_sections() and the canonical blade pipeline.

This inconsistency can be detected without OpenVSP or OCP.

First add regression tests that reproduce the gap, then correct it.

## 3. Reuse existing engineering validation

After structural PropellerSpec validation, perform the existing non-CAD
blade semantic validation before:

- Reporting successful propeller input validation.
- Accepting a PropellerSpec import.
- Queueing a propeller build.
- Starting reference-blade generation from the CLI or Python pipeline.

Reuse the canonical blade implementation.

Acceptable approaches:

- Reuse a suitable existing canonical-resolution entrypoint; or
- Extract a small shared semantic validator from the existing resolution
  code and call it from both preflight and generation.

Do not copy NACA, thickness, TE, or interpolation mathematics into a
second implementation.

Do not make HTTP requests from one backend endpoint to another.

Do not introduce React/FastAPI dependencies into the engineering layer.

Avoid unnecessarily repeating expensive full adaptive resolution when a
shared, equivalent semantic check is sufficient. Document the chosen
boundary.

The semantic check must not:

- Launch OpenVSP.
- Construct OCP geometry.
- Write STEP/STL files.
- Create a CAD job.
- Modify the submitted blade definition.

Retain generation-time checks as defense in depth.

## 4. Preserve existing engineering meaning

Use the current canonical rules and tolerances for:

- Nominal NACA thickness when no override exists.
- Explicit NACA thickness overrides.
- Imported coordinate-profile natural thickness.
- Supported mathematical airfoil definitions.
- Physical trailing-edge requirements.
- Canonical curve inputs required by the resolver.

Do not weaken existing rules to make invalid fixtures pass.

A valid explicit override must remain supported. For example:

NACA 4412
thickness_override_ratio = 0.20
matching thickness distribution = 0.20

must not be rejected merely because nominal NACA thickness is 0.12,
provided all existing engineering checks pass.

The imported-coordinate workflow must retain its existing natural-t/c
policy. Do not rescale embedded coordinates to hide a mismatch.

## 5. Structured errors and early rejection

Report semantic failures through the existing issue format.

Use a stable code such as:

invalid_blade_spec

Provide a useful field path and readable message identifying the
station or distribution involved.

Where the existing validator supplies reliable values, include relevant
context:
- Station r/R.
- Selected airfoil.
- Requested/evaluated thickness.
- Expected nominal or explicit thickness.

Do not invent context or infer it by fragile parsing of exception text
when structured information is available.

For invalid semantic inputs:

- /api/propellers/validate returns a controlled 422 response.
- /api/propellers/build returns a controlled 422 response.
- jobs.submit is not called.
- No new job ID is returned.
- CLI/Python entrypoints reject before reference-blade generation.
- Import preserves the current project unchanged.

Keep error messages free of raw Pydantic input dictionaries, internal
paths, and stack traces.

## 6. Preserve the limits of preflight

A passed preflight means:

"Input structure and non-CAD engineering consistency checks passed."

It does not mean:

"The final propeller has already passed CAD qualification."

Actual hub overlap, blade collisions, Boolean fusion, bore clearance,
and final STEP topology remain build-time checks.

Keep the existing exclusive nominal hub/root rule and supported-count
policy unchanged.

---

# PART B — INITIAL AZIMUTH DEFAULT CONSISTENCY

## 7. Align missing-field behavior

The existing AssemblySpec declares:

initial_azimuth_deg = 0.0

The audit found that omitting this field is accepted by the model but
rejected by the raw preflight and frontend project parser.

Preserve the existing contract default:

- Missing initial_azimuth_deg means 0.0 degrees.
- Explicit numeric zero remains zero.
- Explicit finite nonzero values remain unchanged.
- Explicit null, nonfinite values, and invalid types remain errors under
  the applicable input policy.

Do not use a broad fallback that silently converts every invalid value
to zero.

Do not introduce an unnecessary schema-version change.

Align:
- Raw preflight.
- PropellerSpec parsing.
- API validate/build.
- CLI/Python input handling.
- Frontend PropellerSpec import.
- Exported normalized project data.

Do not change requirements for unrelated mandatory fields.

## 8. Default-handling tests

Use otherwise identical supported PropellerSpecs:

A. initial_azimuth_deg omitted.
B. initial_azimuth_deg explicitly 0.
C. initial_azimuth_deg explicitly 17.5.
D. initial_azimuth_deg explicitly null.
E. An invalid nonnumeric value.

Verify A and B produce equivalent normalized engineering definitions.
Verify C retains 17.5.
Verify D and E fail clearly.

Exporting a successfully imported document may write the explicit
default 0.0. Compare semantic values, not JSON whitespace.

Preserve names, airfoils, distributions, assembly dimensions, and all
other project data.

---

# PART C — VERIFY THE NEW BUILD, NOT THE OLD RESULT

## 9. Correct the browser acceptance helper

Current waitForQualifiedResult() checks for:
- Assembly validation.
- PASS.
- A propeller_solid.step link.

These may belong to an older successful result while a new build runs,
especially when both requests use identical inputs.

Replace this with job-scoped verification.

Before clicking Generate:
- Register a listener for the correct build response.

After submission:
- Verify the expected accepted status.
- Capture the complete returned job_id.
- Wait for that exact job to reach succeeded.
- Fail promptly with diagnostics if that job reaches failed.
- Wait for the displayed result to be bound to that exact job_id.
- Verify artifact URLs belong to that job.

Do not consider these alone sufficient:
- A generic PASS.
- A visible Canvas.
- "Last successful build — current inputs."
- An old STEP download link.
- A build-request counter.

Keep the UI free to show the last successful result while a new job
runs. Strengthen the test rather than hiding useful historical results.

## 10. Bind evidence to actual artifacts

For each accepted browser build, obtain artifacts through:

GET /api/jobs/{captured_job_id}/artifacts

Verify the displayed STEP and validation links correspond to the
captured job.

Read that job's:
- propeller_spec.json
- validation.json

Assert:
- Submitted blade count.
- Hub diameter and length.
- Bore diameter.
- Initial azimuth.
- Project identity.
- Expected assembly validation status.

Use the actual response fields; do not invent report metadata.

A stable result-container data attribute is acceptable if it is bound
to the real displayedResult job identity.

Do not add fake test-only success state to the UI.

## 11. Add an adversarial result-identity test

Add a deterministic browser or integration test covering:

1. Successful result A is visible.
2. Build B starts with identical inputs and a different job ID.
3. B remains queued/running while A's PASS and links remain visible.
4. The new-job acceptance condition must remain unsatisfied.
5. B succeeds: only B's result and artifacts satisfy it.

Also test:
- B fails while A remains successful.
- A delayed response associated with A arrives after B becomes active.

Neither case may be mistaken for successful completion of B.

Controlled/mock responses are appropriate for these race-condition
tests, but not as a substitute for real CAD acceptance.

---

# PART D — GENUINELY ISOLATED SAVE/OPEN/REBUILD

## 12. Use a new browser context

The previous test used context.newPage(), which creates another page
inside the same browser context.

For the fresh-session acceptance scenario, use:

browser.newContext()

Do not copy storage state, cookies, or local/session storage from the
original context.

The same backend may remain running. Describe this accurately as an
isolated frontend session, not a backend restart or offline rebuild.

Export the complete PropellerSpec in context A.
Import only that downloaded document into context B.

Verify:
- Full Propeller mode.
- Top-level propeller name.
- Nested blade name and data.
- Blade count.
- Hub dimensions.
- Bore diameter.
- Initial azimuth.
- Embedded coordinate profiles where present.
- Independent distribution grids and interpolation choices.

Then explicitly generate result C and verify it by its NEW job ID.

Close the additional context cleanly.

## 13. Required real browser sequence

Use the accepted two-blade reference:

D = 400 mm
Root r/R = 0.20
Hub diameter = 90 mm
Hub length = 30 mm
Bore diameter = 12 mm

Execute:

Build A successfully
→ capture and verify job A
→ change hub diameter to 60 mm
→ reject without creating another job
→ retain A as historical
→ restore hub diameter to 90 mm
→ build B with a different job ID
→ wait for and verify B specifically
→ export PropellerSpec
→ open a new isolated browser context
→ import exported JSON
→ verify the restored complete project
→ build C
→ wait for and verify C specifically.

Add a separate semantic-invalid import/API scenario.
Do not mutate the accepted CAD fixture merely to demonstrate rejection.

---

# PART E — REGRESSION TEST PLAN

## 14. Backend semantic tests

Add tests using real shared validation code for:

1. NACA 4412 with no override and thickness 0.20:
   reject before queueing.

2. NACA 0000 with no override and a positive thickness curve:
   reject according to the established canonical rules.

3. NACA 4412 with explicit override 0.20 and matching curve:
   accept non-CAD validation when otherwise valid.

4. Explicit override and curve disagree:
   reject.

5. Imported coordinates and natural t/c disagree:
   reject using existing tolerances.

6. Valid imported-coordinate definition:
   accept without changing coordinates.

7. Omitted versus explicit-zero initial azimuth:
   equivalent normalized result.

8. Invalid hub/bore and unsupported counts 5–8:
   existing early-rejection behavior remains intact.

9. Direct /build invocation without first calling /validate:
   cannot bypass semantic checks.

10. CLI/direct Python pipeline:
    cannot bypass semantic checks.

Use spies/recording fakes only at the worker or CAD boundary to prove
that rejected requests never invoke jobs.submit or the reference-blade
builder.

Do not replace the semantic validator itself with a mock in the tests
intended to qualify semantic validation.

## 15. Frontend integration tests

Verify:

- Invalid PropellerSpec import preserves the current project.
- Valid import remains atomic.
- Omitted azimuth imports as zero.
- Structured semantic errors remain readable.
- Late validation responses cannot replace newer draft state.
- Old successful CAD remains correctly labeled during rejection.
- Job-scoped result identity remains correct.
- No validation/import action starts CAD automatically.

Preserve existing curve, airfoil, and assembly workflows.

## 16. Run the relevant full regression suites

Inspect existing project scripts and use the configured runtime.

Run:
- Backend non-integration tests.
- The complete existing CAD integration set.
- Frontend unit/component tests.
- Production TypeScript/Vite build.
- Ruff.
- The cross-sprint Playwright suite, including the strengthened workflow.

Preserve accepted CAD cases:
- Three-section blade.
- Five-section reference blade.
- Eight-section blade.
- NACA thickness override.
- Imported analytic airfoil.
- Existing two-, three-, and four-blade propellers.
- Two-blade 90×30 mm hub case.

Do not substitute one focused successful CAD test for the full requested
integration coverage.

Do not remove, weaken, or silently deselect failing tests.

If a known unrelated failure occurs, reproduce and document its baseline
status separately. Do not reopen unrelated curve-dragging work in this
patch or label an incomplete regression run as fully passed.

Report, separately for each suite:
- Collected.
- Passed.
- Failed.
- Skipped.
- Deselected.
- Execution command.
- Duration.
- Exact tested commit.

Avoid combining overlapping targeted and full-suite runs into an
inflated unique test count.

---

# PART F — CAD EVIDENCE

## 17. Preserve numerical and geometric behavior

No change to generated geometry is expected for already-valid inputs.

Do not modify:
- OpenVSP adapter behavior.
- OCP Boolean algorithms.
- Blade placement axis.
- Hub/bore construction.
- Overlap or collision tolerances.
- Chord, twist, TE, or contour tolerances.
- STEP topology requirements.

For the real 90×30 case, report measured results from the new run:
- Job ID and input specification.
- Solid/shell/face counts.
- Closed-shell and BRep status.
- Free-edge count.
- Root overlap and outside-hub collisions.
- Bore radius and residual material.
- Adaptive volume.
- STEP round-trip differences.

Compare against the accepted baseline using existing numerical
tolerances. Do not assert byte-identical STEP files or hard-code an old
reported volume as the new result.

Retain the exact new artifacts and checksums so they can be independently
reviewed. Never reuse older artifacts as evidence for a new job.

---

# PART G — DELIVERY AND ACCEPTANCE

## 18. Documentation

Create:

docs/PATCH_04A_2_REPORT.md
docs/PATCH_04A_2_ACCEPTANCE_MATRIX.md

Document:
- Reproduced semantic-preflight defects.
- Shared non-CAD validation implementation.
- Azimuth default policy.
- Job-scoped browser verification.
- New-context save/open/rebuild procedure.
- Actual test coverage and exclusions.
- New CAD evidence and artifact identities.
- Remaining limitations.

Update earlier reports with a short correction/addendum where needed.
Preserve historical results rather than rewriting them as though this
patch's stronger checks existed previously.

Report the actual branch and commit state at delivery.
Do not leave a stale "uncommitted/unmerged" statement if that is no
longer true.

## 19. Acceptance criteria

STRONG PASS requires:

- Known semantic inconsistencies are rejected before CAD queueing.
- Valid explicit thickness overrides remain supported.
- Imported-coordinate semantics remain unchanged.
- Omitted initial azimuth behaves consistently as zero.
- Invalid explicit azimuth values are not silently defaulted.
- Every browser build is verified against its own job ID and artifacts.
- An old PASS cannot satisfy a new-job acceptance condition.
- A failed new job cannot be masked by an older successful result.
- Save/open/rebuild succeeds in a genuinely separate browser context.
- Requested regression suites are executed and accurately reported.
- Valid baseline geometry remains within existing tolerances.
- No historical research files are modified.

If required behavior is unverified or fails, report PASS WITH LIMITATIONS
or FAIL as appropriate. Do not force a STRONG PASS classification.

---

## Strict scope control

Do not implement:
- New airfoil families or interpolation methods.
- Hub fillets, spinners, or mounting features.
- Aerodynamic or structural analysis.
- Additional supported blade counts.
- Desktop packaging.
- Database or frontend-framework replacement.
- Visual curve-editing redesign.
- New CAD engines.
- Broad application refactoring.

## Execution order

1. Reproduce the semantic and omitted-default cases.
2. Reuse/factor the shared non-CAD blade validation.
3. Align default handling.
4. Strengthen job identity and isolated-context browser tests.
5. Run the full requested regressions and new CAD acceptance.
6. Deliver evidence and a factual report.

Implement in the existing BladeGen workspace.
Do not stop after planning.
Do not automatically merge into main.

The goal is that "Input checks passed" includes the existing non-CAD
engineering rules, and "New build passed" is supported by the exact new
job and its measured artifacts.