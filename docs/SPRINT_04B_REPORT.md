# Sprint 04B — Efficient Engineering Input & Responsive Editing

## Closure update — 2026-10-14 (authoritative)

### Decision

The focused Sprint 04B closure has three deliberately separate results:

- **Input fidelity and responsive Apply: PASS.**
- **Official internal CAD qualification: FAIL — TIMEOUT.**
- **External NASA geometry fidelity: UNVERIFIED / NOT RUN.**

The user's hands-on retest confirms that **Add Control Point is now very
fast** on their machine. That successful optimization was preserved. This
closure did not change the prepared evaluator, geometry engine, CAD
tolerances, OpenVSP/OCP operations, source coordinates, or fixture values.

The code under test was based on commit
`1cdb564a2eb92b0171acbab705b41ca63b57416c` on
`sprint/04b-efficient-engineering-input`. No commit was requested, so the
run is recorded as a dirty working tree rather than being mislabelled as a
clean tested commit. The run evidence records Git porcelain status, tracked
production patch SHA-256
`86654d26ce5862bc415f9a3d042a994bac17a6752739fce660f6a31865affafa`,
and exact test/helper source hashes.

Current handoff Git status is intentionally dirty: modified closure files are
`docs/SPRINT_04B_ACCEPTANCE_MATRIX.md`,
`docs/SPRINT_04B_REPORT.md`, `frontend/src/App.tsx`,
`frontend/src/Sprint04B.test.tsx`, `frontend/src/api/client.ts`, both bulk
dialog components, and the distribution parser/tests. Untracked inputs and
evidence are `AUDIT_REPORT.md`, both supplied ZIPs,
`fixtures/x57_manual_reference/`, `docs/evidence/`,
`frontend/e2e/sprint04b-closure.spec.ts`,
`frontend/e2e/sprint04b-x57.spec.ts`, and
`frontend/e2e/x57Evidence.ts`. The ignored exact run directory and preserved
407 MB trace remain under `output/runs/a93b281c29b640afaa6bad698d64a61b/`.

### Fixture gate

`X57_Fixtures_For_Sprint04B.zip` was found at repository root with SHA-256
`c0dd93581ddb02db21a49fe16e8157e35ba3359cc5f19ef8720253e29326e9fd`.
All six members were below `fixtures/x57_manual_reference/`. Existing
destination files were byte-compared with the ZIP entries before
`unzip -n`; every file was identical, so nothing was overwritten.
`sha256sum -c SHA256SUMS.txt` returned five `OK` results:

| File | SHA-256 |
| --- | --- |
| `README_AR.md` | `fb41fa877decf30ec4dfeeb62b8a33b7fb74733dfe1724622fa19e764588c339` |
| `x57_hlp_airfoil.csv` | `ae38d1a5283c9bb61bcda9ef53c1a62c0f05eb32dd6b32609ef7c7d44db26238` |
| `x57_hlp_control_points_mm.csv` | `17540f3100fce406b3aaf5808a71fc98e17b1a1bfaca5c37899cfc0fa3931180` |
| `x57_hlp_control_points_normalized.csv` | `060bc2ae7c4c70e9d920534bb189f4cf636054e154a00d75faa18ef4f2830fba` |
| `manifest.json` | `fd5ede643a8a32cf24a52fe241c270f7affedf4f317ac4b3ca7f6768f60d9584` |

The independent-review ZIP was used read-only. Its source snapshots and
`x57_candidate_HELPER_ONLY.json` were not used as production source or as
the UI candidate.

### Narrow corrections

Pending Apply is now owned by each distribution/station dialog through an
`AbortController`. Cancel/unmount aborts the request; the application passes
the signal to `/api/validate` and rechecks it before history or BladeSpec
commit.

The browser regression delays validation, clicks Cancel, releases the late
successful response, waits for the route to settle and the editor to return
to `Ready`, then exports the complete BladeSpec. Distribution and station
cases match the exact pre-operation JSON, leave Undo disabled, and remain
usable. Component regressions also compare every curve/station value,
preview-call count, and history label after settlement. No arbitrary sleep is
used.

