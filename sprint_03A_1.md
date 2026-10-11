# PATCH 03A.1 — BladeGen Visual Engineering Accuracy

## Repository

https://github.com/ahmadqwcv5-droid/bladegen

## Mission

Implement a focused engineering-accuracy patch following Sprint 03A.

Sprint 03A introduced a searchable Airfoil Library, DAT/CSV import, canonical 2D Airfoil Inspector, and engineering distribution charts.

Independent source-code review identified four issues:

1. Airfoil upper/lower contour lines are practically invisible in the 2D Inspector.
2. Distribution-chart hover coordinates do not correctly map screen positions to engineering radial positions.
3. Reported contour acceptance thresholds differ from the implemented CAD validation thresholds.
4. Sparse imported coordinate profiles can pass import validation but later fail CAD fidelity, without sufficient advance warning.

Correct these issues without replacing the geometry engine or changing validated BladeSpec semantics.

The objective is to make the new visual engineering tools accurate and trustworthy.

---

## PART A — REPOSITORY PREPARATION

### 1. Inspect the current workspace

Inspect Git status, the current branch, and the latest repository commit.

The last reviewed Sprint 03A merge commit was:

`4f52ff1cbf93badc03b3a6317115839e89071a0a`

Do not assume it is still the latest commit.

Create a dedicated branch:

`patch/03a.1-visual-engineering-accuracy`

Preserve any uncommitted work.

Do not modify `00_research_archive`.

Do not automatically merge into `main`.

### 2. Preserve the existing engineering architecture

Keep:

- BladeSpec v0.2.
- Canonical NACA 4-digit generation.
- Imported coordinate profiles.
- SciPy Linear/PCHIP interpolation.
- Physical finite trailing-edge thickness.
- OpenVSP.
- OCP solidification.
- Adaptive Gauss–Kronrod volume reporting.
- Dynamic airfoil stations.
- The Airfoil Library and its file-backed registry.
- Real CAD validation and STEP export.
- Progress reporting and the expandable 3D viewer.

Do not redesign these systems as part of this patch.

---

# PART B — FIX THE 2D AIRFOIL INSPECTOR

## 3. Confirmed SVG stroke-width defect

Inspect:

`frontend/src/components/AirfoilInspector.tsx`

and:

`frontend/src/sprint03a.css`

The current CSS contains values equivalent to:

```css
.airfoil-upper,
.airfoil-lower {
  stroke-width: .004;
  vector-effect: non-scaling-stroke;
}
```

With `vector-effect: non-scaling-stroke`, the stroke width is effectively interpreted in screen-space units.

The resulting airfoil outline is practically invisible.

Independent Chromium reproduction measured an effective stroke width of approximately `0.004px`.

### Required correction

Use visible screen-space stroke widths.

For example:

```css
.airfoil-upper,
.airfoil-lower {
  fill: none;
  stroke-width: 2px;
  vector-effect: non-scaling-stroke;
}
```

Use appropriate thinner widths for:

- Chord line.
- Grid lines.
- Reference axes.

Ensure the upper and lower surfaces remain visually distinguishable.

Keep the existing engineering coordinates unchanged.

Do not change NACA generation, imported coordinates, or TE mathematics merely to improve their appearance.

## 4. Preserve geometrically correct display scaling

Verify that the SVG preserves the actual airfoil geometry.

Requirements:

- The x/c and y/c axes must use consistent geometric scaling.
- Do not introduce unlabelled vertical exaggeration.
- A symmetric airfoil must appear symmetric.
- A cambered airfoil must visibly show its camber.
- Finite trailing-edge geometry must be distinguishable at sufficient zoom.
- Leading-edge and trailing-edge markers must not obscure the contour.
- Small or narrow viewports must not make the profile lines disappear.

If vertical exaggeration is offered, it must be explicitly labelled and disabled by default.

## 5. Inspector acceptance tests

Use actual canonical coordinate data for:

- NACA 0012.
- NACA 2412.
- NACA 4412.
- The existing imported analytic finite-TE profile.

Verify that both source and resolved contours render visibly.

Add Playwright checks for:

