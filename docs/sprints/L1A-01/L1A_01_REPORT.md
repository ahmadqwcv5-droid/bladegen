# L1A-01 — repository cleanup and same-blade baseline

Status: **L1A_BLADE_BASELINE_VERIFIED_AFTER_CLEANUP** within the tested single-blade scope. The exact user X-57 replay, direct old/new geometry comparison, complete backend rerun, and consolidated cross-sprint browser suite passed. Earlier failed and focused runs remain separately identified below.

## Preserved starting point

- Starting HEAD: `39ffb7229c834d9c1e19eab03b529a83f1e366a3`, branch `patch/fp02-c1-thickness-te-qualification`, 433 initial status entries, empty index. The uncommitted implementation was retained, not assumed to be in HEAD.
- New safe branch: `maintenance/l1a-01-blade-baseline`, same HEAD. No reset, stash, clean, commit, tag, merge or push.
- Pre-cleanup recovery checkpoint: `../L1A_01_local_checkpoint_6O4cInS9/source_only_checkpoint.tar.xz`; SHA-256 `074efda3f28a70a7b952c1396d1e153b85e190470237f0c4871ed2b637f40b82`, verified archive integrity. The adjacent directory contains original index/status, tracked binary patch, per-file hashes and modes. It excludes secrets, `.git`, `.tooling`, `.venv`, `node_modules`, old CAD outputs and immutable evidence; those were left in place, not deleted.
- The original user job `3970dc6383f1425b9726d5a9a00f4202` remains unchanged in `output/runs/`. Its raw BladeSpec SHA-256 is `3e63667eb208cfa1a2f60c8eec43ad4d0900ace0a351d2dc9a2c6cfffa81252a`; its full STEP SHA-256 is `1aefd53802607d7b91bd105c814a61e13f3b97641e28991c52c67e2f0648a5b8`.

## Directory map and migration

```text
bladegen/
├── README.md, .gitignore, package/config/lock files
├── backend/                 active API, neutral engineering package, tests
├── frontend/                active UI, unit and browser tests
├── scripts/                 maintained setup/launch/test; frozen optional diagnostics retained
├── examples/                supported illustrative projects
├── fixtures/                reference_user_x57/ and x57_manual_reference/
├── qualification/           FP02 assets and l1a_01/ contract/comparator/local evidence
├── vendor/openvsp_fixed_plane/ unchanged managed-runtime patch/lock
├── docs/
│   ├── README.md            navigation
│   ├── user/                maintained user guides
│   ├── developer/           maintained architecture and Arabic code map
│   ├── releases/level1a/    scope, migration plan/map/report
│   ├── sprints/README.md    chronological task index
│   └── sprints/<original-id>/ original prompts/reports/matrices
└── output/runs/             original and fresh jobs, retained locally
../00_research_archive/       unchanged pre-Sprint-01 research
```

The [plan](../../releases/level1a/MIGRATION_PLAN.tsv) and [machine-readable map](../../releases/level1a/migration_map.json) identify every old/new path, class, SHA-256, byte count, mode and reversible action. All **68** planned moves were collision-free and byte/mode verified at move time (795,903 bytes). All **59** historical/immutable moved files were rehashed successfully after cleanup; nine moved current guides are navigational documents, with the Arabic guide intentionally updated after its move. Four immutable ZIPs were moved without unpacking/rewrite. The supplied L1A ZIP passed integrity checks and all five supplied SHA256SUMS entries passed. The three exact handoff reference files now live in `fixtures/reference_user_x57/` with unchanged hashes. Original research/evidence trees and runtime installations were neither moved nor rewritten. The [migration report](../../releases/level1a/MIGRATION_REPORT.md) gives conflict-safe rollback instructions.

The [24 compatibility pointers](../../releases/level1a/COMPATIBILITY_LINK_PLAN.tsv) restore **97/97** original relative links in moved reports without modifying any archived report byte. They point to current guides, preserved screenshots/evidence, retained jobs or later corrective reports; no duplicate canonical report was created. A [final sweep](../../../qualification/l1a_01/evidence/20261016T115447Z_final/navigation_check_final.json) of the root README and 83 Markdown files under `docs/` resolved **220/220** local links.

Historical `FP02_BLOCKED` (5 PASS, 2 FAIL, 1 REJECTED) remains historical fact in its report. FP02-C1 later qualified 8/8 positive cases on the 900-second trial profile; original Q04 remains rejected. Existing full-propeller implementation and automated regressions are preserved, while the user's hands-on assembly acceptance and further propeller work are deferred.

## Exact user X-57 replay

The frozen [repeatability contract](../../../qualification/l1a_01/repeatability_contract.json) predates this build. The supported launcher was `./scripts/start_level1_trial.sh` with its unchanged 900-second worker budget, UI `http://127.0.0.1:5175`, API `http://127.0.0.1:8012`; the normal default remains 300 seconds. A new Playwright browser context used the visible **Open JSON** action and file chooser on `fixtures/reference_user_x57/blade_spec_X57.json`, verified the imported definition and current preview, exported the candidate, then explicitly clicked **Generate Blade** once. No React-state injection, CAD copy/repair or hand-typed substitute was used.

