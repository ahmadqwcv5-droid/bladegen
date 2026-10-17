# L1A-01 — Repository Cleanup, Blade Baseline Freeze, and Code Map

## 1. Deliver the agreed milestone, not a new feature sprint

Work in the existing BladeGen workspace.

The milestone is **Level 1A — Stable Single-Blade Baseline within the tested scope**.
It is NOT completion of the whole Level 1 product and NOT a claim that arbitrary
blade geometry is supported.

The user personally generated a simple blade, changed its Twist, regenerated it,
and successfully imported/generated the X-57-derived blade through the UI. They
reported substantially easier editing and a good import experience.

Full-propeller functionality already exists and has automated evidence. Preserve
it and its tests, but its further development and the user's hands-on acceptance
are deferred. Do not remove, hide, redesign or relabel it as fully user-accepted.

This task has three outputs:
1. A navigable repository with all sprint/patch/spike task documents discoverable
   under one indexed location, without losing history.
2. A new successful build of the SAME user-tested X-57 blade after cleanup.
3. An identified baseline and a short code-reading map for the next learning step.

Implement the cleanup and verification, not planning alone. No native geometry
changes, feature development, dependency upgrades, performance rewrite, new
engineering schema or changed tolerances are authorized.

## 2. Preserve the actual working candidate before moving anything

Inspect actual HEAD, branch, index, tracked/untracked files and installed runtime.
Do not assume the old base commit contains the successful dirty-worktree fixes.

Create a safe branch such as maintenance/l1a-01-blade-baseline. Preserve all
existing work. No force-checkout, reset, clean, automatic stash, history rewrite,
commit, tag, merge, push or external publication.

Before modification, save a local recoverable snapshot of relevant source,
configs, docs and fixtures, including uncommitted/untracked implementation files.
Record staged/unstaged state, file hashes and an inventory. Keep the snapshot
outside the tree being reorganized and avoid recursive backup inclusion.
Do not put credentials, .env secrets, native installations or all old CAD outputs
in a distributable source/evidence ZIP.

Inventory files by purpose, not by name alone:
- Active application and engineering code.
- Maintained setup/run/test scripts.
- Current user/developer documentation.
- Sprint prompts, reports, acceptance matrices and planning notes.
- Active fixtures and qualification runners.
- Historical diagnostics/evidence and generated outputs.

Write a migration plan with source, destination, classification and reason, then
execute the reversible plan without asking the user to approve every normal move.
Preserve bytes/hashes for archival moves. Include file modes and symlink targets
where relevant. Never overwrite a destination conflict.

Do not touch .git internals, 00_research_archive, installed .tooling runtimes,
.venv, node_modules, original run directories or immutable evidence bundles.
Normal test output goes to NEW directories, not historical evidence paths.

## 3. Use a small, recognizable layout

Keep active backend/frontend package roots and existing test locations stable.
Do not flatten source code, move everything into an archive, or repackage the
Python application merely to make the tree look cleaner.

Target organization, adapting existing names where necessary:

    README.md
    backend/                    # existing application/core/tests
    frontend/                   # existing UI/unit/browser tests
    scripts/                    # maintained setup, launch and test entrypoints
    tools/diagnostics/          # maintained optional diagnostic tools only
    examples/                   # supported illustrative projects
    fixtures/                   # unchanged source/reference inputs
    qualification/              # active repeatable qualification assets
    vendor/openvsp_fixed_plane/ # unchanged lock and native patch
    docs/
        README.md               # documentation landing page
        user/                   # current usage guide
        developer/              # architecture and code-reading map
        releases/level1a/        # scope, baseline and cleanup result
        sprints/
            README.md           # chronological index of all task families
            <original-id>/      # original prompt/report/matrix/notes
    output/runs/                # generated job outputs, retained locally
    00_research_archive/        # unchanged historical archive

Keep required project configs, lockfiles, license/notices, .github, .gitignore
and tool-instruction files at their required locations. Do not rename a config
just to remove it from the root.

Consolidate loose task documents under docs/sprints/, including numbered sprints,
FP integration/qualification work, X57 diagnostic tasks and patches. Preserve
original IDs and meaningful filenames; disambiguate collisions without overwriting.
Use subfolders, not one huge concatenated file.

The index must identify purpose, original result/status, current location and
which later task superseded a failure. Never rewrite a historical FAIL as PASS.
A missing original prompt is 'not found'; do not reconstruct it as historical fact.

Exceptions to physical consolidation:
- Never unpack/rewrite immutable evidence ZIPs or alter reports inside them.
- Leave documents inside 00_research_archive and integrity-bound evidence trees
  in place. Add explicit index entries to them instead of invalidating hashes.
- Record any other necessary exception and its reason; do not silently omit it.