- Nonzero and legible computed stroke widths.
- Visible upper and lower SVG paths or polylines.
- Correct source/resolved switching.
- Responsiveness in a narrow viewport.
- Correct geometry aspect ratio.

Capture before/after screenshots.

Do not treat the presence of SVG elements alone as sufficient proof of visibility.

---

# PART C — CORRECT DISTRIBUTION-CHART HOVER

## 6. Confirmed coordinate-mapping defect

Inspect:

`frontend/src/components/DistributionChart.tsx`

The chart defines an SVG viewBox with internal margins:

```typescript
const WIDTH = 640
const HEIGHT = 260

const MARGIN = {
  left: 58,
  right: 18,
  top: 18,
  bottom: 42
}
```

However, its hover calculation uses the mouse position relative to the entire rendered SVG width.

This ignores the chart's internal plotting margins.

As a result, pointer positions do not map correctly to the radial engineering coordinates.

For the current example, independent reproduction produced approximately:

```text
At the start of the plotted curve:

Expected r/R: 0.2000
Displayed r/R: approximately 0.2725

At the end of the plotted curve:

Expected r/R: 1.0000
Displayed r/R: approximately 0.9775
```

These are meaningful errors for an engineering design tool.

## 7. Implement correct SVG-to-data mapping

Correctly convert pointer coordinates into SVG coordinates.

The implementation must account for:

- SVG viewBox.
- Internal plot margins.
- CSS rendering dimensions.
- Responsive resizing.
- Potential SVG letterboxing from aspect-ratio preservation.

A suitable implementation may use:

`getScreenCTM().inverse()`

with an SVG point or DOMPoint transformation.

Map the pointer's actual position within the plotted horizontal axis to:

`r_over_R`

Clamp appropriately to the valid plotting domain.

Then identify the nearest canonical backend-provided sample.

Do not recalculate engineering PCHIP values in JavaScript.

The backend remains the mathematical authority.

## 8. Hover accuracy requirements

Test:

- Left plotting boundary.
- Right plotting boundary.
- Midpoint.
- Positions between user control points.
- Linear distribution.
- PCHIP distribution.
- Resized chart.
- Narrow-screen chart.

At the left plotted boundary, the displayed radial value must correspond to the first sampled radius.

At the right boundary, it must correspond to the last sampled radius.

For intermediate points, the difference between the pointer's inferred radius and the chosen nearest sample must not exceed half the local sample spacing, apart from floating-point tolerance.

The displayed engineering value must be taken from the corresponding canonical sample.

Verify Chord in mm, Twist in degrees, Rake/Skew in mm, and Thickness in % t/c.

Do not confuse normalized BladeSpec values with physically scaled chart values.

---

# PART D — CAD VALIDATION POLICY CONSISTENCY

## 9. Confirmed discrepancy

Inspect:

- `backend/bladegen/validation/measure_sections.py`
- `backend/bladegen/pipeline.py`
- `docs/VALIDATION_POLICY.md`
- `docs/SPRINT_03A_ACCEPTANCE_MATRIX.md`
- `docs/SPRINT_03A_REPORT.md`

The actual validation code currently uses these contour thresholds:

| Station category | RMS | P95 | Maximum |
|---|---:|---:|---:|
| Airfoil control station | 0.030 mm | 0.060 mm | 0.120 mm |
| Intermediate station | 0.050 mm | 0.100 mm | 0.200 mm |

However, the Sprint 03A acceptance matrix describes the unchanged control contour thresholds as:

```text
RMS <= 0.020 mm
P95 <= 0.040 mm
Maximum <= 0.050 mm
```

These are not the same requirements.

This mismatch must be resolved explicitly.

## 10. Separate existing production gates from tighter acceptance targets

Preserve the established production engineering tolerances unless a separately justified policy change is approved.

Do not silently tighten or loosen historical thresholds.

Recommended solution:

**Production geometry gate**

Retain the existing historical control/intermediate thresholds.

**Additional imported-airfoil acceptance target**

If the tighter 0.020 / 0.040 / 0.050 mm values are intended as qualification requirements for high-fidelity imported-airfoil tests, define them explicitly as an additional acceptance target.

Make the distinction obvious in code and documentation.

For example:

