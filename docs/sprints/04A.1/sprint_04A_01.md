# SPRINT 04A.1 — Assembly Validation, Result Clarity & Project Save/Open



## Mission

Correct the product-workflow gaps discovered after Sprint 04A without
rebuilding the propeller assembly engine.

The user successfully generated a propeller, then changed:
- Hub Diameter to 60 mm.
- Hub Length to 30 mm.

The current blade has Diameter = 400 mm and Root r/R = 0.20.
The existing nominal hub-root compatibility rule correctly rejected the
60 mm hub, but the UI presented a raw Pydantic error alongside the previous
successful job's 100% progress.

The user subsequently confirmed successful generation using:
- Hub Diameter = 90 mm.
- Hub Length = 30 mm.

Treat this as a useful additional regression scenario, not a universal
requirement for every blade.

Implement four corrections:

1. Actionable, dynamic assembly validation.
2. Clear separation between current inputs and previous build results.
3. Consistent early enforcement of supported blade counts.
4. Complete save/open support for both BladeSpec and PropellerSpec.

Continue developing the existing React/FastAPI/Python application.
Do not create a new application or implement desktop packaging.

---

## 1. Workspace preparation and scope

Inspect the current Git working tree and latest implementation.

The last reviewed Sprint 04A merge commit was:
2b8d43eda89460409c5deaa24698e7b5c171ba2f

Do not assume it is still the latest commit.

Create a branch:
patch/04a.1-assembly-validation-project-io

Preserve uncommitted user work.
Do not modify 00_research_archive.
Do not automatically merge into main.

Review at minimum:

- backend/bladegen/models/propeller_spec.py
- backend/bladegen/assembly/builder.py
- backend/bladegen/propeller_pipeline.py
- backend/bladegen/cli.py
- backend/api/routes/propellers.py
- backend/api/services/jobs.py
- frontend/src/App.tsx
- frontend/src/api/client.ts
- frontend/src/editor/bladespecEditor.ts
- frontend/src/components/BuildProgress.tsx
- frontend/src/types/bladespec.ts
- Existing Sprint 04A tests and examples.

Preserve the single-blade pipeline, X-axis assembly convention,
OpenVSP/OCP algorithms, and existing engineering tolerances.

---

## 2. Preserve the current hub-root policy

Do not silently remove or weaken the existing conservative nominal
compatibility check.

Its current requirement is:

R = blade_spec.diameter_mm / 2
root_radius_mm = R * blade_spec.root_radius_ratio
hub_radius_mm = assembly.hub_diameter_mm / 2

Require:
hub_radius_mm > root_radius_mm

Equivalently:
hub_diameter_mm >
    blade_spec.diameter_mm * blade_spec.root_radius_ratio

This is a nominal preflight rule for the current assembly implementation.
It is not a complete test of actual CAD overlap or connection strength.

Passing it does not guarantee Boolean success.
Actual positive-volume intersection, collision checks, fusion, bore
clearance, and final STEP validation must remain unchanged.

Do not:
- Hard-code 80 mm or 90 mm as a universal minimum.
- Automatically enlarge the hub.
- Move the blade root.
- Change chord, twist, or airfoil coordinates.
- Add connector geometry.
- Describe minimal Boolean overlap as structural certification.

Any future change from conservative nominal screening to a more permissive
geometry-based policy belongs to a separate engineering decision.

---

## 3. Show dynamic, useful hub guidance

Display a compact compatibility readout near the assembly inputs:

- Nominal blade root radius in mm.
- Current hub radius in mm.
- Nominal radial overlap or gap in mm.
- Required hub diameter under the current policy.

For the reported example, show information equivalent to:

"Hub diameter is too small for the current blade root.
Blade root radius: 40 mm.
Hub radius: 30 mm.
Nominal radial gap: 10 mm.
The current assembly policy requires a hub diameter greater than 80 mm."

State "greater than 80 mm", not "80 mm or greater".

