from __future__ import annotations

import math

import pytest
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

from bladegen.assembly.builder import _boolean
from bladegen.assembly.hub import make_bore_cutter, make_hub
from bladegen.assembly.transforms import (
    azimuth_angles,
    rotate_about_x,
    transformed_radial_direction,
)
from bladegen.assembly.validation import circular_edges_about_x
from bladegen.solid.ocp_solidify import inspect_shape


@pytest.mark.parametrize(
    "count, expected",
    [(2, [10.0, 190.0]), (3, [10.0, 130.0, 250.0]), (4, [10.0, 100.0, 190.0, 280.0])],
)
def test_exact_x_axis_angular_placement(count, expected):
    angles = azimuth_angles(count, 10.0)
    assert angles == expected
    directions = [transformed_radial_direction(angle) for angle in angles]
    for angle, direction in zip(angles, directions):
        assert direction[0] == pytest.approx(0.0, abs=1e-12)
        assert direction[1] == pytest.approx(math.cos(math.radians(angle)), abs=1e-12)
        assert direction[2] == pytest.approx(math.sin(math.radians(angle)), abs=1e-12)


def test_hub_and_bore_are_x_axis_cylinders_with_requested_dimensions():
    hub = make_hub(90.0, 45.0)
    bore = make_bore_cutter(12.0, 45.0)
    hub_info = inspect_shape(hub)
    bore_info = inspect_shape(bore)
    assert hub_info["bbox"]["extent_mm"] == pytest.approx([45.0, 90.0, 90.0])
    assert bore_info["bbox"]["extent_mm"] == pytest.approx([49.0, 12.0, 12.0])
    assert {round(row["radius_mm"], 6) for row in circular_edges_about_x(hub)} == {45.0}
    assert {round(row["radius_mm"], 6) for row in circular_edges_about_x(bore)} == {6.0}


def test_exact_transform_preserves_volume():
    hub = make_hub(90.0, 45.0)
    properties = GProp_GProps()
    BRepGProp.VolumeProperties_s(hub, properties)
    original = properties.Mass()
    transformed = rotate_about_x(hub, 137.5)
    properties = GProp_GProps()
    BRepGProp.VolumeProperties_s(transformed, properties)
    assert properties.Mass() == pytest.approx(original, rel=1e-12)


class FailedBoolean:
    def SetNonDestructive(self, _value):
        pass

    def SetFuzzyValue(self, _value):
        pass

    def Build(self):
        pass

    def IsDone(self):
        return False


@pytest.mark.parametrize("label", ["Hub/blade fusion 2", "Shaft bore cut"])
def test_boolean_failures_return_operation_specific_diagnostics(label):
    with pytest.raises(RuntimeError, match=label):
        _boolean(FailedBoolean(), label)