The CSV lexer rejects quotes inside unquoted fields such as `6"4"`,
characters after a closing quote, hexadecimal syntax, and values outside the
documented decimal/scientific grammar. Correctly quoted numerics such as
`"64"` remain accepted.

### Real X-57 UI workflow and fidelity

The final workflow used only visible controls and supplied files: global
fields, two-station setup, actual airfoil upload with Normalize off,
application to both stations, actual 40-row distribution upload/review,
Apply, browser Export JSON, and one explicit Generate Blade click. No
prepared BladeSpec was imported or injected.

| Check | Result |
| --- | --- |
| Globals | Exact D=575.9200184294399 mm, root=.20238, x/c=.5, normal |
| Stations | 2 exact endpoint stations, TE=0 mm |
| Airfoil | 74 upper + 67 lower points/station; 282/282 coordinate pairs exact; max error 0 |
| Chord/Twist/Rake/Skew | 40 controls each, PCHIP, exact radii and exact physical-sheet conversions |
| Maximum physical round trip | Chord 7.105427357601002e-15 mm; Rake 1.7763568394002505e-15 mm; Skew 3.552713678800501e-15 mm; Twist 0 deg |
| Maximum normalized-sheet delta | radius 2.220446049250313e-16; Chord 1.734723475976807e-16; Twist 7.105427357601002e-15 deg; Rake 1.6653345369377348e-16; Skew 1.8041124150158794e-16 |
| Thickness | Linear, 2 points, exported product ratio exact |

Thickness remains a documented representation difference: source-native
`0.1305067267946498`, product coordinate measurement
`0.1305533776828919`, delta `0.000046650888242100175` ratio or
`0.0046650888242100175` percentage points. Coordinates were not changed.
Equal controls also do not prove native OpenVSP PCHIP and the product's
SciPy/linearized representation coincide between controls.

### Apply-to-current-preview performance

Timing starts on the actual browser Apply click and ends after the matching
successful validation response, matching canonical-preview response, and
current-preview UI state.

| Measurement | Result |
| --- | ---: |
| Cold first Apply | 412.5 ms |
| Warm repetitions | 20 |
| Warm median | 396.20000000298023 ms |
| Warm p95 | 429.86500000283127 ms |
| Warm maximum | 480.5 ms |
| Target | p95 <= 1000 ms — PASS |

Every Apply issued exactly one validation, one preview, and zero builds. Each
of 20 intervening Undo cycles issued one preview and no validation/build.

### Explicit generation and genuine failure

The UI submitted exactly one CAD job:
`a93b281c29b640afaa6bad698d64a61b`. Exported, submitted, and generated
specifications are canonically identical. The job reached final STEP geometry
validation but failed after 300.2 seconds:

> Build timed out after 300 seconds during Validating final STEP geometry

The job was not retried with modified source or weakened validation. No
official `validation.json` exists, so full internal geometry qualification
is **incomplete** and must not be called PASS.

- exported candidate SHA-256:
  `45bccd02f73388cd1d6a94c16b870e9f5f9931849834e83eef6f74202d66b737`;
- submitted/generated raw spec SHA-256:
  `775e7bd571c815ea88aa8086208f50eb4663375d5953414178f7e753d5425d10`;
- canonical JSON SHA-256 for all three:
  `2b0abd8c54bb62acb7e8d0220d3f82b699fea1d7400255283cc237983a5d875b`;
- STEP: 86,032,477 bytes, SHA-256
  `43c2cd72bebcd3949e0fe0b210aaac9ccbf6918952743fd109ecb0cac2e401d6`;
- preserved trace SHA-256:
  `f9b029f547cad786a4a3092091d5bf2b6be319ed4442e603a3038985ef6b7c9c`.

A separate read-only call through the project's authoritative OCP
`read_step`/`inspect_shape` APIs found one SOLID, one shell, six faces,
zero nondegenerate free edges, closed/BRep-valid topology, area
21,862.951747858962 mm², adaptive volume 46,228.517992522764 mm³, and
extent 75.65972276513737 × 229.75298676162353 × 62.61955159867777 mm.
This is a **partial topology PASS only**; it does not replace the missing
complete pipeline geometry validation. The fixed-rule volume diagnostic was
44,930.54829673597 mm³ (fixed minus adaptive:
−1,297.9696957867927 mm³), so the adaptive volume is a post-failure
diagnostic, not an accepted pipeline result.