```text
Production control-section gate:
RMS <= 0.030 mm
P95 <= 0.060 mm
Maximum <= 0.120 mm

Additional imported-profile acceptance target:
RMS <= 0.020 mm
P95 <= 0.040 mm
Maximum <= 0.050 mm
```

These must not be described as identical policies.

If the stricter limits are not intended to be enforced universally, do not falsely present them as universal runtime gates.

The current imported analytic acceptance fixture measured approximately:

```text
Contour RMS:     0.014267 mm
Contour P95:     0.031276 mm
Contour maximum: 0.036200 mm
```

It should pass both the historical production gate and the additional stricter acceptance target.

## 11. Add policy tests

Create tests that:

- Confirm actual production thresholds.
- Confirm imported-profile acceptance thresholds where applicable.
- Verify that values just above a threshold fail the corresponding gate.
- Verify that values below a threshold pass.
- Ensure documentation and reported results use the correct policy names.

Prefer a clearly defined source of truth for numerical tolerances.

Do not duplicate incompatible tolerance constants across modules.

Preserve existing chord, twist, axis, TE, and STEP topology requirements.

---

# PART E — IMPORTED AIRFOIL QUALITY WARNINGS

## 12. Observed sparse-profile limitation

Sprint 03A reported an important finding.

An imported coordinate profile with only five points per surface passed file import but failed final CAD contour fidelity.

Its maximum reported contour deviation was approximately:

`0.493 mm`

An independently specified analytic profile with 41 points per surface subsequently passed the final CAD acceptance test.

This shows that successful coordinate parsing does not guarantee that OpenVSP will reproduce the intended shape within CAD tolerances.

Do not solve this by silently resampling or smoothing user data.

## 13. Add non-blocking profile-quality diagnostics

Implement a small diagnostic function for coordinate-based airfoils.

Suggested location:

`backend/bladegen/airfoils/diagnostics.py`

Evaluate simple deterministic indicators, such as:

- Upper surface point count.
- Lower surface point count.
- Maximum chordwise gap between adjacent supplied points.
- Very sparse leading-edge coverage.
- Large local changes in polygonal slope, where meaningfully detectable.

Start with conservative, documented warning heuristics.

For example, a profile with fewer than approximately 25–30 points per surface or unusually large x/c spacing may receive a warning.

These are screening heuristics, not proven universal manufacturing or CAD-validity limits.

Do not report that every profile above a certain point count is accurate.

Do not automatically reject every sparse airfoil.

## 14. Surface the warning before Generate

When a user imports or selects a coordinate airfoil, display a clear message such as:

"Low coordinate density detected. OpenVSP surface reconstruction may deviate from the supplied polyline. Final STEP fidelity will be checked after generation."

Display useful details:

```text
Upper surface: 5 points
Lower surface: 5 points
Maximum chordwise spacing: 0.25 c

Warning: Sparse coordinate definition
```

Where practical, return these diagnostics through the existing canonical preview or BladeSpec validation API.

The same warning should appear for an equivalent coordinate airfoil loaded from a standalone BladeSpec JSON, even when its original DAT file or library record is unavailable.

Warning logic must therefore operate on embedded neutral coordinates, not require library metadata.

## 15. Preserve the user's profile

Do not:

- Insert additional coordinate points automatically.
- Smooth or refit the imported contour.
- Change its maximum thickness.
- Alter its camber.
- Replace it with a NACA profile.
- Increase CAD tolerances merely to make the test pass.

The warning is advisory.

The final OCP-based CAD validation remains authoritative for deciding whether the generated STEP meets the established geometric fidelity thresholds.

---

# PART F — TESTING

## 16. Backend tests

Add regression tests for:

1. Imported airfoil coordinate diagnostics.
2. Sparse-profile warnings.
3. Adequately sampled profiles without misleading warnings.
4. Warnings on profiles embedded in BladeSpec.
5. Preservation of original imported coordinates.
6. Validation-policy consistency.
7. Imported coordinate-profile qualification.

Run the existing backend suite.

Re-run the real CAD acceptance cases:

- Three-section blade.
- Five-section baseline.
- Eight-section blade.
- NACA 0008 thickness override.
- The Sprint 03A imported analytic airfoil.

Require the established topology and geometry gates.

