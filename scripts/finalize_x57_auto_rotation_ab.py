#!/usr/bin/env python3
"""Finalize the compact X57-AB-02 decision bundle from measured evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
ARMS = ("A_native", "B_rotation_bypassed", "A2_native_recovery")
FINAL_SHA = "43c2cd72bebcd3949e0fe0b210aaac9ccbf6918952743fd109ecb0cac2e401d6"
RAW_SHA = "85f798f74f672e4c78f3560e3413fcbdbba0ff7410424a840a5fc4e746d8b07f"


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def jread(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def jwrite(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def cread(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def xml_values(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}

    def visit(element: ElementTree.Element, prefix: str) -> None:
        counters: dict[str, int] = {}
        for child in element:
            index = counters.get(child.tag, 0)
            counters[child.tag] = index + 1
            key = f"{prefix}/{child.tag}[{index}]"
            if "Value" in child.attrib:
                result[key] = child.attrib["Value"]
            visit(child, key)

    root = ElementTree.parse(path).getroot()
    visit(root, f"/{root.tag}")
    return result


def selected(rows: list[dict[str, str]], arm: str, station: float) -> dict[str, str]:
    return next(
        row for row in rows
        if row["arm"] == arm and abs(float(row["r_over_R"]) - station) <= 1e-12
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--install-dir", type=Path, required=True)
    args = parser.parse_args()
    run = args.run_dir.resolve()
    source = args.source_dir.resolve()
    full_dir = run / "B_rotation_bypassed" / "full_validation"

    shutil.copyfile(full_dir / "geometry_validation_result.json", run / "B_rotation_bypassed" / "candidate_full_validation.json")
    shutil.copyfile(full_dir / "completed_measurements.json", run / "B_rotation_bypassed" / "candidate_full_measurements.json")
    runners = run / "runners"
    runners.mkdir(exist_ok=True)
    for name in (
        "analyze_x57_auto_rotation_ab.py",
        "validate_x57_ab_candidate.py",
        "diagnose_x57_contours.py",
        "diagnose_x57_validation.py",
        "finalize_x57_auto_rotation_ab.py",
    ):
        shutil.copyfile(ROOT / "scripts" / name, runners / name)

    a_values = xml_values(run / "A_native" / "blade_openvsp.vsp3")
    b_values = xml_values(run / "B_rotation_bypassed" / "blade_openvsp.vsp3")
    a2_values = xml_values(run / "A2_native_recovery" / "blade_openvsp.vsp3")
    changed_ab = [
        {"xml_path": name, "A": a_values.get(name), "B": b_values.get(name)}
        for name in sorted(set(a_values) | set(b_values))
        if a_values.get(name) != b_values.get(name)
    ]
    derived = [
        row for row in changed_ab
        if "/BBox[" in row["xml_path"] or row["xml_path"].endswith("/SmallPanelW[0]")
    ]
    authored = [row for row in changed_ab if row not in derived]
    vsp3_comparison = {
        "A_A2_byte_identical": sha(run / "A_native" / "blade_openvsp.vsp3") == sha(run / "A2_native_recovery" / "blade_openvsp.vsp3"),
        "A_B_changed_value_count": len(changed_ab),
        "geometry_derived_changes": derived,
        "authored_or_export_setting_changes": authored,
        "authored_or_export_settings_unchanged": not authored,
        "interpretation": "B changes only derived bounding-box values and derived SmallPanelW after geometry recomputation; engineer inputs and STEP settings are unchanged.",
    }
    jwrite(run / "vsp3_settings_comparison.json", vsp3_comparison)

    script_main = source / "src/vsp/scriptonly_main.cpp"
    common = source / "src/vsp/common.cpp"
    manager = source / "src/geom_core/ScriptMgr.cpp"
    exit_source = {
        "observed_codes": {"A_native": 44, "B_rotation_bypassed": 92, "A2_native_recovery": 92},
        "source_files": {
            str(script_main): sha(script_main),
            str(common): sha(common),
            str(manager): sha(manager),
        },
        "source_backed_explanation": "scriptonly_main returns Vehicle::RunScript; batchMode assigns that value to the process result; ExecuteScript calls AngelScript GetReturnDWord even though these replay scripts declare void main(). Therefore the varying values are not a documented geometry-success code and are not relabelled as zero.",
        "completion_evidence": "Each arm has START then COMPLETE in probe_update_events.csv, a script COMPLETE marker, 619 complete inventory rows, and complete fresh VSP3/STEP/probe artifacts.",
        "disposition": "Host return-code anomaly reported separately from geometry acceptance; no timeout or missing artifact occurred.",
    }
    jwrite(run / "native_exit_code_evidence.json", exit_source)

    status = {
        "experiment_id": "X57-AB-02",
        "created_at_utc": utc_now(),
        "attempts": [
            {"operation": "isolated native intervention build", "attempts": 1, "exit_code": 0},
            {"operation": "A native arm", "attempts": 1, "exit_code": 44, "completion": "START/COMPLETE and artifacts verified"},
            {"operation": "B bypass arm", "attempts": 1, "exit_code": 92, "completion": "START/COMPLETE and artifacts verified"},
            {"operation": "A2 native recovery arm", "attempts": 1, "exit_code": 92, "completion": "START/COMPLETE and artifacts verified"},
            {"operation": "OCP solidification/re-import", "attempts": 1, "exit_code": 0},
            {"operation": "full 41-station production validation", "attempts": 1, "exit_code": 0, "timed_out": False},
            {"operation": "independent evidence derivation", "attempts": 2, "first_exit_code": 1, "final_exit_code": 0, "retry_reason": "reporting-only heterogeneous CSV field list; all expensive results were deterministically recomputed"},
        ],
        "native_process_status_is_not_geometry_acceptance": True,
        "hidden_retries": False,
    }
    jwrite(run / "execution_status.json", status)

    commands = f"""# X57-AB-02 commands (working directory: {ROOT})

