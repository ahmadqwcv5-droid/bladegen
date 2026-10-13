# Patch 04A.2 — Semantic Preflight and Job-Scoped Verification

## Outcome

Patch 04A.2 is a **PASS WITH LIMITATIONS**. The required product behavior is
implemented and verified: inconsistent blade semantics are rejected before CAD
queueing, an omitted initial azimuth normalizes to 0 degrees, browser acceptance
is tied to the newly submitted job and its artifacts, and save/open/rebuild uses
an isolated frontend context.

The qualification is reporting-only. The latest complete 11-test Playwright run
passed 10 tests and exposed one initialization race in the camera test itself.
After synchronizing that test with the asynchronous example load, the corrected
camera workflow passed independently with real 3-, 5-, and 8-section builds.
There was no final single-command 11/11 rerun after that test-only correction.

The work is on branch `patch/04a.2-semantic-preflight-job-verification`. The
tested base commit is `8b7ab930289df1e66f2c4b34720644136aa93b41`; the Patch
04A.2 working tree is intentionally uncommitted and unmerged at delivery. No
path under `00_research_archive` changed.

## Reproduced defects and shared semantic boundary

The original preflight accepted structurally valid PropellerSpecs whose nested
BladeSpecs would fail later in the canonical resolver. Regression cases capture
both observed gaps:

- NACA 4412 without an override at a station where the thickness curve is 0.20;
- NACA 0000 without an override and with a positive thickness curve.

After raw assembly checks and Pydantic parsing, `validate_propeller_payload()`
now calls the existing `resolve_airfoil_sections()` boundary. This is the same
canonical code used by generation for NACA nominal/override compatibility,
coordinate-profile natural thickness, mathematical NACA support, and physical
trailing-edge intent. It resolves section coordinates only; it does not perform
adaptive full-curve resolution, launch OpenVSP, construct OCP shapes, write
files, or create a job.

`BladeSemanticError` carries a field and structured context rather than relying
on parsed exception text. API issues use the stable `invalid_blade_spec` code
and can identify station index/r/R, selected airfoil, evaluated thickness, and
the nominal, override, or natural expected thickness. Generation-time resolver
checks remain in place as defense in depth.

Tests prove that semantic failures return controlled 422 responses from both
validate and direct build, do not invoke `jobs.submit`, and fail the direct
Python pipeline before output-directory or reference-blade generation. A valid
NACA 4412 override of 0.20 and a matching 0.20 curve remains accepted. Imported
coordinate profiles retain their existing natural-thickness policy and are not
rescaled.

A successful preflight is described as passing input structure and non-CAD
engineering consistency. Boolean overlap, collision, bore, fusion, and final
STEP topology remain build-time qualifications.

## Initial-azimuth policy

The existing `AssemblySpec` default is now applied consistently:

- an omitted `initial_azimuth_deg` becomes `0.0`;
- explicit numeric zero remains zero;
- an explicit finite value such as `17.5` is retained exactly;
- explicit null, strings, booleans, and non-finite values are rejected.

The raw preflight defaults only an absent key. The frontend parser follows the
same rule and normalizes a successfully imported omitted value to 0.0. No schema
version changed, and no unrelated required field gained a fallback.

## Job-scoped browser verification

The shared Playwright helper registers the build-response listener before the
Generate click, requires HTTP 202 and `queued`, captures the complete 32-character
job ID, and polls `/api/jobs/{job_id}`. It fails immediately if that exact job
fails, waits for that exact ID to succeed, and then requires the displayed result
container to expose the same full ID. Artifact URLs and downloaded JSON are
checked against that job rather than against a generic PASS label or an older
successful link.

Component tests cover an adversarial identical-input sequence: result A remains
visible while B is pending, B alone can satisfy the new request, a failed B is
not masked by A, and a delayed A update cannot replace active B. The production
UI retains useful historical-result behavior; no test-only success state was
added.

All cross-sprint real-build specifications were migrated from generic progress
or success labels to exact job identity. The Sprint 04A test also verifies that
the final four-blade artifact belongs to the captured four-blade job.

## Isolated save/open/rebuild workflow

The strengthened real browser workflow executed:

~~~text
Build A (90 × 30) and verify job A
→ set hub diameter to 60 and reject without a build
→ retain A as historical evidence
→ restore 90 and build/verify distinct job B
→ export the complete PropellerSpec
→ browser.newContext() with no copied storage state
→ import only the downloaded document
→ verify mode, project/blade identity, distributions, airfoils, and assembly
→ build and verify distinct job C
~~~

The second context shares the running backend but not frontend cookies,
local/session storage, or browser context state. A separate semantic-invalid
API/import scenario verifies 422 rejection, atomic import, and no CAD request.

Screenshots from the strengthened workflow are retained at:

- [Build A](screenshots/patch04a2/assembly_a_90x30_success.png)
- [Rejected 60 mm draft retaining A](screenshots/patch04a2/invalid_60x30_historical_result.png)
- [Build B](screenshots/patch04a2/assembly_b_90x30_success.png)
- [Isolated-context import and Build C](screenshots/patch04a2/isolated_session_import_rebuild.png)

## New CAD evidence

