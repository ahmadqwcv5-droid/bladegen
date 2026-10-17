# L1A-01 repository migration

## Preservation and execution

Before any move, the working candidate was on `patch/fp02-c1-thickness-te-qualification` at HEAD `39ffb7229c834d9c1e19eab03b529a83f1e366a3`, with 433 Git status entries and an empty index. A local recoverable source-only checkpoint was made outside this repository at `../L1A_01_local_checkpoint_6O4cInS9/`. Its `source_only_checkpoint.tar.xz` SHA-256 is `074efda3f28a70a7b952c1396d1e153b85e190470237f0c4871ed2b637f40b82`; the archive integrity check passed. The checkpoint includes source/config/docs/fixtures (including dirty and untracked source), original status and index records, tracked binary patch, 408 per-file hashes and 472 archive entries with modes. It excludes Git internals, credentials, installed runtimes/dependencies, old CAD outputs, and integrity-bound evidence trees. Those originals remain in place. A non-destructive branch `maintenance/l1a-01-blade-baseline` was created from the same HEAD; nothing was stashed, reset, committed, tagged, merged or pushed.

The [frozen migration plan](MIGRATION_PLAN.tsv) lists 68 source/destination pairs with classification and reason. Every source existed and destination was absent before the move. All 68 moves completed without overwrite; [migration_map.json](migration_map.json) records the before/after SHA-256, bytes, mode and symlink target for each. All moved bytes and modes matched (795,903 total bytes). The original handoff ZIP passed integrity checks; all five supplied `SHA256SUMS.txt` entries passed. The exact user X-57 spec, validation and manifest were copied without alteration to `fixtures/reference_user_x57/`; the original ZIP and extracted incoming copy remain available.

| Before | After | Purpose |
| --- | --- | --- |
| Loose `sprint*.md`, `FP*.md`, X-57 prompt files and `docs/*REPORT.md` / matrices | `docs/sprints/<original-id>/` | One indexed historical chronology, original bytes retained |
| Current `docs/` user guides | `docs/user/` | Active usage guidance |
| Current `docs/` engineering guides | `docs/developer/` | Active architecture and runtime guidance |
| Root X-57 fixture ZIP | `fixtures/x57_manual_reference/` | Source/reference input beside retained extracted fixtures |
| Root L1A handoff ZIP | `docs/sprints/L1A-01/` | Original task bundle preserved intact |

`backend/`, `frontend/`, `scripts/`, `examples/`, `qualification/`, `vendor/openvsp_fixed_plane/`, project configs and lockfiles remain at their active locations. `docs/evidence/`, `docs/screenshots/`, `docs/sprint02_validation/`, the original `output/runs/` jobs, installed `.tooling/`, `.venv`, `node_modules`, and the external `00_research_archive/` were not moved or rewritten. Some older optional diagnostics remain in `scripts/` because their run-relative paths and replay environment are historical; they are not a production import dependency and were not silently modernized. Historical report absolute paths and embedded links remain historical facts; the index and machine-readable map are the navigation layer.

Historical report links were checked before/after moves: 91 of 97 relative links no longer resolved from the new folder context. The separate [compatibility link plan](COMPATIBILITY_LINK_PLAN.tsv) was preflighted for absent destinations and existing targets, then 24 exact symlinks were created and verified. Original report bytes were not edited; all **97/97** original relative links now resolve locally. These links are pointers, not independent report copies. For rollback, remove only a pointer whose `readlink` target still equals the plan, then reverse the corresponding move; refuse a changed pointer or target conflict.

Generated L1A evidence and the recoverable extracted handoff are locally retained but ignored by Git. This does not erase them, untrack existing historical screenshots, or rewrite repository history.

## Rollback and behavior boundary

To reverse archival document/ZIP moves, first inspect `git status` and the [map](migration_map.json), verify each destination still has `sha256_after` and each old source is absent, then rename each destination back to its recorded source in reverse order. Refuse any conflict or changed archival hash. The map's hashes describe the move moment: current user guides were deliberately edited afterward, so save those edited versions first and move them back separately (or restore their original bytes from the pre-cleanup checkpoint if those edits are deliberately discarded). Never apply the archival hash gate to silently erase later guide edits.

Restore current README links separately if rolling back navigation. Do not run a blanket reset/clean: the tree had substantial pre-existing uncommitted work. The source-only archive and original status/patch files are recovery aids, not commands to apply blindly.

No core numerical, geometry, schema, runtime patch, tolerance or production UI behavior was changed in this migration. New browser-test routing sends L1A screenshots to new evidence directories while retaining default legacy paths for ordinary runs. A new exact-X-57 browser replay and a test-config option to use the externally launched trial services are qualification harness changes only.
