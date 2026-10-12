"""OCP Boolean construction of a connected propeller solid."""

from __future__ import annotations

from itertools import combinations
from typing import Callable

from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopoDS import TopoDS

from bladegen.assembly.hub import make_bore_cutter, make_hub
from bladegen.assembly.transforms import (
    azimuth_angles,
    rotate_about_x,
    transformed_radial_direction,
)
from bladegen.assembly.validation import measured_bore, volume_mm3
from bladegen.models import AssemblySpec
from bladegen.solid.ocp_solidify import (
    bounding_box,
    inspect_shape,
    read_step,
    shapes,
    volume_properties,
)

BOOLEAN_FUZZY_TOLERANCE_MM = 1e-7
MINIMUM_OVERLAP_MM3 = 1e-5
COLLISION_VOLUME_TOLERANCE_MM3 = 1e-5
BORE_CLEARANCE_VOLUME_TOLERANCE_MM3 = 1e-5
QUALIFIED_BLADE_COUNTS = frozenset({2, 3, 4})


def _boolean(operation, label: str):
    operation.SetNonDestructive(True)
    operation.SetFuzzyValue(BOOLEAN_FUZZY_TOLERANCE_MM)
    operation.Build()
    if not operation.IsDone():
        raise RuntimeError(f"{label} Boolean operation failed")
    shape = operation.Shape()
    if shape.IsNull():
        raise RuntimeError(f"{label} Boolean operation returned a null shape")
    return shape


def _common(left, right, label: str):
    return _boolean(BRepAlgoAPI_Common(left, right), label)


def _fuse(left, right, label: str):
    return _boolean(BRepAlgoAPI_Fuse(left, right), label)


def _cut(left, right, label: str):
    return _boolean(BRepAlgoAPI_Cut(left, right), label)