Final consolidated-suite job: `1d936f53c0f040b1b14a64267892cf3c`; worker elapsed **370.2 s**, status **succeeded**. Browser test downloaded `blade_spec.json`, `validation.json`, `engine_manifest.json`, `blade_preview.stl` and `blade_solid.step` through normal same-job links. It saved the [screenshot](../../../qualification/l1a_01/evidence/20261016T115447Z_final/same_blade/x57_qualified_after_cleanup.png) and a durable separate [STEP](../../../qualification/l1a_01/evidence/20261016T115447Z_final/same_blade/blade_solid.step) (86,046,021 bytes, SHA-256 `9d797d8dbd6cc9b1fbd7715a56881bcab16d80d93690a6a1c30176b228c71d12`). The downloaded STEP, input, validation and manifest SHA-256 values match the fresh job's server artifacts byte for byte. These generated artifacts are retained locally and Git-ignored, not represented as committed source. An earlier successful preliminary replay, job `2be932e41a2849c4ac2f6e8f3b171a2a`, remains in its original L1A evidence directory and is not substituted for the final suite result.

The unchanged definition is diameter `575.9200184294399 mm`, root `r/R=0.20238`, reference axis `x/c=0.5`, Normal rotation; two coordinate-profile stations at root/tip with zero physical TE; 40 PCHIP controls each for Chord/Twist/Rake/Skew; and two constant linear Thickness controls at `t/c=0.1305533776828919`. The supplied JSON, not rounded prose, is authoritative.

The fresh raw input bytes equal the supplied/user-job input; canonical submitted and resolved hashes equal `44363e7004604e39b0adfc2c098e58d5e0f807ab836ec41c530cf0a0be0f8bb7` and `975a3cbf8a7442328c7183e588deedc759f080b1d721c0b1a65fc126db3cce00`. Parsed input and complete resolved JSON are equal. Managed runtime fingerprint equals `af69cfbeb477880fd7caf13c3fbdef3a2f69f40430dafe4e5a330d9bb7836edd`; production source-set aggregate equals `d39ad693843ce8c317d7c0fd7812a98029ace8f6282bfb766518c77e75dfddd4`, both identical to the user's successful job. Runtime build/contract remain `openvsp-3.54.0-bladegen-fixed-plane.1` / `bladegen.fixed-radial-sections.v1`.

The [official new validation](../../../qualification/l1a_01/evidence/20261016T115447Z_final/same_blade/validation.json) is **PASS** at 41/41 original stations, including original inward root/tip samples and the two imported-profile gates. All 41 full station measurement records are exactly equal to the original, not merely within tolerance. New STEP after re-import: **1 solid, 1 shell, 6 faces, 0 free edges, closed shell, BRepCheck valid**. Volume is `46373.243509611435 mm³`; area `22170.68049735742 mm²`; bounding box min `[-29.250630433616713, 58.277346564874996, -19.579086588854913]` mm, max `[46.40917486979203, 287.82682781045, 43.040468872263425]` mm. Old/new volume, area and bounding-box differences are all **0**. New STEP round-trip flags pass and its round-trip record equals the original.

The [full comparison](../../../qualification/l1a_01/evidence/20261016T115447Z_final/same_blade/comparison_full_records.json) used the existing OCP `compare_steps` method on the two full STEP solids, same frame, 41 parameter samples per face, no alignment. Across **10,086** surface samples, RMS/P95/max deviation are each **0.0 mm**. Maximum old/new differences in actual chord, actual twist, axis error, measured TE, contour RMS/P95/max at any of 41 stations are each **0.0** in their respective mm/degree units. All frozen criteria passed. STEP file bytes differ, so byte equality was not used as the geometry test.

These are **internal input/CAD repeatability** results, not external NASA geometry comparison. External NASA surface fidelity remains **UNVERIFIED**. No aerodynamic, structural, manufacturing, arbitrary-geometry or desktop-portability claim is made.

## Regression and source identity

The final candidate is the same source/config/test candidate used by the consolidated X-57 job above. The trial launcher ran `./scripts/start_level1_trial.sh` on API `8012` and UI `5175`, with its existing 900-second worker budget; `./scripts/start_backend.sh` still defaults to 300 seconds. The owned trial services were stopped after the suite; neither port remained bound.

