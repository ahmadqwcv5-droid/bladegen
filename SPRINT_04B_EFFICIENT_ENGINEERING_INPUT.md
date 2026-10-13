# SPRINT 04B — Efficient Engineering Input & Responsive Editing

Repository: https://github.com/ahmadqwcv5-droid/bladegen
Proposed branch: `sprint/04b-efficient-engineering-input`
Reviewed baseline: `30d85b2cc8d696ed7f1ea5461ad205557fe2743b`

## 1. Product goal and execution boundary

BladeGen currently converts engineering inputs supplied by an engineer into a validated blade or propeller CAD model. It does not choose aerodynamic geometry from thrust, power, or RPM requirements. Preserve that scope.

The user's manual X-57 trial stopped during data entry. Adding and repositioning dozens of rows was impractical, and adding a control point waited on expensive full-resolution validation. This sprint must replace that workflow with supported bulk input and responsive, mathematically faithful editing.

Implement in the existing React/FastAPI/Python application. Do not create a desktop application, replace the geometry engine, introduce aerodynamic analysis, or revisit curve dragging as a separate project. Hub fillets/root fairings are deferred.

Inspect actual HEAD and working-tree status. Preserve user changes, do not overwrite the partially entered X-57 project, and do not modify `00_research_archive`. Do not automatically merge into main. Changes to numerical implementation are permitted only to eliminate redundant computation without changing engineering meaning or weakening gates.

Deliver the work in three reviewable stages: (A) bulk distribution input and evaluator optimization; (B) bulk airfoil-station setup and table editing; (C) end-to-end qualification. Do not stop at planning.

## 2. Required end-user workflows

### Import an existing design definition

1. Enter global dimensions/reference axis using the existing UI.
2. Define two airfoil stations in one setup operation; import an airfoil CSV and apply it to both selected stations.
3. Open **Import Distributions**, select the supplied 40-row X-57 table, confirm columns, units, and interpolation, and apply once.
4. Obtain Chord/Twist/Rake/Skew distributions with 40 points each. Do not generate 40 airfoil stations. Preserve the two-point thickness distribution unless the user explicitly included it in the proposed change.
5. Save/export the complete neutral definition, review it, and explicitly Generate Blade.

No repeated Add Control Point clicking, manual reordering of dozens of radii, source-code edits, hidden JSON injection, or X-57-specific production logic is allowed.

### Start from a small engineer-defined design

Create 2, 3, 5, or another supported number of airfoil stations using a station setup dialog. Populate existing distribution tables with a pasted block or a chosen starter grid. Allow individual exact numerical edits afterward. A starter grid only organizes input; it must not be described as aerodynamic design or optimization.

## 3. Keep three kinds of points distinct

The UI and tests must distinguish:

- **Airfoil stations:** radial locations where the engineer defines an airfoil/profile and physical TE requirement.
- **Distribution controls:** radial/value pairs defining Chord, Twist, Rake, Skew, or Thickness. Grids may differ between distributions and from airfoil stations.
- **Computed samples:** points used internally for previews, curve resolution, CAD, or validation. Never expose all of these as required manual inputs.

Do not synchronize these counts implicitly. Forty CSV rows across four distributions are 160 distribution controls, not forty airfoil profiles or 160 CAD rebuild requests.

## 4. Review the real implementation before editing

At minimum inspect:

- `frontend/src/components/DistributionTable.tsx`
- `frontend/src/components/NumericInput.tsx`
- `frontend/src/components/AirfoilSelector.tsx`
- `frontend/src/App.tsx`
- `frontend/src/editor/bladespecEditor.ts`
- `frontend/src/editor/curveEditing.ts`
- `frontend/src/editor/airfoilSelection.ts`
- `frontend/src/editor/projectDocument.ts`
- `frontend/src/api/client.ts`
- `backend/api/routes/blades.py`
- `backend/api/routes/airfoils.py`
- `backend/bladegen/curves/canonical.py`
- `backend/bladegen/curves/resolver.py`
- `backend/bladegen/validation/propeller_preflight.py`
- `frontend/e2e/jobIdentity.ts`

The reviewed DistributionTable inserts one point at the largest gap midpoint and awaits `onChange`. The reviewed blade `/validate` route calls `resolve_blade_spec`. The reviewed `evaluate_curve` constructs a new PCHIP evaluator for each non-control scalar evaluation. Confirm the actual call graph and measure it; do not infer all observed delay from code alone.