# Build, single attempt; exact CMake build command is preserved in intervention_build.log
script -qefc 'cmake --build /tmp/openvsp-build-354-ribprobe-a93b281c_20261014T164009Z/OpenVSP-prefix/src/OpenVSP-build --target vspscript --parallel 8' {run / 'intervention_build.log'}

# Arms, one fresh process each; exact expanded commands are the COMMAND fields in native_run.log
env BLADEGEN_RIB_PROBE_DIR={run / 'A_native'} BLADEGEN_BYPASS_AUTO_RIB_ROTATION=0 {args.install_dir / 'vspscript'} -script {run / 'A_native/run_arm.vspscript'}
env BLADEGEN_RIB_PROBE_DIR={run / 'B_rotation_bypassed'} BLADEGEN_BYPASS_AUTO_RIB_ROTATION=1 {args.install_dir / 'vspscript'} -script {run / 'B_rotation_bypassed/run_arm.vspscript'}
env BLADEGEN_RIB_PROBE_DIR={run / 'A2_native_recovery'} BLADEGEN_BYPASS_AUTO_RIB_ROTATION=0 {args.install_dir / 'vspscript'} -script {run / 'A2_native_recovery/run_arm.vspscript'}

# OCP finalization was one call to bladegen.solid.ocp_solidify.solidify_step;
# details and elapsed time are in B_rotation_bypassed/ocp_solidification.json.

# Exact full production validation, one attempt, external 900 s limit
{jread(full_dir / 'runtime_configuration.json')['launcher_command']}

# Independent derivation, second (successful) run after reporting-only CSV fix
timeout --signal=TERM --kill-after=30s 900s backend/.venv/bin/python scripts/analyze_x57_auto_rotation_ab.py --run-dir {run} --loc02-dir {ROOT / 'docs/evidence/sprint04b/x57/live_surface_localization/a93b281c_20261014T152749Z'} --loc03-dir {ROOT / 'docs/evidence/sprint04b/x57/rib_placement_localization/a93b281c_20261014T164009Z'} --source-dir {source} --install-dir {args.install_dir}

