# FP02-C1 Level 1 trial inputs

Run the qualified profile from the repository root:

```bash
./scripts/start_level1_trial.sh
```

The launcher uses the authorized 900-second per-design worker limit. The ordinary
application default remains 300 seconds and is not qualified for the X-57 case.

Suggested trial order:

1. Open `simple/FP02_C1_Q01_simple_blade.json`, generate, save/open, then open
   `simple/FP02_C1_Q01_twist_edit.json` and generate again.
2. Open and generate `simple/FP02_C1_Q02_pchip_finite_te.json`.
3. Open and generate `simple/FP02_C1_Q04_R1_reverse_imported.json`.
4. Open `simple/FP02_C1_Q06_two_blade_propeller.json` and generate the propeller.
5. Follow `x57/README_AR.md` for the real X-57 CSV import workflow.

`x57/README_AR.md` is retained byte-for-byte from the source fixture so its
published `SHA256SUMS.txt` remains valid. Its historical “not run yet” package
status describes the fixture at delivery time; the current qualified result is
recorded in `docs/LEVEL1_USER_TRIAL_AR.md` and `docs/FP02_C1_REPORT.md`.

Q04.R1 is a versioned qualification fixture. The original Q04 intentionally
remains invalid and is not a user-trial positive input.

The X-57 workflow has passed internal input/CAD validation. External NASA surface
fidelity remains **UNVERIFIED** because no official comparison geometry was
available in the supplied fixture bundle.