## 17. Frontend tests

Add Vitest and React Testing Library coverage for:

- Visible 2D airfoil contour rendering.
- Source/resolved inspector switching.
- Correct hover mapping.
- Correct engineering units.
- Chart behavior after resize.
- Sparse-profile warning visibility.
- No change to the underlying BladeSpec when warnings appear.
- Existing airfoil selection and import workflow.

## 18. Browser testing

Run Playwright with an actual Chromium browser.

Test:

```text
Open BladeGen
    ↓
Select NACA 2412
    ↓
Verify upper/lower contours are visible
    ↓
Switch to resolved profile
    ↓
Inspect Chord distribution
    ↓
Hover near r/R 0.20
    ↓
Hover near r/R 1.00
    ↓
Check displayed values
    ↓
Resize browser
    ↓
Repeat hover checks
    ↓
Import a sparse coordinate airfoil
    ↓
Verify warning
    ↓
Import the accepted 41-point profile
    ↓
Generate real STEP
    ↓
Confirm CAD validation PASS
```

Capture screenshot evidence for the corrected 2D inspector, correct hover readout, and sparse-profile warning.

Do not claim browser acceptance passed without executing it.

---

# PART G — DELIVERABLES

## 19. Report

Create:

`docs/PATCH_03A_1_REPORT.md`

Include:

- Root cause of the invisible SVG contour.
- Before/after screenshots.
- Corrected hover-coordinate mathematics.
- Hover validation results at known radial positions.
- Exact distinction between production CAD tolerances and imported-profile acceptance targets.
- Sparse-profile warning policy and limitations.
- Source-code changes.
- Actual test results.
- Real CAD regression results.
- Any remaining issues.

Update:

- `docs/VALIDATION_POLICY.md`
- `docs/SPRINT_03A_ACCEPTANCE_MATRIX.md`
- `docs/AIRFOIL_IMPORT_FORMATS.md`
- README if user-facing behavior changes.

Correct historical documentation carefully. Do not erase the original evidence of failed experiments.

---

# PART H — ACCEPTANCE CRITERIA

Classify this patch as STRONG PASS only if:

1. NACA and imported airfoil upper/lower contours are clearly visible.
2. SVG scaling preserves the correct section proportions.
3. Source and resolved profiles remain distinguishable.
4. Hover radial positions accurately map to the plotted curve.
5. Hover values come from canonical backend samples.
6. Hover remains correct after responsive resizing.
7. Production CAD tolerances remain unchanged.
8. Documentation accurately states every applicable tolerance.
9. Sparse imported profiles receive meaningful, non-blocking warnings.
10. Original imported coordinates are preserved.
11. Warning logic also works on standalone embedded-coordinate BladeSpecs.
12. Existing geometry regressions remain successful.
13. Backend and frontend tests pass.
14. Playwright tests execute successfully.
15. The imported 41-point airfoil still generates a valid STEP.
16. `00_research_archive` remains untouched.

Report PASS WITH LIMITATIONS if critical behavior is unverified.

Never fabricate test results or silently adjust numerical requirements.

---

# PART I — STRICT SCOPE CONTROL

Do not implement:

- New airfoil databases.
- Airfoil comparison overlays.
- Drag-to-edit distribution curves.
- 3D station picking.
- Hub geometry.
- Multiple blades.
- Aerodynamic simulation.
- Performance optimization.
- A replacement OpenVSP/OCP pipeline.
- A large frontend redesign.

These features belong to future sprints.

---

# FINAL INSTRUCTION

Implement Patch 03A.1 in the existing BladeGen application.

Execution priority:

1. Correct AirfoilInspector SVG rendering.
2. Correct DistributionChart hover mapping.
3. Reconcile validation thresholds and documentation.
4. Add imported-airfoil quality warnings.
5. Run frontend, backend, browser, and real CAD regression tests.
6. Publish a factual engineering report with reproducible evidence.

Preserve the validated geometry engine and user data.

Do not automatically merge into main.

**The desired result is a trustworthy visual engineering interface where the airfoil shape is visible, plotted values correspond to actual engineering coordinates, CAD tolerances are accurately documented, and sparse imported airfoils are flagged before generation.**