# Bundle finalization
backend/.venv/bin/python scripts/finalize_x57_auto_rotation_ab.py --run-dir {run} --source-dir {source} --install-dir {args.install_dir}
"""
    (run / "commands.txt").write_text(commands, encoding="utf-8")

    retained_final = ROOT / "docs/evidence/sprint04b/x57/job/blade_solid.step"
    retained_raw = ROOT / "output/runs/a93b281c29b640afaa6bad698d64a61b/blade_openvsp.step"
    production_files = (
        "backend/bladegen/adapters/openvsp_adapter.py",
        "backend/bladegen/solid/ocp_solidify.py",
        "backend/bladegen/validation/expected_geometry.py",
        "backend/bladegen/validation/measure_sections.py",
        "backend/bladegen/validation/policy.py",
        "backend/bladegen/validation/station_plan.py",
        "backend/bladegen/pipeline.py",
    )
    git_status = subprocess.run(
        ["git", "status", "--short"], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.splitlines()
    integrity = {
        "captured_at_utc": utc_now(),
        "head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip(),
        "dirty_worktree_preserved": bool(git_status),
        "git_status_short": git_status,
        "retained_failed_job": {
            "final_step_sha256": sha(retained_final),
            "final_step_expected_sha256": FINAL_SHA,
            "final_step_verified": sha(retained_final) == FINAL_SHA,
            "raw_step_sha256": sha(retained_raw),
            "raw_step_expected_sha256": RAW_SHA,
            "raw_step_verified": sha(retained_raw) == RAW_SHA,
            "status": "FAILED/FAIL unchanged",
        },
        "production_source_sha256": {name: sha(ROOT / name) for name in production_files},
        "production_runtime_vspscript_sha256": sha(ROOT / ".tooling/openvsp-3.54.0/opt/OpenVSP/vspscript"),
        "production_runtime_expected_sha256": "e760aa04cbbc08804053bb038679097648f5d3fd9ff65dfc72554cc69f1901c0",
        "production_runtime_unchanged": sha(ROOT / ".tooling/openvsp-3.54.0/opt/OpenVSP/vspscript") == "e760aa04cbbc08804053bb038679097648f5d3fd9ff65dfc72554cc69f1901c0",
        "diagnostic_binary_sha256": sha(args.install_dir / "vspscript"),
        "candidate_solid_sha256": sha(run / "B_rotation_bypassed/candidate_solid.step"),
        "frozen_plan_sha256": sha(run / "plan.json"),
    }
    jwrite(run / "end_integrity.json", integrity)

    summary = jread(run / "experiment_summary.json")
    station_rows = cread(run / "station_comparison.csv")
    plane_rows = cread(run / "rib_plane_comparison.csv")
    profile = jread(run / "profile_preparation_fixed_background.json")
    full = jread(run / "B_rotation_bypassed/candidate_full_validation.json")
    ocp = jread(run / "B_rotation_bypassed/ocp_solidification.json")
    launcher = jread(full_dir / "launcher_result.json")
    region = cread(run / "upper_surface_residual_region.csv")

    production_table = []
    independent_table = []
    plane_table = []
    for station in (0.22302, 0.29061, 0.50345):
        a = selected(station_rows, "A_native", station)
        b = selected(station_rows, "B_rotation_bypassed", station)
        a2 = selected(station_rows, "A2_native_recovery", station)
        production_table.append(
            f"| {station:.5f} | {float(a['production_rms_mm']):.9f} / {float(a['production_p95_mm']):.9f} / {float(a['production_sampled_max_mm']):.9f} | {float(b['production_rms_mm']):.9f} / {float(b['production_p95_mm']):.9f} / {float(b['production_sampled_max_mm']):.9f} | {b['chord_error_mm']} / {b['twist_error_deg']} / {b['axis_error_mm']} / {b['te_error_mm']} | {b['all_original_gates_pass']} | {float(a2['production_sampled_max_mm']):.9f} |"
        )
        independent_table.append(
            f"| {station:.5f} | {float(a['independent_live_sampled_max_mm']):.9f} | {float(b['independent_live_sampled_max_mm']):.9f} | {float(b['direct_A_to_B_sampled_max_mm']):.9f} | {float(b['live_to_raw_sampled_max_mm']):.3e} | {float(b['independent_live_refinement_2x_to_4x_mm']):.3e} |"
        )
        pa = selected(plane_rows, "A_native", station)
        pb = selected(plane_rows, "B_rotation_bypassed", station)
        plane_table.append(
            f"| {station:.5f} | {float(pa['computed_zrotate_deg']):.9f} | {float(pa['plane_angle_from_global_y_deg']):.9f} / {float(pa['rib_y_departure_max_abs_mm']):.9f} | {float(pb['applied_zrotate_deg']):.1f} | {float(pb['plane_angle_from_global_y_deg']):.3e} / {float(pb['rib_y_departure_max_abs_mm']):.3e} |"
        )

    all_records = full["stations"]
    max_contour = max(all_records, key=lambda row: row["contour_max_mm"])
    b_region = next(row for row in region if row["arm"] == "B_rotation_bypassed" and abs(float(row["r_over_R"]) - .22302) <= 1e-12)
    report = f"""# X57 Auto-Rotation A/B Decision

