# FP-02 frozen qualification plan

Status: frozen before qualification CAD execution on 2026-10-15.

Starting HEAD is `39ffb7229c834d9c1e19eab03b529a83f1e366a3` on
`qualification/fp02-level1-user-trial`. FP-02 source, tests, case definitions,
and documentation are intentionally uncommitted until the user reviews them.
The machine-readable authority is
[`qualification/fp02/case_manifest.json`](../qualification/fp02/case_manifest.json).

## Fixed execution contract

- Runtime build: `openvsp-3.54.0-bladegen-fixed-plane.1`.
- Construction contract: `bladegen.fixed-radial-sections.v1`.
- Trial worker limit: 900 seconds per design; the ordinary default remains 300.
- Product paths: the normal BladeSpec/PropellerSpec pipeline, managed OpenVSP,
  OCP solidification/assembly, unchanged section plan, unchanged measurement
  policy, and STEP re-import.
- Expected primary result: `PASS` for each frozen case. A failure is retained and
  reported; inputs and tolerances are not tuned after execution.
- External NASA surface fidelity is outside this qualification and remains
  unverified.

Reverse rotation is already present in the model, UI, adapter, schema, and
documented geometry conventions. It is therefore frozen for Q04 only. Q01–Q03,
Q05, and all assembly cases use Normal rotation.

## Frozen primary matrix

| ID | Definition | Frozen coverage | Planned sections |
|---|---|---|---:|
| Q01 | `qualification/fp02/cases/Q01.json` | Three NACA 0012 stations, zero rake/skew, zero physical TE, Linear; from-scratch browser case | 5 |
| Q02 | `qualification/fp02/cases/Q02.json` | Five mixed/cambered NACA stations, positive rake, finite TE, PCHIP | 11 |
| Q03 | `qualification/fp02/cases/Q03.json` | Q02-derived negative rake slope and signed skew; other engineering inputs fixed | 11 |
| Q04 | `qualification/fp02/cases/Q04.json` | Eight nonuniform imported-coordinate stations, independent grids, explicit thickness, Reverse | 26 |
| Q05 | `qualification/fp02/cases/Q05.json` | Unchanged retained X-57 definition: two imported profiles and 40 controls for Chord/Twist/Rake/Skew | 41 |
| Q06 | `qualification/fp02/cases/Q06.json` | Two blades; supported 90 × 45 mm hub and 12 mm bore | 11 |
| Q07 | `qualification/fp02/cases/Q07.json` | Three blades; same supported assembly family | 11 |
| Q08 | `qualification/fp02/cases/Q08.json` | Four blades; same supported assembly family | 11 |

Q04 reuses retained coordinate arrays as imported-coordinate test data in a
synthetic eight-station design. It is not a new NASA reference or an external
fidelity claim. Q05 is byte-for-byte the retained submitted definition at SHA-256
`775e7bd571c815ea88aa8086208f50eb4663375d5953414178f7e753d5425d10`.

The Q01 edit/rebuild perturbation is fixed at `r/R = 0.625`, changing Twist from
18° to 21° and nothing else. Its file is
`qualification/fp02/cases/Q01_twist_edit.json`. It is a workflow repetition, not
a ninth primary family.

## User workflows

- U1 uses visible controls to create Q01, generate, save, reopen in a new browser
  context, apply the frozen Twist edit, verify stale/previous CAD state, explicitly
  regenerate under a new job ID, and build Q06 through the UI.
- U2 uses the immutable files copied under
  `qualification/fp02/trial_inputs/x57/` to set up two stations, upload/apply the
  profile, import all 40 distribution rows, export/compare the candidate, generate
  Q05, and download that job's project, STEP, validation, and engine manifest.

The original fixture checksum file is copied unchanged and must pass
`sha256sum --check SHA256SUMS.txt` from that directory. No prepared BladeSpec may
be injected into browser state for U1 or U2.

## Acceptance policy

The existing production booleans and numeric policy remain authoritative. Every
planned station must be present and pass chord, twist, reference-axis, contour
RMS/P95/maximum, trailing-edge, wire-count, wire-validity, and wire-closure gates.
The final and re-imported shapes must be one closed, BRep-valid solid and shell
with zero non-degenerate free edges. Propellers additionally require the existing
placement count, positive hub overlaps, pairwise outside-hub collision checks,
fusion steps, continuous coaxial bore, final topology, and STEP round-trip gates.

The case files, their hashes, intended coverage, expected status, and precomputed
station-plan counts are recorded in the machine manifest before any primary CAD
case is executed.