For moved historical reports, preserve original bytes and add a migration map
or an adjacent navigation note. Update current README/guide links. Where an old
public path must remain usable, a clearly labelled pointer is acceptable; avoid
keeping two independently edited canonical copies. Historical absolute job paths
remain historical facts, not text to search-and-replace globally.

Move unused loose diagnostic scripts only after checking imports, CI, test
collection, runner paths and __file__/cwd assumptions. A script imported by an
active test is not dead code. Frozen scripts can remain in an indexed legacy
subdirectory; document their replay environment rather than silently modernizing
old evidence. Keep a necessary live helper at a maintained location with tests.

## 4. Clean code conservatively

Separate file moves from behavioral changes in the change log. Prefer no changes
to core numerical code, models, expected geometry, station policy, the native
patch or report acceptance logic.

Allowed code edits: necessary path/import updates, concise clarification comments,
and small demonstrably behavior-preserving cleanup. No mass rename, dependency
replacement, new abstractions, App.tsx rewrite, or deletion of the propeller path.

Do not delete code because one text search found no references; consider CLI,
dynamic imports, package data, tests and scripts. Archive uncertain historical
material. Do not run broad formatter/autofix commands over frozen diagnostics.

Retain active test coverage; relocation must not silently reduce collected tests.
Separate active-code lint from historical-script findings. Document exclusions by
purpose, not to hide newly failing maintained code.

Improve ignore rules only for genuinely regenerable outputs/caches. Ignoring an
already tracked file does not untrack it or shrink Git history. Do not run blanket
git rm --cached, garbage collection or history-filtering. Large tracked archives
can be inventoried for a separately approved storage cleanup; preserve them now.
No unique user file, failed-job evidence, license, source fixture or working
native runtime may be deleted as 'cleanup'.

Verify production/CI do not acquire imports from archival code. If code paths in
the implementation source-set change, update that identity honestly and keep
historical manifests immutable. Never force a new hash to equal the old one.

## 5. Freeze the correct X-57 reference

The primary reference is the USER'S successful UI job:

    3970dc6383f1425b9726d5a9a00f4202

Supplied handoff files (exact bytes, not rounded examples):
- blade_spec_X57.json
- validation_X57.json
- engine_manifest_X57.json

The raw input SHA-256 is:
3e63667eb208cfa1a2f60c8eec43ad4d0900ace0a351d2dc9a2c6cfffa81252a

The handoff ZIP contains these under reference_user_x57/. Verify its checksums.
Locate the corresponding original job in output/runs/ using its report/provenance.
Do not substitute the earlier failed STEP or a historical NASA/native model.

Read the actual runtime and implementation identity from the supplied manifest.
Its selected runtime is openvsp-3.54.0-bladegen-fixed-plane.1, contract
bladegen.fixed-radial-sections.v1. Preserve this runtime and fixed-plane behavior.

Preserve the submitted definition exactly: diameter 575.9200184294399 mm, root
0.20238, reference axis 0.5, Normal; two identical coordinate-profile assignments;
40 controls each for Chord/Twist/Rake/Skew with PCHIP; two constant Thickness
controls; zero physical TE at the two airfoil stations.

Verify identity using the existing raw/canonical/normalized hash conventions;
keep those different kinds of hashes labelled. Metadata serialization differences
are not permission to change engineering values or profile preparation.

Use existing valid evidence from this exact source/runtime as the pre-cleanup
baseline. If the actual implementation differs materially, record it before
cleanup and establish one identified pre-cleanup build with the unchanged input.
Do not silently treat an untested local revision as the user's tested baseline.

## 6. Verify cleanup without reopening qualification research

Freeze final source/config/test identities after cleanup. Run the established
backend tests (including their native regressions), frontend tests/build, active
lint/shell checks, runtime doctor, and relevant path/link/test-collection checks.
Existing propeller regressions remain regression protection, not new user acceptance.
Do not invent a new eight-case matrix or retest every historical experiment.

Run the supported browser regression suite once on the final candidate, with real
backend/runtime, zero retries and no silently dropped required tests. If a path or
synchronization failure requires correction, preserve it and distinguish a focused
rerun from the later consolidated result. Do not update historical screenshots or
logs in place; direct new evidence to this task's own output directory.

The decisive SAME-BLADE regression must run through the actual UI after cleanup:
1. Launch with ./scripts/start_level1_trial.sh using the unchanged 900-second
   worker budget. Preserve the ordinary 300-second default.
2. Use a new browser context and open the exact supplied blade_spec_X57.json
   through the visible JSON file input. This test is replay after cleanup;
   the existing bulk-import test remains separately covered.