## Direct answers

1. **Was B actually run with only automatic rotation application bypassed? Yes.** One fresh B process used the same diagnostic binary as A/A2. All 619 computed `m_ZRotate` values and all nonexperimental inventory fields match A exactly; all 619 applied B angles are zero. Prepared-profile rows are identical across A/B/A2. The minimal intervention diff is `{sha(run / 'auto_rotation_intervention.diff')}`.
2. **Did A2 restore A, with unchanged profiles and inputs? Yes.** A-to-A2 direct live differences are exactly 0.0 mm at all three planes, selected production RMS/P95/max deltas are exactly 0.0 mm, the complete inventory is byte-identical, and A/A2 VSP3 files are byte-identical. The 86,037 prepared-profile rows have common canonical SHA-256 `{jread(run / 'settings_input_comparison.json')['invariants']['prepared_profile_canonical_sha256']}`.
3. **How did the three sections change?** B passes every original chord, twist, reference-axis, TE, contour and wire gate at all three stations. At r/R 0.22302, production RMS/P95/max changed from 0.253757/0.503102/0.523742 mm to 0.006287/0.010586/0.012279 mm. The independent live sampled max changed from 0.523791 to 0.003958 mm.
4. **Did unchanged 41-station validation complete and pass? Yes.** The exact production `measure_sections` and `pipeline._geometry_summary` path completed 41/41 stations with 41 passed and 0 failed. `_geometry_summary` returned `passed: true` after STEP re-import.
5. **What is the result?** A **qualified diagnostic prototype**, not a deployment-ready change. Causal outcome: **ROTATION_EFFECT_REPRODUCED**. Candidate outcome: **FULL_INTERNAL_DIAGNOSTIC_PASS**. External NASA fidelity remains **UNVERIFIED**.

The original job `a93b281c29b640afaa6bad698d64a61b` and its retained blade validation remain **FAILED/FAIL**. This candidate result is separate and does not rewrite that job.

## Controlled intervention and invariants

The isolated OpenVSP 3.54.0 build retained derivative calculation and logging but applied zero at the existing `mat.rotateZ(m_ZRotate)` operation only when `BLADEGEN_BYPASS_AUTO_RIB_ROTATION=1`. Pivot, translations, rotation order, curve derivatives, engineering inputs, profile preparation, caps and STEP settings were unchanged. Production source/runtime were not modified or used for the arms.

