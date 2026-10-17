# Sprint and task index

Each folder holds the original prompt (when found), report, acceptance matrix, and notes for one task family. Moved archival files are byte-identical to their originals; see the [migration map](../releases/level1a/migration_map.json). Historical statuses below are not rewritten by later fixes. `docs/evidence/`, `qualification/`, `output/runs/`, and the external `00_research_archive/` remain at their original locations because they contain integrity-bound or retained run evidence. Twenty-four [compatibility pointers](../releases/level1a/COMPATIBILITY_LINK_PLAN.tsv) keep all 97 original relative links in moved reports resolvable without changing their bytes. Archive links below resolve only in the local workspace where that sibling archive exists, not in a standalone Git clone.

| ID | Purpose and original result | Location / later resolution |
| --- | --- | --- |
| Pre-Sprint-01 CAD benchmarks | Research Tests 01–05 and `prompt.md`–`prompt5.md`; historical outcomes remain in their individual reports | [immutable archive inventory](../../../00_research_archive/ARCHIVE_README.md) |
| Spike 00A | OpenVSP X-57 single blade; STRONG PASS in the original research scope | [archived prompt](../../../00_research_archive/openVSP_prompt1.md) · [archived report](../../../00_research_archive/spike_00A_openvsp_x57_blade/SPIKE_00A_REPORT.md) |
| Spike 00A.1 | STEP solid qualification; OpenVSP-only did not produce a solid, OCP workflow documented | [archived report](../../../00_research_archive/spike_00A1_step_solid/SPIKE_00A1_REPORT.md); original prompt not found as a separate file |
| Spike 01 | Neutral BladeSpec→solid STEP; PASS | [archived prompt](../../../00_research_archive/openVSP_prompt2.md) · [archived report](../../../00_research_archive/spike_01_bladegen/SPIKE_01_REPORT.md) |
| Spike 01B | Custom user-defined blade; PASS with limitations | [archived prompt](../../../00_research_archive/openVSP_prompt3.md) · [archived report](../../../00_research_archive/spike_01B_custom_blade/SPIKE_01B_REPORT.md) |
| Spike 01C | Canonical curve resolution; STRONG PASS | [archived prompt](../../../00_research_archive/openVSP_prompt3_1.md) · [archived report](../../../00_research_archive/spike_01C_curve_resolution/SPIKE_01C_REPORT.md) |
| Spike 01D | Multi-airfoil/finite TE; STRONG PASS in both phases | [archived prompt](../../../00_research_archive/spike_01D.md) · [archived report](../../../00_research_archive/spike_01D_multi_airfoil_te/SPIKE_01D_REPORT.md) |
| 01 | Initial Level 1 Alpha implementation; original validation in report | [01](01/) |
| 02 | UI + dynamic stations; PASS with limitations | [02](02/) |
| 02.1 | Reliability/progress; STRONG PASS | [02.1](02.1/) |
| 02.1.1 | Null/progress/camera corrections; STRONG PASS | [02.1.1](02.1.1/) |
| 03A | Airfoil library and visual design; STRONG PASS | [03A](03A/) |
| 03A.1 | Profile inspection corrections; STRONG PASS | [03A.1](03A.1/) |
| 03B | Station inspection and comparison; STRONG PASS | [03B](03B/) |
| 03B.1 | Station inspection corrections; STRONG PASS | [03B.1](03B.1/) |
| 03C | Transactional curve editing and undo/redo; original matrix PASS, repeated-drag defect later corrected by 03C.1 | [03C](03C/) → [03C.1](03C.1/) |
| 03C.1 | Continuous editing/history correction; later patch to 03C | [03C.1](03C.1/) |
| 04A | Full-propeller automated CAD evidence for 2/3/4 blades; STRONG PASS within measured scope | [04A](04A/) |
| 04A.1 | Assembly preflight and project save/open; PASS, with proof corrected by 04A.2 | [04A.1](04A.1/) → [04A.2](04A.2/) |
| 04A.2 | Exact-job browser proof and stale-result fixes; STRONG PASS | [04A.2](04A.2/) |
| 04B | Efficient engineering input; input/Apply PASS, initial X-57 CAD TIMEOUT, NASA external fidelity UNVERIFIED | [04B](04B/) → [FP01](FP01/) for fixed-plane CAD |
| X57 contour | Diagnostic isolation, not a product acceptance | [prompt](X57-CONTOUR/) · [immutable results](../evidence/sprint04b/x57/contour_isolation/) |
| X57 root cap A/B | Diagnostic A/B, not a product acceptance | [prompt](X57-ROOT-CAP-AB/) · [immutable results](../evidence/sprint04b/x57/root_cap_ab/) |
| X57 surface→STEP | Localization decision, not a product acceptance | [prompt](X57-SURFACE-STEP/) · [immutable results](../evidence/sprint04b/x57/live_surface_localization/) |
| X57 rib/loft | Diagnostic localization, not a product acceptance | [prompt](X57-RIB-LOFT/) · [immutable results](../evidence/sprint04b/x57/rib_placement_localization/) |
| X57 AB02 | Auto-rotation ablation, not a product acceptance | [prompt](X57-AB02/) · [immutable results](../evidence/sprint04b/x57/rotation_ablation/) |
| FP01 | Managed fixed-plane runtime integration; FP01_INTEGRATION_PASS | [FP01](FP01/) |
| FP02 | Original qualification blocked: 5 PASS, 2 FAIL, 1 REJECTED | [FP02](FP02/) → [FP02-C1](FP02-C1/) for the corrected positive cases |
| FP02-C1 | Corrected qualification: 8/8 positive cases and 16/16 browser tests; READY_FOR_USER_TRIAL at 900 s | [FP02-C1](FP02-C1/); original Q04 remains intentionally rejected |
| L1A-01 | Repository cleanup and same user-tested blade replay; see current report for measured result | [L1A-01](L1A-01/) |

The earlier [STEP validation diagnosis](../evidence/sprint04b/x57/validation_diagnostics/) and [Sprint 04B independent review](04B/AUDIT_REPORT.md) are also indexed here. These remain historical investigations, not retroactive PASS claims. Original prompts not found in the working repository have not been reconstructed; all discovered task prompts are listed in their family folders.
