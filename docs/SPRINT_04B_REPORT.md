# Sprint 04B — Efficient Engineering Input & Responsive Editing

## Outcome

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