Update the values when any relevant input changes, including:
- Propeller diameter.
- Root r/R.
- Hub diameter.

Explain that Hub Length controls axial extent and cannot by itself close
a radial gap.

Do not claim that 90 × 30 mm will work for every blade.
Do not reject a 30 mm hub length merely because older examples used 45 mm.

Perform inexpensive checks while editing without launching CAD or creating
a build job. Keep backend validation authoritative.

---

## 4. Return structured, user-facing validation issues

Replace raw exception dumps in the normal UI with useful field-level issues.

Provide stable issue codes and field paths. An issue may contain:

- code
- field
- message
- relevant numeric context
- comparison operator / bound, when applicable

Example:

code: hub_root_nominal_overlap_required
field: assembly.hub_diameter_mm
context:
  hub_diameter_mm: 60
  root_radius_mm: 40
  nominal_gap_mm: 10
  required_diameter_bound_mm: 80
  bound_is_exclusive: true

Keep an appropriate readable "detail" response for existing clients where
necessary, while adding structured issue data.

Do not show raw input_value dictionaries, Pydantic documentation URLs,
internal paths, or stack traces as the main user message.

Use the same error presentation for Validate Assembly and Generate Propeller.

Cover:
- Hub/root incompatibility.
- Bore diameter greater than or equal to hub diameter.
- Nonpositive or nonfinite dimensions.
- Invalid blade count.
- Unsupported runtime blade count.
- Invalid nested BladeSpec.

Geometric build failures must remain distinguishable from input errors.
For example, passing nominal checks but failing actual root overlap is a
geometry compatibility failure, not a schema parse error.

Preserve useful diagnostics in controlled logs.

---

## 5. Align supported blade counts before expensive work

The current neutral contract permits 2–8 blades, while the production
assembly builder is qualified for 2, 3, and 4.

Keep that distinction explicit and consistent.

Create or reuse one lightweight runtime capability policy, independent of
React, FastAPI, and OCP shape construction.

Use the same supported-count definition in:
- API preflight validation.
- API build submission.
- CLI/propeller pipeline preflight.
- Assembly builder defensive checks.
- Frontend assembly controls.

The build pipeline must reject unsupported counts BEFORE calling the
reference-blade generator.

For unsupported requests, do not:
- Create a queued CAD job through the API.
- Launch OpenVSP.
- Generate a reference blade only to reject assembly afterward.

Expose capabilities through a small API response or existing suitable
endpoint so the UI does not duplicate a hard-coded support list.

The UI may show 2, 3, and 4 as supported choices and explain that higher
counts are not qualified in this release.

Preserve the versioned PropellerSpec contract where possible; do not
claim that all structurally representable values are currently buildable.

Validation messages must distinguish:
"Unsupported in this release"
from:
"Geometrically impossible."

---

## 6. Separate current draft validity from build history

Correct the confusing combination in the user's screenshot:

"Active job succeeded / 100%"
and
"Input validation error"

Model these as separate concepts:

A. Current design
- Modified / not yet checked.
- Checking inputs.
- Input checks passed.
- Input checks failed.

B. Active generation
- Queued.
- Running.
- Failed.

C. Last completed result
- Its own job ID.
- Its submitted specification.
- Its artifacts and validation.
- Whether it still matches the current design.

Do not change a previously successful job to "failed" merely because the
new draft is invalid.

Do not relabel old CAD as if it represented rejected input.

When the current draft is invalid, show prominently:

"Current inputs are invalid. No new CAD build was started."

The previous result may remain visible, but label it:

"Last successful build — previous inputs."

A completed 100% indicator may remain in an explicitly historical result
panel or collapsed section, not as the apparent progress of the rejected
new request.

Preserve previous artifact access and existing stale-preview protection.

---

## 7. Keep validation responses revision-safe

Associate each validation attempt with the exact submitted design revision.