| Dimension | Classification |
| --- | --- |
| Input fidelity | PASS |
| Apply performance | PASS |
| Standalone retained STEP topology | PASS (partial evidence) |
| Official internal CAD qualification | FAIL / INCOMPLETE — timeout |
| External NASA geometry fidelity | UNVERIFIED / NOT RUN — no official reference geometry in fixture |

### Closure verification

| Suite | Exact command | Result | Duration |
| --- | --- | --- | ---: |
| Frontend unit/component | `cd frontend && npm test -- --run` | 26 files; 160 passed | 14.68 s |
| Backend non-integration | `cd backend && ../.venv/bin/pytest -m "not integration" -q --durations=0` | 149 passed, 11 deselected | 2.18 s |
| Ruff | `cd backend && ../.venv/bin/ruff check bladegen api tests` | PASS | <1 s |
| Production build | `cd frontend && npm run build` | 48 modules; PASS | 0.63 s |
| Cancellation browser | `cd frontend && npx playwright test e2e/sprint04b-closure.spec.ts --project=chromium` | 1 passed | 4.4 s |
| Real X-57 UI/CAD | `cd frontend && npx playwright test e2e/sprint04b-x57.spec.ts --project=chromium` | 1 failed at genuine CAD timeout after UI/input/performance passed | 5.6 min |

Before the final qualification, one deliberately interrupted smoke attempt
stopped before distribution/CAD after exposing a Rotation selector issue; it
created no job. Two subsequent authoring attempts also stopped before
distribution Apply/CAD because Chromium evicted the airfoil-import response
body from its inspector cache.
The final harness verifies rendered UI plus the persisted profile through a
read-only endpoint; no product assertion was weakened. Failure trace, video,
screenshot, and error context are preserved under the exact ignored job.

Evidence:

- [run summary](evidence/sprint04b/x57/evidence_summary.json)
- [exported candidate](evidence/sprint04b/x57/exported_candidate.json)
- [submitted specification](evidence/sprint04b/x57/job/submitted_blade_spec.json)
- [generated specification](evidence/sprint04b/x57/job/blade_spec.json)
- [retained STEP](evidence/sprint04b/x57/job/blade_solid.step)
- [partial topology inspection](evidence/sprint04b/x57/partial_topology_inspection.json)
- [candidate screenshot](evidence/sprint04b/x57/x57_candidate_current.png)
- [preserved trace](../output/runs/a93b281c29b640afaa6bad698d64a61b/playwright_failure/trace.zip)

Closure classification: **PARTIAL PASS — INPUT/PERFORMANCE PASS; X-57 CAD
JOB FAILED ON TIMEOUT; EXTERNAL NASA FIDELITY UNVERIFIED.**

## Original Sprint 04B outcome (historical; superseded by closure above)

Sprint 04B is implemented and regression-qualified for generic engineering
inputs. An engineer can paste or upload a multi-distribution table, review
mapping/units/interpolation, apply it as one transaction, create a bounded set
of airfoil stations, apply a profile to selected stations, continue exact
table editing, export/open the neutral definition, and explicitly generate a
qualified blade or propeller.

The result is a **conditional pass**, not a strong X-57 acceptance pass. The
required `fixtures/x57_manual_reference` pack is absent from this workspace.
Its hashes, actual 40-row source values, source profile, exported X-57
candidate JSON, and X-57 CAD result therefore cannot be truthfully produced.
No archived or invented data was substituted. The real-control browser
qualification uses a clearly labelled deterministic synthetic 40-row input;
it proves the product workflow and CAD gates, not NASA geometry fidelity.

Work was performed on branch `sprint/04b-efficient-engineering-input`, based on
HEAD `30d85b2cc8d696ed7f1ea5461ad205557fe2743b`. The implementation remains an
uncommitted working tree because this task did not request a commit or merge.
No path under `00_research_archive` was modified.

## Delivered workflow

### Distribution input

