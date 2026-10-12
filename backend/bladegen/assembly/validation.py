"""Independent OCP measurements used to qualify an assembled propeller."""

from __future__ import annotations

import math

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.GeomAbs import GeomAbs_Circle
from OCP.TopAbs import TopAbs_EDGE, TopAbs_SOLID
from OCP.TopoDS import TopoDS

from bladegen.solid.ocp_solidify import shapes, volume_properties


def volume_mm3(shape) -> float:
    if shape.IsNull() or not shapes(shape, TopAbs_SOLID):
        return 0.0
    return float(volume_properties(shape)["volume_mm3"])


def common_volume_mm3(left, right, fuzzy_tolerance_mm: float = 1e-7) -> float:
    operation = BRepAlgoAPI_Common(left, right)
    operation.SetNonDestructive(True)
    operation.SetFuzzyValue(fuzzy_tolerance_mm)
    operation.Build()
    if not operation.IsDone():
        raise RuntimeError("Independent common-volume measurement failed")
    return volume_mm3(operation.Shape())


def circular_edges_about_x(shape, axis_tolerance: float = 1e-9) -> list[dict]:
    circles: list[dict] = []
    for edge in shapes(shape, TopAbs_EDGE):
        curve = BRepAdaptor_Curve(TopoDS.Edge_s(edge))
        if curve.GetType() != GeomAbs_Circle:
            continue
        circle = curve.Circle()
        direction = circle.Axis().Direction()
        if abs(abs(float(direction.X())) - 1.0) > axis_tolerance:
            continue
        center = circle.Location()
        circles.append(
            {
                "radius_mm": float(circle.Radius()),
                "center_mm": [float(center.X()), float(center.Y()), float(center.Z())],
                "axis": [float(direction.X()), float(direction.Y()), float(direction.Z())],
            }
        )
    return circles


def measured_bore(shape, requested_radius_mm: float, tolerance_mm: float = 1e-5) -> dict:
    candidates = [
        circle
        for circle in circular_edges_about_x(shape)
        if math.isclose(circle["radius_mm"], requested_radius_mm, abs_tol=tolerance_mm)
        and math.hypot(circle["center_mm"][1], circle["center_mm"][2]) <= tolerance_mm
    ]
    return {
        "requested_radius_mm": requested_radius_mm,
        "measured_radii_mm": [circle["radius_mm"] for circle in candidates],
        "maximum_radius_error_mm": (
            max(abs(circle["radius_mm"] - requested_radius_mm) for circle in candidates)
            if candidates
            else None
        ),
        "x_axis_aligned": bool(candidates),
        "boundary_circle_count": len(candidates),
    }