If the user edits dimensions while validation is pending:
- Ignore obsolete success/error responses.
- Do not clear errors for a newer invalid draft.
- Do not overwrite new inputs.
- Do not label the current design valid using an older response.

Input validation success means only the checks actually performed.
Before CAD generation, clearly state that final geometric qualification
has not yet run.

A known-invalid draft must not enqueue a build.

Preserve the existing backend-driven generation progress and the rule
that 100% requires confirmed job success.

---

## 8. Implement complete project save/open

The current UI can export PropellerSpec but its Open JSON path uses only
the BladeSpec parser. Correct this mismatch.

Support both documents:

A. BladeSpec
- Opens in Single Blade mode.
- Preserves current backward-compatible supported versions.

B. PropellerSpec v0.1
- Opens in Full Propeller mode.
- Restores the complete nested BladeSpec.
- Restores every assembly parameter.
- Preserves the top-level propeller name and units.

Do not identify document type from schema_version alone.
BladeSpec and PropellerSpec can share version text.

Inspect the actual document structure, then validate against the correct
contract. Reject ambiguous or unsupported structures clearly.

For a full propeller preserve:
- Top-level name.
- Nested blade name.
- Blade count.
- Hub diameter and length.
- Bore diameter.
- Initial azimuth.
- All airfoil definitions and coordinates.
- Every distribution and interpolation choice.
- Thickness overrides, including null/omitted handling.
- Physical TE values.

Do not regenerate an imported propeller name automatically from the blade
name and thereby overwrite its saved name.

Do not silently discard unknown or invalid fields.
Do not serialize frontend row IDs or transient UI state.

---

## 9. Atomic import and predictable reset behavior

Import must be atomic:

Parse → identify type → validate → replace editor state.

On failure, keep the current project unchanged.
Do not partially load the blade while losing the assembly.

Use backend validation without generating STEP or launching OpenVSP.
Unsupported runtime configurations must receive an explicit message,
never a silent conversion to a supported count.

After a successful import:
- Reset transient editing/history state appropriately.
- Establish a complete project baseline.
- Update design mode and selected stations safely.
- Invalidate incompatible pending requests.
- Keep old displayed CAD explicitly associated with its old snapshot.

Define Reset to restore the complete baseline project, not only its blade.

New and Load Example must have documented behavior for both design modes.
They must not silently retain an unrelated old hub configuration.

Switching between Single Blade and Full Propeller must not erase the
engineer's assembly settings.

An exported supported propeller must be reopenable in a fresh application
session and rebuildable from its JSON through the existing CLI.

---

## 10. Keep changes small and reusable

Prefer small modules for:
- Runtime assembly capabilities/preflight.
- Structured validation issues.
- Project document parsing and serialization.
- Draft-validation status.

Do not place all new logic inside App.tsx.

Preserve:
- Existing React frontend.
- Existing FastAPI endpoints where compatible.
- Shared serialized CAD worker.
- Independent Python engine and CLI.
- Versioned neutral specifications.

No desktop framework, database, or new CAD engine is needed.

Do not spend this patch revisiting curve dragging.
Numeric editing and existing curve displays must continue working.

---

## 11. Required validation tests

Use the current five-section reference blade at D=400 mm, root r/R=0.20.

Test these input cases:

1. Hub D=60, L=30, bore=12:
   Reject with a field-level hub/root explanation.
   No CAD job or OpenVSP invocation.

2. Hub D=80:
   Reject under the unchanged strict nominal preflight policy.

3. Hub D=81 with otherwise valid inputs:
   May pass the nominal radius check.
   Do not treat that as proof of geometric build success.

4. Hub D=90, L=30, bore=12:
   Pass preflight and execute a real two-blade acceptance build.

5. Change propeller diameter to 600 mm with root r/R=0.20:
   The nominal hub-diameter bound must become 120 mm, not remain 80 mm.

6. Bore diameter equal to or greater than hub diameter:
   Reject before build.