- **Import Distributions** accepts an actual UTF-8 CSV file or ordinary
  Ctrl/Cmd+V tab-separated spreadsheet paste.
- Exact known headers map Chord/Twist/Rake/Skew/Thickness with explicit units;
  `row` is shown as informational and unknown columns require explicit
  exclusion.
- The review exposes source, row count, target distributions, units,
  interpolation, domain, old/new counts, and data preview before Apply.
- Physical Chord/Rake/Skew values use the reviewed immutable diameter snapshot;
  stale dimension/design snapshots reject on Apply.
- Partial replacement, separate per-distribution interpolation, and independent
  grids are supported. Thickness, stations, dimensions, and assembly remain
  unchanged unless explicitly included.
- Parsing and candidate construction do not mutate state. A successful Apply
  performs one validation request, at most one canonical preview refresh, one
  history entry, and zero CAD requests.
- Cancel, malformed input, backend rejection, stale response, and no-op paths
  preserve committed state. Undo/Redo treats the bulk replacement as one edit.
- Focused numeric inputs show exact stored precision while editing.

The complete contract is documented in
[BULK_INPUT_FORMATS.md](BULK_INPUT_FORMATS.md).

### Airfoil stations and profiles

- **Set Up Airfoil Stations** supports 2–64 uniformly spaced stations or an
  explicit nonuniform normalized list.
- The user deliberately chooses an existing source profile, common physical TE,
  retention of matching stations, and whether to replace Thickness with a
  reviewed two-point constant.
- The review shows exact radii, old/new counts, retained/assigned counts, TE,
  and Thickness coordination before one atomic Apply.
- Station checkboxes and **Apply Profile to Selected Stations** provide batch
  assignment without creating a profile per distribution row.
- NACA nominal/override and imported-coordinate natural-thickness semantics
  continue through the canonical backend validation.

### Evaluator optimization

`PreparedCurveEvaluator` owns one validated immutable Linear or SciPy PCHIP
evaluator and provides scalar and array evaluation. The resolver prepares the
five blade curves once per request and reuses them for adaptive probes, exact
control restoration, airfoil-section resolution, and the unchanged
5,001-location verification grid. Design preview reuses the same request-local
evaluators and vectorizes its chart locations.

No tolerance, verification density, control value, interpolation definition,
semantic preflight, OpenVSP geometry operation, OCP topology operation, or CAD
gate was weakened. Mathematical equivalence tests cover knots, near-knots,
endpoints, dense and deterministic random queries, sign-changing curves,
Linear, and PCHIP. Constructor instrumentation proves five PCHIP instances for
five PCHIP distributions per request.

Measured before/after and interactive results are in
[SPRINT_04B_PERFORMANCE.md](SPRINT_04B_PERFORMANCE.md).

## Real-control browser evidence

The final test used browser file upload, the browser clipboard and Control+V,
dialog review/Cancel/Apply controls, existing Undo/Redo, exact numeric input,
Export JSON, a new isolated browser context, and explicit build buttons. It did
not inject project JSON into application state or call build before the user
action.

The deterministic synthetic source has 40 shared radii from 0.2 through 1.0;
Chord 80→30 mm, Twist 30→5 degrees, Rake −2.5→1.75 mm, and Skew −1.25→2.5 mm.
Both endpoint stations use deliberately selected NACA 0012, TE=0, and an
explicit two-point constant Thickness distribution. One Chord value was then
edited exactly to `78.7654321` before export/open and CAD generation.

Evidence:

- [Pasted TSV review](screenshots/sprint04b/paste_review.png)
- [Four 40-control distributions applied](screenshots/sprint04b/forty_row_applied.png)
- [Downloaded definition opened in an isolated context](screenshots/sprint04b/isolated_import.png)
- [Qualified blade result](screenshots/sprint04b/qualified_blade.png)
- [Qualified propeller result](screenshots/sprint04b/qualified_propeller.png)

Playwright also re-ran the existing narrow viewport numeric-table case and the
Sprint 03B narrow CAD-viewer case. The new workflow was repeated in focused and
consolidated runs. The user's later hands-on retest is still required; automated
evidence does not prove that every perceived editing friction is resolved.

## CAD qualification