## 5. Bulk distribution import — P0

Add a discoverable **Import Distributions** action near the distribution tables. Accept UTF-8 CSV and pasted tab-separated text from spreadsheet cells. Native XLSX workbook reading is not required in this sprint.

Support:

- One shared `r_over_R` column plus one or more distribution value columns.
- A file/paste operation targeting one distribution with its own radial grid.
- Partial imports: only explicitly selected distributions are replaced. Other distributions, airfoil stations, global dimensions, and assembly settings remain unchanged.

The supplied fixture has these exact headers:

`row,r_over_R,chord_mm,twist_deg,rake_mm,skew_mm`

Recognize `row` as an informational index and display that it is not mapped to engineering data. Do not send it into BladeSpec. Treat other unmapped columns as visible warnings requiring explicit exclusion, not silently ignored unknown engineering data.

### Review before Apply

Show filename/source, row counts, target distributions, interpolation per distribution, units, radial domain, old/new point counts, and a readable candidate preview.

Offer **Cancel** and **Apply**. No state mutation occurs on opening, parsing, or cancelling the dialog. The initial operation is **Replace selected distribution(s)**, not an ambiguous merge. Do not delete and recreate rows through a loop of existing single-point callbacks.

For X-57, the review should show four selected distributions, 40 rows each, PCHIP explicitly selected/confirmed, and Thickness unchanged.

### Units

Preserve existing storage semantics:

- Chord/Rake/Skew in mm become the appropriate value divided by `R = diameter_mm / 2`.
- Twist in degrees stays in degrees.
- Thickness in `% t/c` becomes ratio / 100; a `thickness_ratio` column is already a ratio.
- Explicit normalized columns may be supported with their existing meaning.

Never guess units from numerical magnitude or labels such as plain `value`. Require explicit mapping when headers are ambiguous. Never confuse radial millimetres with `r/R`; version one may require normalized `r_over_R` and reject other radial forms with a helpful message.

Use the diameter from the candidate snapshot reviewed by the user. A concurrent diameter/root edit invalidates that preview; do not silently reinterpret the same imported values using a newer diameter.

### Input integrity

Preserve signs, precision, and all supplied values. Handle scientific notation. Do not silently simplify, smooth, resample, drop rows, extrapolate endpoints, convert blanks to zero, or change interpolation.

Reject duplicates, missing required cells, nonfinite values, unusable domains, and inconsistent endpoints with row/column errors. A visible explicit sort action is acceptable, but sorting must not change any value or merge duplicates. Explain a root/tip mismatch rather than moving the project's root automatically.

No requirement that all distributions share one grid. Impose documented safety limits independent of this specific 40-row fixture; exercise at least 200-row synthetic imports.

## 6. Clipboard and table editing — P0

Support one ordinary Ctrl/Cmd+V paste of a rectangular TSV block through an explicit paste dialog or selected table range. Do not implement background clipboard monitoring. Avoid building an entire spreadsheet application.

Pasted multirow changes use the same conversion/validation/transaction layer as CSV import. Provide a review before destructive replacement. Changes to several radius values must be checked against the final proposed table, not rejected because an intermediate cell would cross its old neighbour.

Retain individual add/delete/value/radius editing. Improve responsiveness; do not require a tab-switch workaround. Keep focused input and scroll positions stable. Display precise input when needed without rounding the neutral values to the three-decimal presentation format.

## 7. Bulk airfoil-station setup — P0, bounded scope

Add **Set Up Airfoil Stations** and **Apply Profile to Selected Stations** controls.

The setup dialog supports:

- A total station count including root and tip with uniform radial spacing, OR a pasted explicit `r/R` list.
- Root and tip matching the current global domain.
- A deliberately chosen existing library/imported profile used as a starting assignment, with individual profile editing still available afterward.
- An explicitly entered common physical TE requirement, or preserved values for retained stations.
- A review of old/new station count, assignments, and any required thickness coordination before Apply.

For example, count 5, root 0.20, tip 1.0 gives 0.20, 0.40, 0.60, 0.80, 1.0. This is only a placement template.

Do not regenerate a different airfoil family or guess a physically suitable profile. Do not assume that adding an interpolated airfoil station preserves the old loft exactly. Make station insertion/replacement a design edit and mark CAD stale.