7. Zero/negative/nonfinite dimensions and noninteger blade counts:
   Reject appropriately.

8. Blade counts 5–8:
   Reject runtime generation before queueing/reference-blade generation.
   Explain the current supported range.

Test the shared policy through API, CLI preflight, and engine entrypoints.

Do not remove actual OCP overlap checks because preflight has passed.

---

## 12. Project round-trip and state tests

Verify:

- BladeSpec export → import.
- PropellerSpec export → import.
- A custom propeller name survives round-trip.
- Imported coordinate airfoils survive unchanged.
- Different blade and distribution grid sizes survive.
- Interpolation and precise numerical values survive.
- Invalid JSON preserves the current project.
- Invalid PropellerSpec preserves the current project.
- Reset restores both blade and assembly.
- A mode switch does not erase assembly inputs.
- No import/export/reset action creates a CAD job.
- Exported propeller JSON works with build-propeller CLI.

Compare parsed engineering data, not JSON whitespace or property ordering.

Test the user's status sequence:

Successful assembly A
→ change hub diameter to 60 mm
→ reject current inputs without generating
→ retain A, clearly labeled historical
→ restore hub diameter to 90 mm and set length to 30 mm
→ generate assembly B
→ display B with its correct job ID and full specification.

Test delayed validation responses and failed generation separately.

---

## 13. Real CAD and browser acceptance

Add a reproducible accepted example for:

- Reference blade diameter: 400 mm.
- Root r/R: 0.20.
- Blade count: 2.
- Hub diameter: 90 mm.
- Hub length: 30 mm.
- Shaft bore diameter: 12 mm.
- Initial azimuth: 0 degrees.

Generate through the actual application pipeline, export STEP, and
re-import it for measurement.

Require unchanged production gates:
- One connected valid solid.
- Closed shell.
- Zero non-degenerate free edges.
- Valid BRep.
- Positive root/hub overlap.
- No unsupported outside-hub blade collisions.
- Correct through-bore.
- Existing STEP round-trip checks.
- Existing blade-geometry tolerances.

Preserve the previous accepted 2-, 3-, and 4-blade regression examples.

Run Playwright against the real application:

Load example
→ Full Propeller
→ create a successful result
→ enter Hub D=60 / L=30
→ verify clear error and historical-result labeling
→ verify no new build request
→ enter Hub D=90 / L=30
→ generate successfully
→ export PropellerSpec
→ open a fresh session
→ import exported JSON
→ verify all inputs and names
→ rebuild and validate the saved design.

Use real backend/CAD execution for at least the 90 × 30 mm case.
Do not replace CAD evidence with mocked success responses.

---

## 14. Delivery and acceptance

Create:
docs/PATCH_04A_1_REPORT.md
docs/PATCH_04A_1_ACCEPTANCE_MATRIX.md

Update README and relevant architecture/assembly documentation.

Document:
- The unchanged conservative hub-root policy.
- Dynamic numeric guidance.
- Supported-count policy and early rejection.
- Project import/export/reset semantics.
- Current-input versus historical-result states.
- Exact commands and executed test results.
- Real 90 × 30 mm assembly measurements.
- Remaining limitations.

Provide screenshots of:
- The readable 60 mm hub error.
- Previous successful CAD clearly labeled as historical.
- Successful 90 × 30 mm assembly.
- Restored full-propeller project after JSON import.

Do not claim STRONG PASS unless all four corrective goals pass, including
a real save/open/rebuild workflow and the user's 90 × 30 mm regression.

Do not fabricate results or silently alter engineering requirements.
Do not automatically merge into main.

## Final instruction

Implement this focused patch in the existing BladeGen repository.

Preserve the geometry engine and historical data.

The desired outcome is that an engineer can understand why assembly
parameters are rejected, correct them without confusion about old CAD,
save and reopen the complete propeller design, and regenerate it using
the same neutral specification and qualified assembly pipeline.