def build_assembly(
    reference_blade_step,
    assembly: AssemblySpec,
    progress_callback: Callable[[str], None] | None = None,
) -> tuple[object, dict]:
    if assembly.blade_count not in QUALIFIED_BLADE_COUNTS:
        raise ValueError(
            f"Blade count {assembly.blade_count} is not qualified for Sprint 04A; "
            "the measured production range is 2-4 blades"
        )
    reference = read_step(reference_blade_step)
    reference_info = inspect_shape(reference)
    if reference_info["solids"] != 1 or not reference_info["brepcheck_valid"]:
        raise RuntimeError("Reference blade STEP is not one valid solid")
    reference_volume = float(reference_info["volume_mm3"])

    angles = azimuth_angles(assembly.blade_count, assembly.initial_azimuth_deg)
    blades = [rotate_about_x(reference, angle) for angle in angles]
    copy_volumes = [volume_mm3(blade) for blade in blades]
    maximum_copy_volume_delta = max(abs(volume - reference_volume) for volume in copy_volumes)
    if maximum_copy_volume_delta > max(reference_volume * 1e-9, 1e-6):
        raise RuntimeError("Exact blade transform did not preserve reference volume")
    if progress_callback:
        progress_callback("blade_copies_complete")

    hub = make_hub(assembly.hub_diameter_mm, assembly.hub_length_mm)
    hub_info = inspect_shape(hub)
    overlap_volumes = [
        volume_mm3(_common(blade, hub, f"Hub intersection for blade {index + 1}"))
        for index, blade in enumerate(blades)
    ]
    if any(volume <= MINIMUM_OVERLAP_MM3 for volume in overlap_volumes):
        raise ValueError(
            "Hub does not have a positive-volume intersection with every blade root; "
            f"measured overlaps={overlap_volumes} mm^3"
        )
    if progress_callback:
        progress_callback("hub_intersection_complete")

    collisions: list[dict] = []
    for (left_index, left), (right_index, right) in combinations(enumerate(blades), 2):
        common = _common(left, right, f"Blade collision {left_index + 1}/{right_index + 1}")
        total = volume_mm3(common)
        outside = volume_mm3(_cut(common, hub, "Blade collision outside hub")) if total else 0.0
        collisions.append(
            {
                "blade_pair": [left_index + 1, right_index + 1],
                "total_intersection_mm3": total,
                "outside_hub_intersection_mm3": outside,
                "passed": outside <= COLLISION_VOLUME_TOLERANCE_MM3,
            }
        )
    failed_collisions = [row for row in collisions if not row["passed"]]
    if failed_collisions:
        raise ValueError(f"Unexpected blade-to-blade intersection outside hub: {failed_collisions}")

    if progress_callback:
        progress_callback("fusion_started")
    fused = hub
    fusion_steps: list[dict] = []
    for index, blade in enumerate(blades):
        fused = _fuse(fused, blade, f"Hub/blade fusion {index + 1}")
        info = inspect_shape(fused)
        fusion_steps.append(
            {
                "blade_index": index + 1,
                "solids": info["solids"],
                "brepcheck_valid": info["brepcheck_valid"],
            }
        )
        if info["solids"] != 1 or not info["brepcheck_valid"]:
            raise RuntimeError(f"Fusion through blade {index + 1} did not produce one valid solid")
    if progress_callback:
        progress_callback("fusion_complete")

    if progress_callback:
        progress_callback("bore_started")
    bore = make_bore_cutter(assembly.shaft_bore_diameter_mm, assembly.hub_length_mm)
    final = _cut(fused, bore, "Shaft bore cut")
    final_info = inspect_shape(final)
    if final_info["solids"] != 1 or not final_info["brepcheck_valid"]:
        raise RuntimeError("Shaft bore cut did not produce one valid solid")
    final = TopoDS.Solid_s(shapes(final, TopAbs_SOLID)[0])
    final_info = inspect_shape(final)
    residual_bore_volume = volume_mm3(_common(final, bore, "Shaft bore clearance"))
    if residual_bore_volume > BORE_CLEARANCE_VOLUME_TOLERANCE_MM3:
        raise RuntimeError(
            f"Shaft bore is obstructed by {residual_bore_volume:.9g} mm^3 of material"
        )
    bore_measurement = measured_bore(final, assembly.shaft_bore_diameter_mm / 2.0)
    if bore_measurement["boundary_circle_count"] < 2 or not bore_measurement["x_axis_aligned"]:
        raise RuntimeError(f"Unable to independently measure the X-axis bore: {bore_measurement}")
    if progress_callback:
        progress_callback("bore_complete")

    diagnostics = {
        "rotation_axis": [1.0, 0.0, 0.0],
        "requested_blade_count": assembly.blade_count,
        "actual_blade_placement_count": len(blades),
        "azimuth_angles_deg": angles,
        "radial_directions": [transformed_radial_direction(angle) for angle in angles],
        "reference_blade": reference_info,
        "copy_volumes_mm3": copy_volumes,
        "maximum_copy_volume_delta_mm3": maximum_copy_volume_delta,
        "hub": hub_info,
        "hub_diameter_mm": assembly.hub_diameter_mm,
        "hub_length_mm": assembly.hub_length_mm,
        "shaft_bore_diameter_mm": assembly.shaft_bore_diameter_mm,
        "hub_blade_overlap_mm3": overlap_volumes,
        "minimum_positive_overlap_mm3": MINIMUM_OVERLAP_MM3,
        "blade_collisions": collisions,
        "fusion_steps": fusion_steps,
        "fusion_status": "PASS",
        "boolean_fuzzy_tolerance_mm": BOOLEAN_FUZZY_TOLERANCE_MM,
        "bore": {
            **bore_measurement,
            "residual_material_volume_mm3": residual_bore_volume,
            "continuous_through_hole": residual_bore_volume <= BORE_CLEARANCE_VOLUME_TOLERANCE_MM3,
        },
        "bore_cut_status": "PASS",
        "final_before_export": final_info,
        "final_bbox": bounding_box(final),
        "final_volume": volume_properties(final),
        "passed": True,
    }
    return final, diagnostics
