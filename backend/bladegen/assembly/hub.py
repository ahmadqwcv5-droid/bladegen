"""Simple X-axis cylindrical hub and through-bore primitives."""

from __future__ import annotations

from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt


def _x_cylinder(radius_mm: float, length_mm: float, start_x_mm: float):
    axis = gp_Ax2(gp_Pnt(start_x_mm, 0.0, 0.0), gp_Dir(1.0, 0.0, 0.0))
    maker = BRepPrimAPI_MakeCylinder(axis, radius_mm, length_mm)
    maker.Build()
    if not maker.IsDone():
        raise RuntimeError("OpenCascade X-axis cylinder construction failed")
    return maker.Shape()


def make_hub(hub_diameter_mm: float, hub_length_mm: float):
    return _x_cylinder(hub_diameter_mm / 2.0, hub_length_mm, -hub_length_mm / 2.0)


def make_bore_cutter(
    shaft_bore_diameter_mm: float,
    hub_length_mm: float,
    extension_mm: float = 2.0,
):
    return _x_cylinder(
        shaft_bore_diameter_mm / 2.0,
        hub_length_mm + 2.0 * extension_mm,
        -hub_length_mm / 2.0 - extension_mm,
    )