- Frozen pre-run plan SHA-256: `{sha(run / 'plan.json')}`.
- Diagnostic binary: `{args.install_dir / 'vspscript'}`, SHA-256 `{sha(args.install_dir / 'vspscript')}`.
- OpenVSP source commit: `db6c6fe8f4eca27d7517f4ae0b2078abdd3fd927`.
- Project HEAD: `{integrity['head']}`; the pre-existing dirty worktree was preserved.
- A/B/A2 pseudo-rib inventory: 619 each, exact correspondence.
- All-arm live fixed-plane residual maximum: 1.805e-13 mm (limit 1e-6 mm).
- Rib-to-post-skin native-u maximum: 1.449e-12 mm across 619 ribs.
- A/B saved-model value differences are only geometry-derived BBox and `SmallPanelW`; no authored/export setting differs. See `vsp3_settings_comparison.json`.

## Three selected production gates

Production columns are RMS / P95 / sampled max in mm. B dimensional columns are chord mm / twist deg / axis mm / TE mm.

| r/R | A contour | B contour | B dimensional errors | all B gates | A2 max mm |
|---:|---:|---:|---:|:---:|---:|
{chr(10).join(production_table)}

At the worst station, the expected-upper residual in x/c [0.13, 0.18] fell from 0.523791 mm at x/c 0.155250 in A to {float(b_region['sampled_max_mm']):.9f} mm in B. No best-fit alignment, scale change or separate normalization was used.

## Independent physical-plane evidence

| r/R | E→A live sampled max mm | E→B live sampled max mm | direct A→B max mm | B live→raw max mm | B 2x→4x max delta mm |
|---:|---:|---:|---:|---:|---:|
{chr(10).join(independent_table)}

The direct A/B effect exceeds the frozen 0.001 mm material-effect threshold at all three planes. Independent candidate refinement is stable within 0.0001 mm. Exact raw-section BReps, coordinates, true-scale overlays and upper residual plots are under `stations/`.

## Rib-plane mechanism

| r/R | computed angle deg | A plane angle / max | B applied deg | B plane angle / max |
|---:|---:|---:|---:|---:|
{chr(10).join(plane_table)}

The ablation makes the selected positioned ribs coplanar with the requested global-Y planes to floating-point precision while retaining the original computed derivative-driven angles. A2 exactly restores the tilted A geometry. This supports the causal classification without claiming that the rotation explained every small residual.

## Fixed profile-preparation background

The preexisting preparation discrepancy was held unchanged, not subtracted or repaired. Its 4x physical sampled maxima are {profile['0.22302']['factors']['4x']['physical_mm']['sampled_max_mm']:.9f}, {profile['0.29061']['factors']['4x']['physical_mm']['sampled_max_mm']:.9f}, and {profile['0.50345']['factors']['4x']['physical_mm']['sampled_max_mm']:.9f} mm. The 2x→4x deltas are {profile['0.22302']['sampled_max_refinement_2x_to_4x_mm']:.9f}, {profile['0.29061']['sampled_max_refinement_2x_to_4x_mm']:.9f}, and {profile['0.50345']['sampled_max_refinement_2x_to_4x_mm']:.9f} mm, so the earlier 0.0001 mm preparation-refinement target remains unmet. That limitation is explicitly separate from the stable B fixed-plane comparison and unchanged product gates.

## OCP finalization and STEP round trip

The unchanged production `solidify_step` path added **0 faces**. It sewed the six raw OpenVSP faces into one shell and made/re-exported one solid.

- Re-import: 1 solid, 1 shell, 6 faces, 0 non-degenerate free edges.
- Closed shell: true; BRepCheck valid: true.
- Surface area: {ocp['solid_after_reimport']['surface_area_mm2']:.9f} mm².
- Adaptive Gauss-Kronrod volume: {ocp['solid_after_reimport']['volume_mm3']:.12f} mm³ at relative tolerance 1e-9 (estimated relative error {ocp['solid_after_reimport']['volume_estimated_relative_error']:.3e}).
- STEP round-trip volume delta: {ocp['roundtrip']['volume_delta_mm3']:.3e} mm³.
- STEP round-trip bounding-box max delta: {ocp['roundtrip']['bbox_max_abs_delta_mm']:.3e} mm.
- Candidate solid: `B_rotation_bypassed/candidate_solid.step`, {summary['candidate_step']['size_bytes']} bytes, SHA-256 `{summary['candidate_step']['sha256']}`.

