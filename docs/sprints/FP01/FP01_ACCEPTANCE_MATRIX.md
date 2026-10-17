# FP-01 acceptance matrix

Status: **FP01_INTEGRATION_PASS**

This matrix records the measured phase-one managed fixed-plane runtime integration at application HEAD `1cdb564a2eb92b0171acbab705b41ca63b57416c` on branch `integration/fp01-managed-fixed-plane-runtime`. The worktree remains intentionally dirty and uncommitted.

| Gate | Result | Evidence |
|---|---|---|
| Pinned modified OpenVSP distribution | PASS | OpenVSP 3.54.0 commit `db6c6fe8f4eca27d7517f4ae0b2078abdd3fd927`; source archive SHA-256 `0b72cf30b68ae5b4845fd61d6cfebfa2033c9ff9188c95e335b86b6cc543c2af`; maintained patch SHA-256 `0dd6f87b867ccaeb6518f8f01f7093e4e1a05f02d0c5a268c66cc1d157ed71d3`. |
| Compile-time construction policy | PASS | Feature ON applies identity at the proven automatic `m_ZRotate` application and continues the calculation; feature OFF retains the upstream operation. No profile, loft, cap, tolerance, or export algorithm was changed. |
| Real Python/native identity | PASS | Compiled SWIG queries return build `openvsp-3.54.0-bladegen-fixed-plane.1`, contract `bladegen.fixed-radial-sections.v1`, and capability `fixed_radial_sections_v1`. Native `_vsp.so` SHA-256 is `e9c91cd48148ddf7017631770aed019f3fda44c25bba4fa556f58d243472baea`. |
| Project-local staged setup | PASS | Clean staged build/import/geometry smoke completed; no system runtime was replaced. A second unchanged setup reused the verified install in 1.96 s. Failed pre-activation attempts and logs were preserved and never activated. |
| Fail-closed runtime selection | PASS | Managed default and explicit absolute `OPENVSP_ROOT` share one resolver; missing, stock, wrong identity/capability, wrong ABI, tampered, mixed, stale, empty, and relative selections are rejected without fallback. |
| CLI/API integration | PASS | `bladegen doctor`, `runtime-info --json`, `GET /api/runtime`, pre-queue checks, worker fingerprint recheck, and allow-listed per-run `engine_manifest.json` are implemented. |
| Native semantic integration suite | PASS | `13 passed, 163 deselected` in 589.93 s (wall 591.73 s), including zero/nonzero rake, inherited diagnostic flag invariance, real CAD, and propeller paths. |
| X-57 fresh production CLI build | PASS | Normal production Python pipeline, external 900 s bound, unchanged submitted input, 365.16 s wall; 41 planned/completed/passed, 0 failed. One provenance-only retry was made; results are not combined. |
| X-57 final STEP topology | PASS | 1 solid, 1 shell, 6 faces, 0 free edges, closed shell, valid BRep; volume 46373.243509611435 mm³; surface area 22170.68049735742 mm². |
| X-57 comparison to accepted AB-02 B | PASS | 10,086 surface samples; RMS/P95/max, bounding-box, root/tip, and surface-area deltas all 0.0. Candidate STEP SHA-256 `e55f3e4ff6c1b8666a0ae8f1d580af8a413e9d484739a7378493f236d5c968b8`; byte identity was not required. |
| Small real blade through API | PASS | Job `0c23cc7aa9bb44bfa4adf0b1672bcd51`, succeeded in 47.6 s; valid closed one-solid STEP and matching completed engine provenance. |
| Existing propeller through API | PASS | Job `3946de3d51df40c48dd17919c713acfd`, succeeded in 66.4 s; valid closed one-solid STEP and matching completed engine provenance. |
| Runtime-unavailable API rejection | PASS | Blade and propeller component tests assert HTTP 503 before job allocation; the worker independently rejects a queued fingerprint mismatch. |
| Non-CAD backend suite | PASS | `163 passed, 13 deselected` in 1.05 s. |
| Frontend unit suite | PASS | 26 files, 160 tests passed in 17.02 s. |
| Frontend production build | PASS | Vite build completed in 333 ms; existing large-chunk advisory remains non-fatal. |
| FP01 Python Ruff scope | PASS | All FP01 Python implementation and tests passed Ruff. Repository-wide `backend scripts` found 29 unrelated existing findings in diagnostic/benchmark scripts; no assertions or unrelated investigation sources were weakened. |
| Linux/Python target | PASS, scoped | Qualified on Linux x86_64, glibc 2.39, Python 3.12.3, GCC 13.3.0, CMake 4.3.4, SWIG 4.2.0, OCP 7.9.3.1.1, NumPy 2.5.3, SciPy 1.18.1. |
| Broader product-wide CAD regression | PENDING | Deferred to the next qualification phase as required. |
| Default 300 s full X-57 UI acceptance | PENDING | X-57 was qualified through the normal CLI under an explicit 900 s external bound; this is not a performance claim. |
| External NASA surface fidelity | UNVERIFIED | Internal product and accepted AB-02 comparisons do not establish external NASA fidelity. |
| Profile-preparation refinement | UNCHANGED | The prior small profile-preparation discrepancy and unmet refinement target remain documented. |
| Original failed job | UNCHANGED | Job `a93b281c29b640afaa6bad698d64a61b` and all prior diagnostic evidence remain immutable. |

Large generated binaries remain under ignored `.tooling/` paths. Code, locks, patch, setup, documentation, and tests are repository deliverables; no merge, commit, external publication, or system-wide activation was performed.