Reuse existing canonical NACA/coordinate semantics. If applying profiles requires changes to thickness controls, include those changes explicitly in the review and commit them atomically with the profile assignments. Do not rewrite coordinates or silently reset unrelated distributions. Preserve a valid explicit override or require the user to resolve a conflict.

Keep import of distribution rows separate from station setup: the 40-row X-57 distribution file must never create 40 airfoil stations.

For the immediate X-57 workflow, enable two endpoints, the same imported airfoil at both, TE=0, and an explicitly reviewed constant natural-thickness distribution. Do not hard-code the X-57 profile or thickness into production logic.

## 8. One engineering transaction per bulk operation

Build a complete candidate from the current committed snapshot. Validate the whole proposed state once, then commit all of it or none of it.

Preserve structural checks and existing non-CAD semantic checks for NACA nominal thickness, explicit overrides, imported-profile natural thickness, physical TE rules, finite curves, and valid radial domains. Do not bypass the semantic-preflight corrections from 04A.2.

During draft import/editing, distinguish provisional data from committed engineering state. Avoid requests per row, per cell, or per pointer event. For one Apply, target one backend validation operation plus at most one canonical preview refresh; a separate parsing request is acceptable if needed and documented.

An unchanged candidate creates no history entry, clears no Redo, and does not invalidate matching CAD. A real bulk import is one Undo operation. Station/TE/thickness-coordination changes must undo together. If the existing history scope must be extended, do so narrowly rather than introducing a new application-wide state library.

Handle invalid input, timeout, cancellation, second import, project load/reset, mode switch, and late responses safely. An old operation must not overwrite a newer design. Invalid candidates do not affect the last committed data or completed artifacts.

## 9. Optimize evaluation without changing mathematics — P0

Profile parsing, semantic checking, curve resolution, preview, and React rendering separately. Use the user's 40-point case, not only the five-section demo.

Prepare each canonical curve evaluator once per immutable snapshot/operation and reuse it. Evaluate arrays of query positions in one call where possible, including the 5001-location verification grid. Reuse the same evaluator inside adaptive interval probes instead of rebuilding it at every sample.

Preserve:

- SciPy PCHIP, with extrapolation disabled.
- Existing Linear meaning.
- Exact user-control return behavior, including endpoint handling.
- Domain/finite-value checks.
- Existing 5001-location verification and adaptive tolerances.
- Semantic thickness/TE checks.
- Existing final CAD/STEP validation gates.

Do not improve timing by reducing verification density, deleting controls, accepting an approximate frontend curve, widening tolerances, or weakening the /validate contract. Prefer making the current full validation efficient first. If a separate lightweight draft endpoint is necessary, name/label its scope honestly and preserve full validation before CAD generation.

Request-local reuse is preferred to a complicated global cache. If cross-request caching is introduced, make it bounded and keyed by every relevant immutable input/interpolation setting. Prove invalidation and never use mutable object identity or a project name as the key.

Do not make the UI run authoritative PCHIP mathematics. Canonical backend samples remain the committed chart source.

## 10. Performance qualification

Set explicit provisional acceptance targets on the documented local reference machine; these are targets to verify, not preclaimed performance results:

- Visible UI acknowledgement of Add/Paste/Import: within 100 ms.
- 40-row import parsing and review presentation: within 500 ms, excluding file-picker interaction.
- A 40-point-per-curve commit with current canonical preview: p95 <= 1 second after warm-up.
- Equivalent 200-point-per-curve test: p95 <= 2 seconds after warm-up.

Measure at least 20 ordinary repetitions, report cold-first time separately, and report median, p95, and maximum. Include request counts and PCHIP-constructor counts. No CAD generation belongs in these interactive budgets.

Record before/after on the same inputs, machine, runtime versions, and browser. If a target is missed, identify the remaining bottleneck and report a limitation; do not invent a speedup or quietly change the target. A loading animation alone is not a performance fix.

## 11. Fixtures and engineering provenance

The attached `fixtures/x57_manual_reference` files are preexisting source-derived data, not a generated CAD result:

- `x57_hlp_airfoil.csv`
- `x57_hlp_control_points_mm.csv`
- `x57_hlp_control_points_normalized.csv`
- `manifest.json`
- `SHA256SUMS.txt`
- `README_AR.md`

Check their hashes and record source/derived status. Do not fetch a different model revision or modify fixtures to pass tests. If this pack is missing in your actual workspace, report that fact rather than inventing the file contents.