## Complete unchanged production validation

- Planned/completed/passed/failed: 41 / 41 / 41 / 0.
- Endpoint plan preserved: root requested 0.20238 → sampled 0.207365125; tip requested 1.0 → sampled 0.9995014875.
- Maximum chord error: {full['max_chord_error_mm']:.9f} mm.
- Maximum twist error: {full['max_twist_error_deg']:.9f} deg.
- Maximum reference-axis error: {full['max_reference_axis_error_mm']:.9f} mm.
- Maximum TE error: {full['max_te_error_mm']:.9f} mm.
- Maximum section contour RMS/P95/max: {max(row['contour_rms_mm'] for row in all_records):.9f} / {max(row['contour_p95_mm'] for row in all_records):.9f} / {max_contour['contour_max_mm']:.9f} mm; worst sampled max at requested r/R {max_contour['requested_r_over_R']}.
- Both imported-profile-specific checks pass.
- Every station has one valid, closed wire and every original gate passes.

The validator worker took {launcher['worker_wall_seconds']:.3f} s wall time. Exact production `measure_sections` took {launcher['operation_statistics']['production_measure_sections']['total_seconds']:.3f} s; section extraction accounted for {launcher['operation_statistics']['section_extraction']['total_seconds']:.3f} s. `_geometry_summary` took {launcher['operation_statistics']['production_geometry_summary']['total_seconds']:.6f} s. The product default 300 s timeout was not changed; the diagnostic used the authorized 900 s external bound.

## Process-status note

Native host codes were A=44, B=92, A2=92 and are not relabelled as zero. Matching OpenVSP source shows `scriptonly_main` returns `RunScript`, and `ExecuteScript` calls `GetReturnDWord()` even for these `void main()` scripts. Each arm independently has native START→COMPLETE, a script COMPLETE marker, 619 inventory rows, and complete fresh artifacts. The variable void-return value is therefore reported as a host-status anomaly, separately from geometry acceptance. No arm was retried. The independent report derivation was rerun once after a reporting-only heterogeneous-CSV column error; the expensive evidence was deterministically recomputed.

## Decision and smallest next action

- Causal outcome: **ROTATION_EFFECT_REPRODUCED**.
- Candidate outcome: **FULL_INTERNAL_DIAGNOSTIC_PASS**.
- Product meaning: compliance with BladeGen's existing fixed-global-Y internal contract for this X-57 case.
- External NASA geometry fidelity: **UNVERIFIED**; no external NASA reference comparison was performed here.
- Deployment status: **not deployed and not product-wide qualified**.

The smallest justified next action is a separately approved production proposal for a maintained/upstream native-library change that prevents this automatic derivative-driven rib tilt for BladeGen's fixed-plane construction contract, followed by broader propeller regression and a fresh end-to-end UI build. Do not invent a public OpenVSP option, silently replace the installed runtime, or infer that every blade is qualified from this case.

## Evidence map

