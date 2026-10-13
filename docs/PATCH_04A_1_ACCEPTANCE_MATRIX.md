# Patch 04A.1 Acceptance Matrix

> **Patch 04A.2 correction:** The original “fresh-session” and generic PASS/link
> checks did not prove browser-context isolation or bind acceptance to the newly
> submitted job. The historical 04A.1 results remain recorded below; the
> strengthened evidence and corrected acceptance status are in
> [the Patch 04A.2 matrix](PATCH_04A_2_ACCEPTANCE_MATRIX.md).

| Requirement | Evidence | Result |
| --- | --- | --- |
| Preserve strict nominal hub policy | Shared guidance/preflight; D=80 rejects and D=81 passes nominal screening | PASS |
| Dynamic actionable guidance | UI/module tests for D400/60 and D600 bound 120; live screenshot | PASS |
| Hub length not treated as radial repair | UI explanation; 90 × 30 accepted by measured CAD | PASS |
| Structured safe issues | API/preflight tests cover hub, bore, dimensions, count, nested blade, and non-object body | PASS |
| One shared 2/3/4 runtime policy | API, pipeline, builder, capability endpoint, and UI use the same tuple | PASS |
| Unsupported count rejected early | API creates no job; pipeline creates no output and never calls reference build | PASS |
| Draft/history/generation separated | App state model, focused unit sequence, and real-browser historical-result evidence | PASS |
| Revision-safe asynchronous validation | Delayed-success test edits the design and retains Modified status | PASS |
| Complete BladeSpec open | Structure parser and round-trip test restore blade with neutral assembly baseline | PASS |
| Complete PropellerSpec open/export | Custom name, assembly, coordinates, null override, grid sizes, interpolation, and precise values tested | PASS |
| Atomic invalid import | UI tests preserve current name, hub, assembly baseline, and do not build | PASS |
| Complete reset and mode preservation | UI tests restore imported hub/name and retain assembly through mode switches | PASS |
| Exported project fresh-session rebuild | Live Playwright download, fresh page import, field verification, and real rebuild | PASS |
| 60 × 30 rejection creates no CAD job | Unit and browser request-count assertions | PASS |
| Real 2-blade 90 × 30 CAD | CLI PASS plus isolated real integration test | PASS |
| One valid closed STEP after re-import | 1 solid, 1 shell, 0 free edges, closed, BRep valid | PASS |
| Positive overlap and no unsupported collision | Both overlaps about 1381.2065 mm³; outside-hub intersection 0.0 mm³ | PASS |
| Correct through-bore | Two 6.0 mm boundaries; residual material 0.0 mm³ | PASS |
| STEP mass/bbox round-trip | Volume delta 3.92e-8 mm³; bbox max delta 7.44e-11 mm | PASS |
| Existing blade geometry gates preserved | Reference geometry validation PASS; algorithms/tolerances unchanged | PASS |
| Frontend regression/build | 22 files / 116 tests; production build passed | PASS |
| Backend regression/lint | 135 fast tests; Ruff passed; focused real test passed | PASS |
| Real browser evidence | Required sequence passed in 5.2 min; four screenshots | PASS |
| Historical archive unchanged | No file under 00_research_archive modified | PASS |

All required patch gates pass. The recommendation remains the existing
OpenVSP reference-blade pipeline followed by authoritative OCP assembly,
Boolean validation, STEP export, and STEP re-import qualification.