The reference blade parameters are D=575.9200184294399 mm, root r/R=0.20238, reference x/c=0.5, normal rotation, two airfoil stations using the supplied profile, and TE=0 at both endpoints. The four supplied distributions use PCHIP. The known source-vs-product thickness measurement and interpolation-representation differences are documented in the fixture README; do not compensate for them by altering source data.

## 12. Tests and real user acceptance

### Data and state

Cover CSV and clipboard equivalence; single and multidistribution import; independent grids; negative rake/skew; normalized versus physical units; two diameters; full precision; duplicate/missing/malformed cells; domain conflicts; cancelled/failed Apply; full rollback; concurrent edits; no-op; one Undo/Redo transaction; and current-design/old-CAD separation.

Cover station setup with 2, 3, 5, and 8 stations; explicit nonuniform radii; selected profile batch application; matching/inconsistent overrides; natural-coordinate thickness; and explicit TE values. Ensure distribution imports never change station count.

### Mathematical regression

Compare old scalar and optimized vectorized evaluation on existing valid fixtures and deterministic randomized legal curves: exact knots, near knots, endpoints, random and dense interior queries, Linear/PCHIP, and sign-changing values. Compare resolved-vector and final geometry behavior within the existing numerical gates; investigate differences rather than widening gates. Confirm that preflight remains non-CAD.

### Browser workflow using real controls

Load a new project -> enter global X-57 dimensions -> use station setup for two endpoints -> import/apply the airfoil to both -> import the actual 40-row CSV -> review mappings/PCHIP -> Apply once -> verify four 40-point distributions, two airfoil stations, and two-point thickness -> export JSON -> compare every engineering value to the conversion contract -> Undo/Redo the bulk transaction -> modify one numeric value -> save/open in a new browser context.

Exercise actual file upload and an actual paste event, not just helper invocation. Test normal and narrow layouts and repeated import/edit cycles. No calls to /api/build or /api/propellers/build until explicit Generate.

### CAD qualification

Use the improved input path to build at least one already-qualified custom blade and propeller; verify final STEP topology, shape measurements, and round-trip using exact job identity.

Also submit the X-57 blade produced by the user-facing import flow and retain the exact input/output/validation or failure evidence. Do not label an input-import PASS as a NASA geometry-match PASS. A reproducible preexisting X-57 geometry/representation issue must be reported separately; do not change the source profile, interpolation policy, CAD tolerance, or add bespoke geometry to conceal it. Scope any later fidelity fix separately.

Rerun existing backend non-integration, CAD integration, frontend tests/build, lint, and applicable cross-sprint browser tests on the final revision. Report collected/passed/failed/skipped/deselected/retries and exact commands without inflating counts from repeated targeted runs.

## 13. Architecture and deliverables

Keep versioned BladeSpec/PropellerSpec compatible. Suggested small modules: distribution import/parser service, column/unit mapping, atomic bulk transaction helpers, station-setup dialog, and reusable prepared canonical evaluator. Adapt names to the real repository. Do not turn App.tsx into the sole home of all new logic.

Import/validation/conversion services belong in the reusable Python/domain layer where appropriate; browser file selection and clipboard handling belong in React. No desktop packaging, new database, or native XLSX dependency is required.

Create:

- `docs/SPRINT_04B_REPORT.md`
- `docs/SPRINT_04B_ACCEPTANCE_MATRIX.md`
- `docs/BULK_INPUT_FORMATS.md`
- A measured before/after performance report.
- Reproducible real X-57 UI-import evidence and exported candidate JSON.

Provide actual screenshots/video of the new workflow. Preserve all failures and tested commit identities. The final report must separate input usability, numerical correctness, final CAD validity, and external NASA fidelity.

## Acceptance decision

The sprint is not a strong pass merely because helper tests or an importer dialog exist. It must remove the user's repeated-row burden, preserve engineering values and independent grids, support bounded bulk station setup, show measured interactive improvement, preserve prior CAD regressions, and run the real import workflow without hidden project injection or automatic generation.

The user's later hands-on retest remains necessary. Do not claim that all UI friction is resolved solely from automated tests.

## Final instruction

Implement this in the existing repository with minimal maintainable changes. Do not automatically merge into main.

The engineer should select or paste data, review it, apply it once, and generate CAD explicitly—not manually reproduce a source file row by row. Preserve trust in every value while making the common workflow practical.