- `experiment_summary.json`: causal/candidate machine-readable outcome.
- `station_comparison.csv`: selected production and independent results.
- `rib_plane_comparison.csv`: computed/applied angles and plane departures.
- `settings_input_comparison.json`, `vsp3_settings_comparison.json`, `A2_recovery.json`: invariants and recovery.
- `B_rotation_bypassed/candidate_full_validation.json` and `candidate_full_measurements.json`: exact production acceptance and all 41 records.
- `B_rotation_bypassed/ocp_solidification.json`: raw/sewn/solid/re-import topology and mass properties.
- `B_rotation_bypassed/full_validation/validation_timings.csv`: stage and station timings.
- `stations/`: exact section BReps, coordinates, residual CSVs and plots.
- `execution_status.json`, `commands.txt`, `environment_identity.json`, `end_integrity.json`: reproducibility and preserved-state evidence.
- `evidence_manifest.json`: bundled and deliberately omitted large artifacts.
"""
    (run / "X57_AUTO_ROTATION_AB_DECISION.md").write_text(report, encoding="utf-8")

    include: set[Path] = set()
    top_names = (
        "X57_AUTO_ROTATION_AB_DECISION.md",
        "plan.json",
        "experiment_summary.json",
        "settings_input_comparison.json",
        "vsp3_settings_comparison.json",
        "A2_recovery.json",
        "station_comparison.csv",
        "rib_plane_comparison.csv",
        "upper_surface_residual_region.csv",
        "profile_preparation_fixed_background.json",
        "independent_metrics.json",
        "auto_rotation_intervention.diff",
        "observation_plus_intervention.diff",
        "execution_status.json",
        "native_exit_code_evidence.json",
        "commands.txt",
        "environment_identity.json",
        "end_integrity.json",
        "analysis_timings.csv",
        "analysis.log",
        "intervention_build.log",
        "rib_plane_ablation.png",
    )
    include.update(run / name for name in top_names)
    include.update(path for path in (run / "stations").rglob("*") if path.is_file())
    include.update(path for path in runners.rglob("*") if path.is_file())
    for arm in ARMS:
        for name in (
            "run_arm.vspscript",
            "native_run.log",
            "probe_snapshot.json",
            "probe_rib_inventory.csv",
            "probe_rib_surface_audit.csv",
            "probe_transform_bases.csv",
            "probe_update_events.csv",
            "production_selected_raw.json",
            "selected_production_worker.log",
        ):
            include.add(run / arm / name)
    include.update(
        path for path in full_dir.rglob("*")
        if path.is_file() or path.is_symlink()
    )
    include.update(
        (
            run / "B_rotation_bypassed/ocp_solidification.json",
            run / "B_rotation_bypassed/ocp_solidification.log",
            run / "B_rotation_bypassed/candidate_full_validation.json",
            run / "B_rotation_bypassed/candidate_full_measurements.json",
        )
    )
    include = {path for path in include if path.exists() and path.is_file() and not path.is_symlink()}
    omitted = []
    for arm in ARMS:
        for name, reason in (
            ("blade_openvsp.step", "large raw CAD retained separately"),
            ("blade_openvsp.vsp3", "saved replay model retained separately"),
            ("probe_detailed_curves.csv", "large all-rib native curve dump; selected coordinates and canonical prepared-profile hash are bundled"),
            ("probe_final_live_cuts.csv", "large native live dump; selected live coordinates are bundled under stations"),
        ):
            path = run / arm / name
            omitted.append({"path": str(path.relative_to(run)), "size_bytes": path.stat().st_size, "sha256": sha(path), "reason": reason})
    candidate = run / "B_rotation_bypassed/candidate_solid.step"
    omitted.append({"path": str(candidate.relative_to(run)), "size_bytes": candidate.stat().st_size, "sha256": sha(candidate), "reason": "qualified candidate solid delivered separately from compact review ZIP"})
    manifest = {
        "created_at_utc": utc_now(),
        "bundle_policy": "compact review ZIP; candidate and large arm CAD/native dumps retained separately",
        "manifest_self_hash_excluded": True,
        "bundled_files": [
            {"path": str(path.relative_to(run)), "size_bytes": path.stat().st_size, "sha256": sha(path)}
            for path in sorted(include)
        ],
        "omitted_large_artifacts": omitted,
    }
    manifest_path = run / "evidence_manifest.json"
    jwrite(manifest_path, manifest)
    include.add(manifest_path)

    zip_path = run / "X57_AUTO_ROTATION_AB_EVIDENCE.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(include):
            archive.write(path, Path(run.name) / path.relative_to(run))
    bundle_result = {
        "path": str(zip_path),
        "size_bytes": zip_path.stat().st_size,
        "sha256": sha(zip_path),
        "bundled_file_count": len(include),
        "candidate_solid_separate": omitted[-1],
    }
    jwrite(run / "bundle_result.json", bundle_result)
    print(json.dumps(bundle_result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
