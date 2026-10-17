# L1A-01 repeatability assets

- [`repeatability_contract.json`](repeatability_contract.json) froze identity, topology, station and direct-STEP limits before the post-cleanup build.
- [`compare_same_blade.py`](compare_same_blade.py) compares a fresh completed UI job to user job `3970dc6383f1425b9726d5a9a00f4202` using the existing OCP direct comparator. It does not generate or repair CAD.
- `evidence/<run-id>/` holds local browser logs, traces, downloads and the independently labeled same-blade comparison; it is Git-ignored because it includes a large generated STEP and is not a source bundle.
- `incoming/` is the locally extracted, checksum-verified original handoff. It is Git-ignored and recoverable from the unchanged ZIP in `docs/sprints/L1A-01/`.

For the user-facing result and tested commands, read [`L1A_01_REPORT.md`](../../docs/sprints/L1A-01/L1A_01_REPORT.md). Keep the original job and historical evidence unchanged.