The accepted input for all three jobs is project
`two_blade_propeller_hub_90x30`, blade `custom_blade_multi_airfoil`, diameter
400 mm, root r/R 0.20, two blades, hub 90 × 30 mm, shaft bore 12 mm, and initial
azimuth 0 degrees.

| Job | Role | Normalized spec SHA-256 | STEP SHA-256 | Validation SHA-256 |
| --- | --- | --- | --- | --- |
| `058269be5f2d433ca3d207a581bc9b38` | A | `27c9c6e163acf9cf03ddf9b5cf0f989ed7aae9ec1494536107bc5c4ef7a94d60` | `14294986cc0f13c0a526608f3f887761d8f2df0ae28c865ea1631121ccc9b139` | `2782900cc5491218bfe6ec32805dcf91c2c5d66f02ef4f2ffde42c09e3dcf784` |
| `41251b314e4e418db0834787d888d54b` | B | `27c9c6e163acf9cf03ddf9b5cf0f989ed7aae9ec1494536107bc5c4ef7a94d60` | `f49a15d136b04a58000f8177162fc3649913ae028cee2aca0e44bd696f25b3af` | `80e933361a4d06da26e3f5fa9e0641b77f9eb5313a5977eb1ca62966e416d4e9` |
| `e470c9fbd3954752ab61d6031e8e4a15` | C | `27c9c6e163acf9cf03ddf9b5cf0f989ed7aae9ec1494536107bc5c4ef7a94d60` | `c2540ff68305ca6f6c4c5c6748921d45c399b61e7c68930e276dc727202b108f` | `b26b9969624d1506f0c6c971ba13da93daca8e9690485b5f88769a99d9c5fbee` |

Distinct STEP bytes are expected and are not used as a geometry criterion. Each
job's `validation.json` reports the same qualified measurements:

| Measurement | Result |
| --- | ---: |
| Status | PASS |
| Placements / azimuths | 2 / 0°, 180° |
| Root/hub common volume | 1381.2065006890468, 1381.2065006898015 mm³ |
| Outside-hub blade collision | 0.0 mm³ |
| Copy-volume maximum delta | 7.275957614183426e-12 mm³ |
| Solids / shells / faces after STEP re-import | 1 / 1 / 20 |
| Closed shell / BRep valid | true / true |
| Non-degenerate free edges | 0 |
| Requested / measured bore radius | 6.0 / 6.0, 6.0 mm |
| Bore residual material / continuous | 0.0 mm³ / true |
| Surface area | 54132.84047780774 mm² |
| Adaptive Gauss–Kronrod volume | 261815.11278796682 mm³ |
| Bounding-box extent | 50.573775018916436 × 400.0432202905267 × 90.0000002 mm |
| STEP round-trip volume delta | 3.92028596252203e-8 mm³ |
| STEP round-trip bbox maximum delta | 7.440803528879769e-11 mm |

These values match the accepted baseline within the existing numerical gates.
No OpenVSP adapter, OCP Boolean, placement, hub/bore, curve, contour, tolerance,
or topology algorithm changed.

## Regression results

The following are suite totals, reported separately; focused reruns are not
added to them as extra unique tests.

| Suite | Command | Collected / result | Duration |
| --- | --- | --- | ---: |
| Backend non-integration | `cd backend && ../.venv/bin/pytest -m "not integration" -q --durations=0` | 158 collected; 147 passed, 11 deselected, 0 failed | 46.12 s |
| CAD integration | `cd backend && source ../scripts/openvsp_env.sh && ../.venv/bin/pytest -m integration -q --durations=0` | 158 collected; 11 passed, 147 deselected, 0 failed | 443.54 s |
| Frontend unit/component | `cd frontend && npm test -- --run` | 22 files; 122 passed, 0 failed | 15.34 s |
| Production build | `cd frontend && npm run build` | 43 modules; passed | 0.435 s |
| Ruff | `cd backend && ../.venv/bin/ruff check bladegen api tests` | all checks passed | 0.05 s |
| Cross-sprint Playwright, latest complete run | `cd frontend && npm run test:e2e` | 11 collected; 10 passed, 1 failed in pre-fix camera initialization | 23.3 min |
| Corrected camera workflow | `cd frontend && npx playwright test e2e/patch-camera.spec.ts` | 1 collected; 1 passed, 0 failed | 5.6 min |
| Strengthened 04A.2 workflow | `cd frontend && npm run test:e2e -- patch04a1.spec.ts --grep "90×30 project"` | 1 collected; 1 passed, 0 failed | 5.3 min |

The integration suite retained the 3-, 5-, and 8-section blades, NACA override,
imported analytic profile, 2/3/4-blade assemblies, and 90×30 two-blade case. One
existing Starlette/httpx deprecation warning and the existing Vite large-chunk
advisory remain. No test was removed, weakened, or silently deselected.

## Remaining limitations

- A final single-command Playwright 11/11 run was not repeated after the last
  camera test synchronization correction; the corrected test passed separately.
- Counts 5–8 remain valid contract values but unsupported for runtime builds.
- Preflight does not certify CAD Booleans, fatigue, balance, or manufacturability.
- The installed OpenVSP workflow remains qualified on Linux only.
- Generated job artifacts remain in the ignored `output/runs` workspace rather
  than source control; their identities and hashes above allow local review.
