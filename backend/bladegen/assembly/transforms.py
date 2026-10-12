"""Exact OpenCascade blade-copy transforms for cyclic propeller placement."""

from __future__ import annotations

import math

from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf

X_AXIS = gp_Ax1(gp_Pnt(0.0, 0.0, 0.0), gp_Dir(1.0, 0.0, 0.0))


def azimuth_angles(blade_count: int, initial_azimuth_deg: float) -> list[float]:
    return [initial_azimuth_deg + index * 360.0 / blade_count for index in range(blade_count)]


def x_rotation(angle_deg: float) -> gp_Trsf:
    transform = gp_Trsf()
    transform.SetRotation(X_AXIS, math.radians(angle_deg))
    return transform


def rotate_about_x(shape, angle_deg: float):
    operation = BRepBuilderAPI_Transform(shape, x_rotation(angle_deg), True)
    operation.Build()
    if not operation.IsDone():
        raise RuntimeError(f"Blade rotation failed at azimuth {angle_deg:g} degrees")
    return operation.Shape()


def transformed_radial_direction(angle_deg: float) -> list[float]:
    point = gp_Pnt(0.0, 1.0, 0.0).Transformed(x_rotation(angle_deg))
    return [float(point.X()), float(point.Y()), float(point.Z())]
