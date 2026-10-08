"""Orchestrate the neutral-spec -> OpenVSP -> OCP pipeline."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path

from bladegen.adapters.openvsp_adapter import HIDDEN_ADAPTER_DEFAULTS, build_and_export
from bladegen.curves.resolver import resolve_blade_spec
from bladegen.models import BladeSpec
from bladegen.solid.ocp_solidify import read_step, solidify_step, write_stl
from bladegen.validation.geometry_validation import compare_steps, validate_openvsp_readback
from bladegen.validation.measure_sections import measure_sections


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validation_rows(result: dict) -> list[dict]:
    readback = result["openvsp_readback"]
    solid = result["solidification"]["solid_after_reimport"]
    roundtrip = result["solidification"]["roundtrip"]
    rows = [
        {
            "category": "bladespec",
            "check": "parse_and_validate",
            "value": True,
            "target": "True",
            "passed": True,
        },
        {
            "category": "openvsp",
            "check": "readback_matches_bladespec",
            "value": readback["max_curve_control_error"],
            "target": "<=1e-12 controls; <=1e-5 mm airfoil",
            "passed": readback["passed"],
        },
        {
            "category": "solid",
            "check": "solid_count",
            "value": solid["solids"],
            "target": "1",
            "passed": solid["solids"] == 1,
        },
        {
            "category": "solid",
            "check": "closed_shell",
            "value": solid["closed_shell"],
            "target": "True",
            "passed": solid["closed_shell"],
        },
        {
            "category": "solid",
            "check": "nondegenerate_free_edges",
            "value": solid["free_edges"],
            "target": "0",
            "passed": solid["free_edges"] == 0,
        },
        {
            "category": "solid",
            "check": "brepcheck_valid",
            "value": solid["brepcheck_valid"],
            "target": "True",
            "passed": solid["brepcheck_valid"],
        },
        {
            "category": "roundtrip",
            "check": "step_reimport",
            "value": roundtrip["volume_delta_mm3"],
            "target": "valid solid; stable volume/bbox",
            "passed": all(
                roundtrip[key]
                for key in (
                    "one_solid",
                    "one_shell",
                    "zero_free_edges",
                    "closed_shell",
                    "brepcheck_valid",
                )
            ),
        },
    ]
    geometry = result.get("geometry_validation")
    if geometry:
        rows.append(
            {
                "category": "geometry",
                "check": "independent_section_measurements",
                "value": geometry["max_te_error_mm"],
                "target": "all preserved thresholds; TE <=0.020 mm",
                "passed": geometry["passed"],
            }
        )
    regression = result.get("x57_regression")
    if regression:
        rows.extend(
            {
                "category": "x57_regression",
                "check": name,
                "value": regression[key],
                "target": target,
                "passed": regression["passed"] if name in ("rms_mm", "p95_mm", "max_mm") else True,
            }
            for name, key, target in (
                ("rms_mm", "rms_mm", "<=0.10 mm"),
                ("p95_mm", "p95_mm", "<=0.25 mm"),
                ("max_mm", "max_mm", "<=0.75 mm"),
                ("bbox_max_abs_error_mm", "bbox_max_abs_error_mm", "reported"),
                ("tip_position_error_mm", "tip_position_error_mm", "reported"),
                ("surface_area_difference_mm2", "surface_area_difference_mm2", "reported"),
            )
        )
    return rows


def _geometry_summary(records: list[dict]) -> dict:
    controls = [row for row in records if row["station_kind"] == "control"]
    required = (
        "chord_pass",
        "twist_pass",
        "reference_axis_pass",
        "contour_rms_pass",
        "contour_p95_pass",
        "contour_max_pass",
        "te_pass",
    )
    root = next(row for row in controls if row["requested_r_over_R"] == 0.20)
    tip = next(row for row in controls if row["requested_r_over_R"] == 1.00)
    return {
        "method": "OCP plane sections of newly re-imported final STEP",
        "passed": all(all(row[key] for key in required) for row in records),
        "stations": records,
        "max_chord_error_mm": max(row["chord_absolute_error_mm"] for row in records),
        "max_twist_error_deg": max(row["twist_absolute_error_deg"] for row in records),
        "max_reference_axis_error_mm": max(
            row["reference_axis_position_error_mm"] for row in records
        ),
        "control_contour_rms_max_mm": max(row["contour_rms_mm"] for row in controls),
        "control_contour_p95_max_mm": max(row["contour_p95_mm"] for row in controls),
        "control_contour_max_mm": max(row["contour_max_mm"] for row in controls),
        "max_te_error_mm": max(row["te_absolute_error_mm"] for row in controls),
        "root_measurement": {
            "requested_r_over_R": root["requested_r_over_R"],
            "measured_r_over_R": root["sampled_r_over_R"],
        },
        "tip_measurement": {
            "requested_r_over_R": tip["requested_r_over_R"],
            "measured_r_over_R": tip["sampled_r_over_R"],
        },
    }


def build(
    spec_path: Path,
    output_dir: Path,
    regression_reference_step: Path | None = None,
) -> dict:
    spec = BladeSpec.from_json(spec_path)
    resolved = resolve_blade_spec(spec)
    output_dir.mkdir(parents=True, exist_ok=True)
    resolved_path = output_dir / "resolved_blade_spec.json"
    resolved_path.write_text(resolved.model_dump_json(indent=2) + "\n", encoding="utf-8")
    adapter = build_and_export(resolved, output_dir)
    readback = validate_openvsp_readback(resolved, adapter.readback)
    if not readback["passed"]:
        raise RuntimeError(f"OpenVSP readback validation failed: {readback}")

    solid_path = output_dir / "blade_solid.step"
    solidification = solidify_step(adapter.step_path, solid_path)
    preview_path = output_dir / "blade_preview.stl"
    write_stl(read_step(solid_path), preview_path)
    spec_copy = output_dir / "blade_spec.json"
    shutil.copyfile(spec_path, spec_copy)
    geometry_validation = _geometry_summary(measure_sections(solid_path, spec))
    if not geometry_validation["passed"]:
        raise RuntimeError(
            f"Independent final-solid geometry validation failed: {geometry_validation}"
        )
    result = {
        "status": "PASS",
        "bladespec": {
            "schema_version": spec.schema_version,
            "path": str(spec_path.resolve()),
            "sha256": _sha256(spec_path),
            "backend_independent": True,
        },
        "outputs": {
            "blade_openvsp_vsp3": str(adapter.vsp3_path.resolve()),
            "blade_openvsp_step": str(adapter.step_path.resolve()),
            "blade_solid_step": str(solid_path.resolve()),
            "blade_preview_stl": str(preview_path.resolve()),
            "blade_spec": str(spec_copy.resolve()),
            "resolved_blade_spec": str(resolved_path.resolve()),
        },
        "openvsp_readback": readback,
        "geometry_validation": geometry_validation,
        "airfoil_resolution": {
            "trailing_edge_policy_v0.2": "smooth_chord_normal",
            "sections": [
                {
                    "r_over_R": section.r_over_R,
                    "policy": section.trailing_edge_policy,
                    "local_chord_mm": section.local_chord_mm,
                    "requested_te_mm": section.requested_trailing_edge_thickness_mm,
                    "generated_te_mm": section.generated_trailing_edge_thickness_mm,
                    "mathematical_error_mm": section.mathematical_error_mm,
                }
                for section in resolved.airfoil_sections
            ],
        },
        "curve_resolution": {
            "resolver_version": resolved.resolver_version,
            "tolerance_profile": resolved.tolerance_profile,
            "curves": {
                name: {
                    "original_control_count": curve.original_control_count,
                    "resolved_point_count": len(curve.parameter_vector),
                    "tolerance": curve.tolerance,
                    "tolerance_unit": curve.tolerance_unit,
                    "max_canonical_vs_resolved_error": curve.max_canonical_vs_resolved_error,
                    "verification_locations": curve.verification_locations,
                }
                for name, curve in resolved.curve_items()
            },
        },
        "hidden_openvsp_adapter_defaults": HIDDEN_ADAPTER_DEFAULTS,
        "solidification": solidification,
    }
    if regression_reference_step:
        regression = compare_steps(regression_reference_step, solid_path)
        result["x57_regression"] = regression
        if not regression["passed"]:
            result["status"] = "FAIL"
            raise RuntimeError(f"X-57 regression failed: {regression}")

    validation_json = output_dir / "validation.json"
    validation_csv = output_dir / "validation.csv"
    result["outputs"]["validation_json"] = str(validation_json.resolve())
    result["outputs"]["validation_csv"] = str(validation_csv.resolve())
    validation_json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    rows = _validation_rows(result)
    with validation_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=("category", "check", "value", "target", "passed")
        )
        writer.writeheader()
        writer.writerows(rows)
    return result