| Verification | Actual result | Retained evidence |
| --- | --- | --- |
| `./scripts/test_backend.sh` | **197 passed**, 1 dependency deprecation warning, **555.54 s**; no retry | [full backend log](../../../qualification/l1a_01/evidence/20261016T113703Z_focused/backend_full_final.log) |
| `cd frontend && npm test` | **160/160 passed** in 26 files, **25.14 s**; no retry | [unit log](../../../qualification/l1a_01/evidence/20261016T104455Z/frontend_unit_after_sync_fix.log) |
| `cd frontend && npm run build` | PASS, 48 modules, Vite build **198 ms** (the complete command wall duration was not separately captured) | [build log](../../../qualification/l1a_01/evidence/20261016T115447Z_final/frontend_build_final.log) |
| `.venv/bin/ruff check backend/api backend/bladegen backend/tests`; `bash -n scripts/*.sh`; `.venv/bin/python -m compileall -q backend/api backend/bladegen backend/tests` | All PASS; individual elapsed times not captured | [Ruff](../../../qualification/l1a_01/evidence/20261016T115447Z_final/ruff_final.log), [shell](../../../qualification/l1a_01/evidence/20261016T115447Z_final/shell_syntax_final.log), [compileall](../../../qualification/l1a_01/evidence/20261016T115447Z_final/compileall_final.log) |
| `source scripts/openvsp_env.sh` then `.venv/bin/bladegen doctor` | READY, managed fixed-plane build/contract confirmed | [doctor log](../../../qualification/l1a_01/evidence/20261016T115447Z_final/runtime_doctor_final.log) |
| Final cross-sprint Playwright command below | **17/17 passed, 0 failed, 0 skipped, 0 retries**, 17 attempts, **2,764,663.619 ms** (46 min 4.664 s) | [JSON result](../../../qualification/l1a_01/evidence/20261016T115447Z_final/browser/consolidated_results.json), [console log](../../../qualification/l1a_01/evidence/20261016T115447Z_final/browser/consolidated_console.log) |

The final browser command, run from `frontend/`, was:

```bash
set -o pipefail
FP02_EVIDENCE_RUN_ID=l1a_01_20261016T115447Z_final \
FP02_EVIDENCE_ROOT=../qualification/l1a_01/evidence/20261016T115447Z_final/browser \
L1A_EVIDENCE_ROOT=../qualification/l1a_01/evidence/20261016T115447Z_final \
L1A_EXTERNAL_SERVER=1 L1A_UI_PORT=5175 \
npx playwright test --config playwright.fp02.config.ts \
  --output ../qualification/l1a_01/evidence/20261016T115447Z_final/browser/test-results \
  2>&1 | tee ../qualification/l1a_01/evidence/20261016T115447Z_final/browser/consolidated_console.log
```

The first full backend run was **196/197** in **578.19 s** because a test still used the moved `docs/VALIDATION_POLICY.md` path; that test's relocated path then passed **13/13** focused before the complete 197/197 rerun. Two retained full frontend-unit attempts were **159/160** in **21.64 s** and **24.34 s**, due to test-only selector/input synchronization; the final 160/160 run followed test-harness corrections. The first consolidated browser run was **15 passed, 2 failed, 0 skipped/retries** in **2,562,165.303 ms**: the isolated-context path assumed old UI port 5174 and clipboard permission assumed origin 5174. Its [JSON result and traces](../../../qualification/l1a_01/evidence/20261016T104455Z/browser/) remain intact. A focused correction run passed **2/2** in **463,705.774 ms**, zero retries; it was not counted as a consolidated 17/17 result. The later complete 17/17 run above stands independently. Assertions, geometry limits and production logic were not weakened.

No production UI, schema, canonical resolver, geometry algorithm, native patch, solidification, tolerance or station policy changed. Cleanup code edits are limited to the relocated validation-policy test path, deterministic existing unit-test selectors/input scheduling, browser evidence/output routing and trial-origin test corrections. Test collection remains **197 backend** and **17 browser** cases; the preserved full-propeller path passed its automated browser and backend regressions without acquiring user-acceptance status.

Final tested HEAD is `39ffb7229c834d9c1e19eab03b529a83f1e366a3` on `maintenance/l1a-01-blade-baseline`. The [192-file source/config/test hash manifest](../../../qualification/l1a_01/evidence/20261016T115447Z_final/source_files_sha256_final.txt) (manifest SHA-256 `1033e28c555377e944e6f247fc4f78d7e441f39120202ea21776963cb156b19c`) passed `sha256sum --check` after the final suite. The scoped tracked source diff SHA-256 is `acddb9d4ce2ebb40e7f0f3427f086b11c9f536a24f98e726ea59f217fca7bd9a`. The [final Git status inventory](../../../qualification/l1a_01/evidence/20261016T115447Z_final/git_status_final.txt) has **141 porcelain entries** and **zero staged files**; this is an uncommitted working baseline, not a release or published revision.

Suggested later commit split, **not performed**: (1) documentation/index/migration and reference fixtures; (2) test-path/evidence harness plus qualification contract/comparator/report. A large generated STEP should remain a separate local artifact, not a source commit. Stop here after recording the final qualification result; do not start propeller development or another sprint.

Git publication note: the HEAD, dirty status and “not performed” wording above record the **qualification-time** state on 2026-10-16. A subsequent user-requested commit/push is a separate Git action; it does not retroactively change the measured source identity or turn the ignored full STEP into a tracked source file.
