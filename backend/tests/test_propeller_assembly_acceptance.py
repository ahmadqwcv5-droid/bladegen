from __future__ import annotations

from pathlib import Path

import pytest

from bladegen.assembly.builder import build_assembly
from bladegen.assembly.hub import make_bore_cutter
from bladegen.assembly.validation import common_volume_mm3, measured_bore
from bladegen.models import AssemblySpec
from bladegen.solid.ocp_solidify import inspect_shape, read_step, write_step


@pytest.mark.integration
@pytest.mark.parametrize(
    "count, angles",
    [
        (2, [0.0, 180.0]),
        (3, [0.0, 120.0, 240.0]),
        (4, [0.0, 90.0, 180.0, 270.0]),
    ],
)
def test_real_two_three_four_blade_assemblies(built_blade, tmp_path, count, angles):
    assembly = AssemblySpec(
        blade_count=count,
        hub_diameter_mm=90,
        hub_length_mm=45,
        shaft_bore_diameter_mm=12,
        initial_azimuth_deg=0,
    )
    final, result = build_assembly(Path(built_blade["outputs"]["blade_solid_step"]), assembly)
    assert result["azimuth_angles_deg"] == angles
    assert result["actual_blade_placement_count"] == count
    assert all(value > 0 for value in result["hub_blade_overlap_mm3"])
    assert all(row["passed"] for row in result["blade_collisions"])
    assert result["maximum_copy_volume_delta_mm3"] < 1e-6
    assert result["bore"]["continuous_through_hole"]
    path = tmp_path / f"propeller_{count}.step"
    write_step(final, path)
    imported = read_step(path)
    topology = inspect_shape(imported)
    assert topology["shape_type"] == "SOLID"
    assert topology["solids"] == 1
    assert topology["shells"] == 1
    assert topology["closed_shell"]
    assert topology["free_edges"] == 0
    assert topology["brepcheck_valid"]
    bore = measured_bore(imported, 6.0)
    assert bore["boundary_circle_count"] == 2
    assert bore["maximum_radius_error_mm"] < 1e-9
    cutter = make_bore_cutter(12, 45)
    assert common_volume_mm3(imported, cutter) < 1e-5


@pytest.mark.integration
def test_real_two_blade_90_by_30_regression(built_blade, tmp_path):
    assembly = AssemblySpec(
        blade_count=2,
        hub_diameter_mm=90,
        hub_length_mm=30,
        shaft_bore_diameter_mm=12,
        initial_azimuth_deg=0,
    )
    final, result = build_assembly(Path(built_blade["outputs"]["blade_solid_step"]), assembly)
    assert result["azimuth_angles_deg"] == [0.0, 180.0]
    assert result["actual_blade_placement_count"] == 2
    assert all(value > 0 for value in result["hub_blade_overlap_mm3"])
    assert all(row["passed"] for row in result["blade_collisions"])
    assert result["maximum_copy_volume_delta_mm3"] < 1e-6
    assert result["bore"]["continuous_through_hole"]

    path = tmp_path / "propeller_two_blade_hub_90x30.step"
    write_step(final, path)
    imported = read_step(path)
    topology = inspect_shape(imported)
    assert topology["shape_type"] == "SOLID"
    assert topology["solids"] == 1
    assert topology["shells"] == 1
    assert topology["closed_shell"]
    assert topology["free_edges"] == 0
    assert topology["brepcheck_valid"]
    assert measured_bore(imported, 6.0)["maximum_radius_error_mm"] < 1e-9
    assert common_volume_mm3(imported, make_bore_cutter(12, 30)) < 1e-5


@pytest.mark.integration
def test_real_assembly_rejects_insufficient_overlap(built_blade):
    assembly = AssemblySpec(
        blade_count=3,
        hub_diameter_mm=60,
        hub_length_mm=45,
        shaft_bore_diameter_mm=12,
        initial_azimuth_deg=0,
    )
    with pytest.raises(ValueError, match="positive-volume intersection"):
        build_assembly(Path(built_blade["outputs"]["blade_solid_step"]), assembly)


@pytest.mark.integration
def test_unqualified_high_blade_count_fails_before_boolean_fusion(built_blade):
    assembly = AssemblySpec(
        blade_count=8,
        hub_diameter_mm=90,
        hub_length_mm=45,
        shaft_bore_diameter_mm=12,
        initial_azimuth_deg=0,
    )
    with pytest.raises(ValueError, match="unsupported in this release"):
        build_assembly(Path(built_blade["outputs"]["blade_solid_step"]), assembly)
