# Sprint 04A — Full Propeller Assembly MVP

## Outcome

Sprint 04A implements a reusable full-propeller path in the existing
React/FastAPI/Python product while preserving the validated single-blade
pipeline. The work is on `sprint/04a-full-propeller-assembly`, based on reviewed
`main` SHA `f9edf964427e4f25c2b27be93b1fdc754d792ade`. The working tree remains
uncommitted for review; it has not been merged to `main`.

The result is a **STRONG PASS for the measured 2-, 3-, and 4-blade production
range**. PropellerSpec accepts the planned engineering range 2–8, but Sprint 04A
intentionally rejects 5–8 at assembly time because those counts have not been
fully production-qualified. An exploratory 8-blade case passed the preliminary
placement/collision stage but fusion runtime was not acceptable for this sprint;
no broader support claim is made.

## Architecture and contracts

`PropellerSpec v0.1` is backend-neutral and contains one complete, unchanged
`BladeSpec v0.2` plus an `AssemblySpec`. It contains no OpenVSP or OCP objects.
The JSON Schema is at `docs/schemas/propeller_spec_v0_1.schema.json`; complete
reproducible inputs are:

- `examples/propeller_two_blade.json`
- `examples/propeller_three_blade.json`
- `examples/propeller_four_blade.json`

Representative assembly content is:

```json
{
  "schema_version": "0.1",
  "name": "three_blade_propeller",
  "units": "mm",
  "blade_spec": { "schema_version": "0.2", "units": "mm" },
  "assembly": {
    "blade_count": 3,
    "hub_diameter_mm": 90.0,
    "hub_length_mm": 45.0,
    "shaft_bore_diameter_mm": 12.0,
    "initial_azimuth_deg": 0.0
  }
}
```

The abbreviated `blade_spec` above is explanatory only; every accepted input
contains the full BladeSpec document. The same single-blade definition is reused
unchanged by all three examples. The exact complete JSON example is
[propeller_three_blade.json](../examples/propeller_three_blade.json).

## Changed files

- Engineering: `models/propeller_spec.py`, `assembly/{transforms,hub,validation,builder}.py`,
  `propeller_pipeline.py`, CLI and shared OCP export helpers.
- Application: propeller API route, job build-type/progress/artifact handling,
  response schema, and existing blade-example filtering.
- Product UI: mode/assembly controls and identity logic in `App.tsx`, propeller
  API/types, actual-STL viewer presets, progress diagnostics, and Sprint 04A CSS.
- Qualification: backend model/primitive/Boolean/pipeline/CLI/API/real-CAD tests,
  frontend tests, real Playwright workflow, examples, schema, and screenshots.
- Documentation: README, architecture, geometry/assembly conventions, this
  report, and the acceptance matrix.

No file under `00_research_archive` changed.

`bladegen.propeller_pipeline.build_propeller()` is separate from the existing
`bladegen.pipeline.build()`. It calls that blade pipeline exactly once, retains
the blade STEP and validation, then passes the validated solid into the OCP-only
assembly engine. The core imports neither FastAPI nor React and accepts explicit
input/output paths, so it remains suitable for a future application adapter.

## Geometry construction and diagnostics

The reference blade extends along `+Y`. Every copy is an exact
`BRepBuilderAPI_Transform` rotation about global X with
`θᵢ = θ₀ + i × 360°/N`. The hub and bore are also coaxial with X. Copy volume
is measured against the reference before fusion; maximum deltas were below
`2.19e-11 mm³`. Because OCP transforms the existing BRep rather than refitting
or regenerating it, its faces and section geometry are inherited exactly.

The 90 × 45 mm hub is measured at `286277.6305583692 mm³`. Each root has about
`1397.715592 mm³` of common volume with the uncut hub, comfortably above the
explicit `1e-5 mm³` threshold. All pairwise blade intersections outside the hub
measure `0.0 mm³`. Sequential fusions each produce one BRep-valid solid. The
Boolean fuzzy tolerance is explicitly `1e-7 mm`; no connector or root-fairing
geometry is added.

The 12 mm bore cutter extends 2 mm beyond each hub end. After final STEP
re-import, two coaxial circular boundaries both measure radius `6.0 mm`, maximum
radius error is `0.0 mm`, and common volume between the final solid and extended
bore cutter is `0.0 mm³`. This independently verifies a continuous through-hole
with no hidden blade-root material.

## Real accepted CAD results

All values below come from real OpenVSP 3.54.0 reference-blade builds followed
by OCP assembly and STEP re-import in the browser acceptance workflow. The
reference blade volume is `38559.346222987304 mm³` in every case. Final run IDs
were `bd1a92c61d764beda56348da50b83fac` (2),
`697b947e770d417d9da5fc01c7af29f7` (3), and
`7f7250b6882f478596ae8b31fe9de4e1` (4).

| Blades | Azimuths | Final volume (mm³) | Faces | Solids / shells | Free edges | Closed / valid | Round-trip volume Δ (mm³) | BBox max Δ (mm) |
| ---: | --- | ---: | ---: | --- | ---: | --- | ---: | ---: |
| 2 | 0°, 180° | 355511.51164215506 | 20 | 1 / 1 | 0 | true / true | 3.20e-9 | 7.44e-11 |
| 3 | 0°, 120°, 240° | 392673.14204351895 | 28 | 1 / 1 | 0 | true / true | 1.98e-8 | 7.47e-11 |
| 4 | 0°, 90°, 180°, 270° | 429834.7724337172 | 36 | 1 / 1 | 0 | true / true | 2.45e-6 | 7.44e-11 |