3. Verify the definition, then explicitly Generate once. No injected React state,
   diagnostic binary, copied STEP, fabricated success or manual CAD repair.
4. Require a fresh job ID and complete same-job validation, engine manifest,
   STEP, preview and spec downloads through normal UI links.
5. Verify all 41 original station checks, imported-profile gates, original root/
   tip inward samples, one valid closed solid and existing round-trip acceptance.
6. Compare before/after definitions, resolved engineering vectors when available,
   native identity, all station measurements, topology, volume and bounding box.
   If the exact old STEP is available, also apply the existing direct geometric
   regression comparison in the same frame and sampling convention.

Freeze repeatability criteria BEFORE the post-cleanup run using existing project
practice. Same runtime/numerical behavior should reproduce measurements within
those criteria; a material difference is a regression even if both reports say PASS.
Do not widen criteria afterwards. Do not use a best-fit alignment to hide changes.
STEP bytes may differ due to metadata; compare geometry, not byte equality alone.

If the old full STEP is absent, report direct old/new STEP comparison as unavailable
and use the exact supplied input, original measurement records and preserved
numerical-source identity. Do not claim an unperformed comparison or ask the user
to type the blade again. Failure to bind the exact input/report reference is a blocker.

A real browser build may supply both suite evidence and the decisive regression
when its exact inputs and final candidate identity match. Avoid an unnecessary
second expensive build solely for a second report table.

Use bounded workers and truthful progress. Preserve logs/first failures. If the
new build times out at 900 seconds, record the failure; do not repeatedly increase
the budget or cut measurement work. Timings are observations, not speed targets.

## 7. Prepare concise documentation for understanding the code next

Create current docs, not an enormous second report collection:

- docs/releases/level1a/SCOPE_AND_STATUS.md:
  tested blade capabilities and limitations; user-reported simple/X-57 success;
  automated evidence versus hands-on acceptance; propeller follow-up deferred.
  State that 'any blade' is a direction, not demonstrated universal coverage.
- docs/developer/CODE_MAP_AR.md:
  a short Arabic map with REAL paths and principal symbols found in this workspace.
  Trace UI input/import -> BladeSpec -> resolver/profile preparation -> adapter/
  managed OpenVSP -> OCP -> final validation -> job state/artifacts/viewer.
  Separate preview from authoritative final STEP, generation from validation,
  and backend-neutral engineering code from web/CLI entrypoints.
- A reading order of about five stops, each tied to one concrete file/function
  and one question. Explain why the maintained fixed-plane patch exists and where
  it is maintained, without retelling every diagnostic trial.
- Update the quick start and current Arabic guide with actual paths and tested
  launcher commands. Preserve the complete simple CSV and X-57 input files.

Do not invent an architecture or claim desktop portability was tested. Keep the
existing core independent of the web and avoid a desktop migration in this task.
The detailed teaching walkthrough is next, not another implementation package now.

## 8. Evidence, checkpoint and stop

Put this task's prompt/report/matrix under docs/sprints/L1A-01/. Its report includes
before/after trees, old-to-new path map, all archive hash checks, justified code
edits, affected tests and exact final commands/counts/durations/retries.

Provide a small handoff with:
- Current README, sprint index, scope/status and Arabic code map.
- A machine-readable migration map and reversible rollback instructions.
- Exact tested source snapshot identity (HEAD plus dirty source/diff hashes when
  uncommitted), runtime fingerprint, manifest and preserved baseline inputs.
- The fresh X-57 job's validation, engine manifest, input, comparison and screenshot.
- Fresh STEP at a durable path with size/hash, supplied separately if large.
- A verified local source checkpoint or source-only archive without secrets,
  generated dependencies or recursive evidence backups; describe what it omits.

No automatic commit/tag is authorized. Supply a suggested commit split and name
for later approval; do not call an uncommitted tree a published release. A small
report prose update does not require rerunning CAD if executed source is unchanged.

Success: L1A_BLADE_BASELINE_VERIFIED_AFTER_CLEANUP.
Otherwise: BLOCKED/INCOMPLETE with the exact cleanup/regression issue.

Success means organized and reproducible single-blade baseline within the tested
scope, not all of Level 1 closed. Keep these explicit:
- Full-propeller implementation and existing automated evidence preserved;
  user's assembly acceptance and its next development phase are deferred.
- NASA external surface fidelity UNVERIFIED.
- 900-second trial profile qualified; default-300-second X-57 not qualified.
- No new aerodynamic/structural/manufacturing or arbitrary-geometry guarantees.

Execute, then STOP. Do not start propeller development, a performance sprint,
new features or further geometric experiments automatically.

The final response must say: what moved, what executable behavior changed (ideally
none), whether the same blade passed again, where all sprints now live, how to
launch, and which source files we should read together next.