The following exact jobs belong to the final consolidated Playwright run. Job
artifacts remain under ignored `output/runs`; their IDs prevent an older result
from satisfying the tested build.

### Synthetic blade job `25f9c4adf64f45a0b5baf311d3b41040`

| Measurement after STEP re-import | Result |
| --- | ---: |
| Status | PASS |
| Shape / solids / shells / faces | SOLID / 1 / 1 / 8 |
| Closed shell / BRep valid / free edges | true / true / 0 |
| Surface area | 18,794.19979531136 mm² |
| Volume | 43,173.686527240505 mm³ |
| Bounding-box extent | 41.35558371032071 × 160.1752508853957 × 69.75720996486619 mm |
| Round-trip volume delta | 5.318725015968084e-9 mm³ |
| Round-trip maximum bbox delta | 7.275957614183426e-12 mm |

### Synthetic three-blade propeller job `a25f2d23a0db4857b88c85a35618895a`

| Measurement after STEP re-import | Result |
| --- | ---: |
| Status | PASS |
| Shape / solids / shells / faces | SOLID / 1 / 1 / 28 |
| Closed shell / BRep valid / free edges | true / true / 0 |
| Surface area | 80,166.27097229194 mm² |
| Volume | 406,699.16175732994 mm³ |
| Bounding-box extent | 50.22930681707611 × 321.5371864127662 × 361.39321328417907 mm |
| Round-trip volume delta | 1.3154931366443634e-8 mm³ |
| Round-trip maximum bbox delta | 5.0746962187986355e-11 mm |

These results qualify the synthetic custom workflow only. They are not an X-57
or NASA reference comparison.

## Verification results

Focused development runs are not added to the suite totals below.

| Suite | Exact command | Consolidated result | Duration |
| --- | --- | --- | ---: |
| Backend non-integration | `cd backend && ../.venv/bin/pytest -m "not integration" -q --durations=0` | 160 collected; 149 passed, 11 deselected, 0 failed | 1.76 s |
| CAD integration | `cd backend && source ../scripts/openvsp_env.sh && ../.venv/bin/pytest -m integration -q --durations=0` | 160 collected; 11 passed, 149 deselected, 0 failed | 515.25 s |
| Frontend unit/component | `cd frontend && npm test -- --run` | 26 files; 156 passed, 0 failed | 14.20 s |
| Production build | `cd frontend && npm run build` | 48 modules; passed | 0.646 s |
| Ruff | `cd backend && ../.venv/bin/ruff check bladegen api tests` | all checks passed | — |
| Cross-sprint Playwright | `cd frontend && npm run test:e2e` | 12 collected; 12 passed, 0 failed, 0 skipped, 0 retries | 25.2 min |

The Playwright result is one final invocation using Chromium, one worker,
`fullyParallel: false`, and no configured retries. Four earlier focused
authoring runs exposed ambiguous prefix locators (`40 rows`, `Chord value 1/2`);
the assertions were made exact without weakening product checks. A subsequent
focused run passed in 2.7 minutes, followed by the consolidated 12/12 result.
The existing Starlette/httpx deprecation warning and Vite large-chunk advisory
remain; neither is introduced as a functional acceptance failure.

## X-57 provenance limitation

At qualification time `fixtures/x57_manual_reference` did not exist. Therefore:

- no fixture SHA256 values can be reported;
- the supplied profile and exact 40 source rows could not be imported;
- no real X-57 candidate JSON or X-57-specific build/failure artifact was
  created;
- no claim is made about NASA geometry matching or the documented
  source/product thickness representation difference.

The preexisting `00_research_archive` was intentionally left outside scope and
was not used as an undocumented substitute. Once the named fixture pack is
placed in the repository unchanged, the same UI sequence must be rerun and its
hashes, exported neutral definition, exact job artifacts, and any geometry
fidelity result appended as separate evidence.

## Acceptance classification

Input usability, numerical correctness, generic CAD validity, and preservation
of prior regressions pass. External X-57 provenance/fidelity evidence is
blocked by the missing input pack. Sprint 04B is therefore **CONDITIONAL PASS —
X-57 fixture qualification pending**, not a strong final pass.