The mass calculation uses the existing OCP adaptive mass-properties path. As
expected, final volume is not computed by simply summing blades and hub because
root overlap is fused and bore material is removed.

## CLI, API, jobs, and artifacts

The original command remains unchanged. The new independent command is:

```bash
bladegen build-propeller propeller.json --output output/propeller
```

New endpoints are:

- `POST /api/propellers/validate`
- `POST /api/propellers/build`

Both product types use the existing `/api/jobs/{job_id}` status and artifact
routes and the same single-worker executor. Job metadata identifies `blade` or
`propeller`. Propeller progress is based on confirmed events: neutral validation,
reference-blade generation, exact copy placement, positive-volume intersection,
fusion, bore cut, final STEP validation, artifacts, and process confirmation.
Stage-specific failures distinguish these operations.

Successful jobs expose allow-listed `propeller_solid.step`,
`propeller_preview.stl`, `propeller_spec.json`, `blade_solid.step`,
`blade_spec.json`, `validation.json`, plus separate blade and CSV diagnostics.
The preview STL is tessellated from the final re-imported OCP assembly solid.

## Product behavior

The existing React editor now switches between **Single Blade** and
**Full Propeller** while retaining all airfoil stations and distributions.
Assembly controls edit blade count, hub diameter/length, bore diameter, and
initial azimuth. Static validation does not start CAD. Generate freezes the full
PropellerSpec snapshot and binds the result type, job ID, artifacts, validation,
and STL to that snapshot. Any blade or assembly change, or a mode switch, marks
the old CAD visibly stale.

The Three.js viewer displays the actual propeller STL with X-axis front, side,
isometric, fit, and expanded modes. Single-blade radial guides are disabled with
an explanation in propeller mode so a guide is not misleadingly shown on only
one rotated blade.

## Failure behavior and limitations

Controlled tests cover invalid dimensions, bore ≥ hub, tangential/insufficient
root contact, unqualified high counts, operation-specific fusion and bore-cut
failures, and every invalid final topology condition. Failed builds do not reach
PASS or expose an invalid assembly as a successful artifact.

Sprint 04A deliberately excludes spinner, fillets, keyway, bolt holes, flanges,
advanced root fairings, independent per-blade geometry/pitch, aero/structural
analysis, and desktop packaging. Linux OpenVSP setup is qualified; Windows and
macOS still require separate runtime packaging. The Vite build retains its
pre-existing large-chunk advisory, and backend tests retain one Starlette/httpx
deprecation warning.

## Deviations from the initial plan

The neutral contract keeps the requested 2–8 range, but the production builder
uses an explicit measured qualification gate of 2–4 rather than claiming all
contract-valid counts. An exploratory 8-blade fusion was too slow for a reliable
serialized web job. This is a deliberate safety limitation, not a hidden input
change. No alternate CAD backend, artificial connector, mesh Boolean, or
per-blade OpenVSP regeneration was introduced.

## Evidence

- [Assembly controls](screenshots/sprint04a/assembly_controls.png)
- [Two-blade assembly](screenshots/sprint04a/two_blade_assembly.png)
- [Three-blade assembly](screenshots/sprint04a/three_blade_assembly.png)
- [Four-blade assembly](screenshots/sprint04a/four_blade_assembly.png)
- [Hub/bore front detail](screenshots/sprint04a/hub_bore_front_detail.png)
- [Expanded propeller viewer](screenshots/sprint04a/expanded_propeller_viewer.png)
- [Assembly validation](screenshots/sprint04a/assembly_validation_results.png)

## Verification and reproduction

- Backend: `125 passed` in `526.29 s`; one existing deprecation warning.
- Frontend: `19` files, `104` tests passed.
- Production frontend: TypeScript and Vite passed; 41 modules transformed.
- Isolated real assembly acceptance: `5 passed` in `120.09 s`.
- Complete Playwright regression: `9 passed` in `21.2 min`.
- Real browser Sprint 04A workflow: passed in `6.2 min` for 2, 3, and 4 blades, including
  views, stale identity, downloads, screenshots, and validation inspection.

Run each accepted case directly:

```bash
source scripts/openvsp_env.sh
.venv/bin/bladegen build-propeller examples/propeller_two_blade.json --output output/propeller_two
.venv/bin/bladegen build-propeller examples/propeller_three_blade.json --output output/propeller_three
.venv/bin/bladegen build-propeller examples/propeller_four_blade.json --output output/propeller_four
```

Run all qualification gates:

```bash
./scripts/test_backend.sh
cd frontend
npm test
npm run build
npm run test:e2e
```

See [the acceptance matrix](SPRINT_04A_ACCEPTANCE_MATRIX.md) for requirement-level
traceability and [assembly conventions](PROPELLER_ASSEMBLY_CONVENTIONS.md) for
the authoritative coordinate and validation rules.
