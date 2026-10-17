"""Neutral PropellerSpec -> validated blade -> OCP assembly pipeline."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from bladegen.assembly.builder import BORE_CLEARANCE_VOLUME_TOLERANCE_MM3, build_assembly
from bladegen.assembly.hub import make_bore_cutter
from bladegen.assembly.validation import common_volume_mm3, measured_bore
from bladegen.pipeline import build as build_blade
from bladegen.progress import ProgressReporter, ProgressState
from bladegen.runtime.provenance import completion_context, record_completed_runtime
from bladegen.solid.ocp_solidify import inspect_shape, read_step, write_step, write_stl
from bladegen.validation.propeller_preflight import validate_propeller_payload

ASSEMBLY_PROGRESS = {
    "blade_copies_complete": ProgressState(
        "blade_copies",
        "Blade copies positioned",
        55,
        "Exact OCP X-axis rotations preserve the validated blade volume",
    ),
    "hub_intersection_complete": ProgressState(
        "hub_intersection",
        "Hub intersections verified",
        60,
        "Every blade root has measured positive-volume hub overlap and no outside-hub collision",
    ),
    "fusion_started": ProgressState(
        "fusion", "Fusing hub and blades", 60, "OCP is constructing one connected assembly solid"
    ),
    "fusion_complete": ProgressState(
        "fusion",
        "Hub and blade fusion completed",
        70,
        "The hub and every requested blade form one valid connected solid",
    ),
    "bore_started": ProgressState(
        "bore", "Cutting shaft bore", 70, "OCP is cutting the coaxial X-axis through-hole"
    ),
    "bore_complete": ProgressState(
        "bore",
        "Shaft bore cut completed",
        80,
        "The coaxial X-axis through-bore passed clearance and dimensional checks",
    ),
}


def _bbox_delta(before: dict, after: dict) -> float:
    return max(
        abs(left - right)
        for key in ("min_mm", "max_mm")
        for left, right in zip(before[key], after[key])
    )


def _rows(result: dict) -> list[dict]:
    assembly = result["assembly_validation"]
    topology = assembly["final_after_reimport"]
    return [
        {
            "category": "propeller",
            "check": "blade_count",
            "value": assembly["actual_blade_placement_count"],
            "target": assembly["requested_blade_count"],
            "passed": assembly["actual_blade_placement_count"] == assembly["requested_blade_count"],
        },
        {
            "category": "assembly",
            "check": "positive_hub_overlap",
            "value": min(assembly["hub_blade_overlap_mm3"]),
            "target": f">{assembly['minimum_positive_overlap_mm3']}",
            "passed": all(
                value > assembly["minimum_positive_overlap_mm3"]
                for value in assembly["hub_blade_overlap_mm3"]
            ),
        },
        {
            "category": "assembly",
            "check": "blade_collisions",
            "value": max(
                (row["outside_hub_intersection_mm3"] for row in assembly["blade_collisions"]),
                default=0.0,
            ),
            "target": "<=1e-5 mm3 outside hub",
            "passed": all(row["passed"] for row in assembly["blade_collisions"]),
        },
        {
            "category": "assembly",
            "check": "fusion_status",
            "value": assembly["fusion_status"],
            "target": "PASS",
            "passed": assembly["fusion_status"] == "PASS",
        },
        {
            "category": "bore",
            "check": "bore_cut_status",
            "value": assembly["bore_cut_status"],
            "target": "PASS",
            "passed": assembly["bore_cut_status"] == "PASS",
        },
        {
            "category": "bore",
            "check": "continuous_clearance",
            "value": assembly["bore"]["residual_material_volume_mm3"],
            "target": "<=1e-5 mm3",
            "passed": assembly["bore"]["continuous_through_hole"],
        },
        {
            "category": "topology",
            "check": "solid_count",
            "value": topology["solids"],
            "target": 1,
            "passed": topology["solids"] == 1,
        },
        {
            "category": "topology",
            "check": "closed_shell",
            "value": topology["closed_shell"],
            "target": True,
            "passed": topology["closed_shell"],
        },
        {
            "category": "topology",
            "check": "free_edges",
            "value": topology["free_edges"],
            "target": 0,
            "passed": topology["free_edges"] == 0,
        },
        {
            "category": "topology",
            "check": "brepcheck_valid",
            "value": topology["brepcheck_valid"],
            "target": True,
            "passed": topology["brepcheck_valid"],
        },
        {
            "category": "roundtrip",
            "check": "volume_delta_mm3",
            "value": assembly["roundtrip"]["volume_delta_mm3"],
            "target": "reported; topology invariant",
            "passed": assembly["roundtrip"]["passed"],
        },
    ]


def _require_valid_roundtrip(topology: dict) -> None:
    failures = []
    if topology["solids"] != 1:
        failures.append(f"solids={topology['solids']}")
    if topology["shells"] != 1:
        failures.append(f"shells={topology['shells']}")
    if topology["free_edges"] != 0:
        failures.append(f"free_edges={topology['free_edges']}")
    if not topology["closed_shell"]:
        failures.append("closed_shell=False")
    if not topology["brepcheck_valid"]:
        failures.append("brepcheck_valid=False")
    if failures:
        raise RuntimeError(
            "Final propeller STEP topology failed after re-import: " + ", ".join(failures)
        )


def build_propeller(
    spec_path: Path,
    output_dir: Path,
    progress_path: Path | None = None,
) -> dict:
    """Build one validated propeller without requiring FastAPI or React."""
    progress = ProgressReporter(progress_path)
    progress.report(
        ProgressState(
            "propeller_validation",
            "Validating PropellerSpec",
            5,
            "Checking the neutral assembly contract",
        )
    )
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    spec = validate_propeller_payload(payload, require_runtime_support=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    propeller_spec_path = output_dir / "propeller_spec.json"
    propeller_spec_path.write_text(spec.model_dump_json(indent=2) + "\n", encoding="utf-8")
    blade_input = output_dir / "blade_spec_input.json"
    blade_input.write_text(spec.blade_spec.model_dump_json(indent=2) + "\n", encoding="utf-8")

    progress.report(
        ProgressState(
            "blade_resolution",
            "Resolving reference blade",
            15,
            "PropellerSpec validated; starting the existing BladeSpec pipeline",
        )
    )
    try:
        blade_result = build_blade(
            blade_input,
            output_dir,
            manifest_submitted=payload,
            manifest_build_type="propeller",
            defer_engine_completion=True,
        )
    except Exception as exc:
        raise RuntimeError(f"Reference blade generation failed: {exc}") from exc
    blade_validation_path = output_dir / "blade_validation.json"
    (output_dir / "validation.json").replace(blade_validation_path)
    blade_result["outputs"]["validation_json"] = str(blade_validation_path.resolve())
    blade_csv = output_dir / "validation.csv"
    if blade_csv.exists():
        blade_validation_csv = output_dir / "blade_validation.csv"
        blade_csv.replace(blade_validation_csv)
        blade_result["outputs"]["validation_csv"] = str(blade_validation_csv.resolve())

    progress.report(
        ProgressState(
            "blade_generation",
            "Reference blade generated",
            40,
            "The existing BladeSpec pipeline produced one independently validated source solid",
        )
    )

    def report_assembly(stage: str) -> None:
        progress.report(ASSEMBLY_PROGRESS[stage])

    try:
        final_shape, assembly = build_assembly(
            output_dir / "blade_solid.step",
            spec.assembly,
            progress_callback=report_assembly,
        )
    except ValueError as exc:
        raise ValueError(f"Assembly compatibility failed: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Assembly Boolean construction failed: {exc}") from exc

    propeller_step = output_dir / "propeller_solid.step"
    write_step(final_shape, propeller_step)
    reimported_shape = read_step(propeller_step)
    reimported = inspect_shape(reimported_shape)
    before = assembly["final_before_export"]
    _require_valid_roundtrip(reimported)
    required_topology = True
    bore_cutter = make_bore_cutter(
        spec.assembly.shaft_bore_diameter_mm,
        spec.assembly.hub_length_mm,
    )
    residual = common_volume_mm3(reimported_shape, bore_cutter)
    bore = measured_bore(reimported_shape, spec.assembly.shaft_bore_diameter_mm / 2.0)
    bore.update(
        {
            "residual_material_volume_mm3": residual,
            "continuous_through_hole": residual <= BORE_CLEARANCE_VOLUME_TOLERANCE_MM3,
        }
    )
    if not bore["continuous_through_hole"] or bore["boundary_circle_count"] < 2:
        raise RuntimeError(f"Final propeller STEP bore validation failed: {bore}")
    roundtrip = {
        "one_solid": reimported["solids"] == 1,
        "one_shell": reimported["shells"] == 1,
        "zero_free_edges": reimported["free_edges"] == 0,
        "closed_shell": reimported["closed_shell"],
        "brepcheck_valid": reimported["brepcheck_valid"],
        "volume_delta_mm3": abs(before["volume_mm3"] - reimported["volume_mm3"]),
        "bbox_max_abs_delta_mm": _bbox_delta(before["bbox"], reimported["bbox"]),
        "passed": required_topology,
    }
    assembly["bore"] = bore
    assembly["final_after_reimport"] = reimported
    assembly["roundtrip"] = roundtrip
    assembly["passed"] = required_topology and bore["continuous_through_hole"]

    progress.report(
        ProgressState(
            "assembly_validation",
            "Validating final propeller STEP",
            90,
            "Re-imported topology, bore, mass properties, and placements passed",
        )
    )
    preview_path = output_dir / "propeller_preview.stl"
    write_stl(reimported_shape, preview_path)
    result = {
        "status": "PASS",
        "build_type": "propeller",
        "propeller_spec": {
            "schema_version": spec.schema_version,
            "name": spec.name,
            "backend_independent": True,
        },
        "reference_blade_validation": blade_result,
        "engine": blade_result["engine"],
        "assembly_validation": assembly,
        "completion_context": completion_context(
            submitted=payload,
            build_type="propeller",
            identity=blade_result["engine"],
            planned_section_count=blade_result["geometry_validation"]["station_count"],
            completed_section_count=len(blade_result["geometry_validation"]["stations"]),
        ),
        "outputs": {
            "propeller_solid_step": str(propeller_step.resolve()),
            "propeller_preview_stl": str(preview_path.resolve()),
            "propeller_spec": str(propeller_spec_path.resolve()),
            "blade_solid_step": str((output_dir / "blade_solid.step").resolve()),
            "blade_spec": str((output_dir / "blade_spec.json").resolve()),
            "blade_validation": str(blade_validation_path.resolve()),
            "engine_manifest": str((output_dir / "engine_manifest.json").resolve()),
        },
    }
    validation_path = output_dir / "validation.json"
    validation_csv = output_dir / "assembly_validation.csv"
    result["outputs"]["validation_json"] = str(validation_path.resolve())
    result["outputs"]["assembly_validation_csv"] = str(validation_csv.resolve())
    validation_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    with validation_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=("category", "check", "value", "target", "passed")
        )
        writer.writeheader()
        writer.writerows(_rows(result))
    record_completed_runtime(output_dir / "engine_manifest.json")
    progress.report(
        ProgressState(
            "artifacts",
            "Writing propeller artifacts",
            95,
            "Authoritative STEP, OCP preview, neutral specifications, and validation reports are ready",
        )
    )
    return result
