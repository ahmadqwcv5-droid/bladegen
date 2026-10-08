# Migration report

The pre-migration root contained 24 historical entries and 284 files outside the
active 1.7 GB `.venv`. It was not a Git worktree. The only symlinks were internal
virtual-environment Python/library links; the workspace is a writable NTFS/FUSE
mount. `.venv`, `.vscode`, and the active `sprint01.md` were retained at root.

All prompts, Tests 01–05, Spikes 00A–01D, CAD outputs, reports, caches, benchmark
notes, and the migration tool were moved without overwriting into
`00_research_archive`, preserving names and relative structure. Every file was
hashed before moving and re-hashed afterward; all 284 manifest rows are
`verified`. See `00_research_archive/ARCHIVE_MANIFEST.csv`.

The authoritative engine selected was `spike_01_bladegen/bladegen`, which already
contained the 01C canonical resolver and 01D multi-airfoil/finite-TE changes. A
clean source-only copy was promoted; caches, `.orig` files, and generated output
were not copied. The finite-TE multi-airfoil example was independently promoted.
Product code and scripts contain no archive imports. Historical scripts may
require their old relative locations and are preserved for evidence, not runtime.
