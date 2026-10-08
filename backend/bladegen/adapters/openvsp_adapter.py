"""Translate resolved neutral BladeSpec into an OpenVSP PROP."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from bladegen.models import (
    ResolvedBladeSpec,
    ResolvedCurve,
    RotationDirection,
)

MM_PER_INCH = 25.4

# Stable backend policy, intentionally absent from BladeSpec.
HIDDEN_ADAPTER_DEFAULTS = {
    "single_blade": True,
    "prop_mode": "blade",
    "precone_deg": 0.0,
    "feather_deg": 0.0,
    "cylindrical_sections": False,
    "zero_unmodeled_pcurves": ["sweep", "induced_lift_coefficient", "axial", "tangential"],
    "root_and_tip_end_caps": "OpenVSP option 1, length 1, offset 0, strength 0.5",
    "airfoil_modifiers": "none; scale 1, offsets/rotation 0, no close/trim/flap",
    "surface_numerics": {
        "LECluster": 0.2,
        "TECluster": 0.2,
        "InCluster": 0.25,
        "OutCluster": 0.25,
        "Tess_U": 41,
        "Tess_W": 81,
        "SectTess_U": 6,
        "SmallPanelW": 0.0017510362728820603,
        "MaxGrowth": 1.1820996252126847,
    },
    "step_export": {
        "length_unit": "inch (STEP reader converts to millimeters)",
        "tolerance": 1e-6,
        "split_surfaces": True,
        "merge_points": False,
        "trim_trailing_edge": False,
        "merge_leading_trailing_edges": False,
        "export_prop_main_surface": True,
    },
}


@dataclass(frozen=True)
class AdapterResult:
    prop_id: str
    vsp3_path: Path
    step_path: Path
    readback: dict
    api_errors: list[str]


def _load_openvsp() -> ModuleType:
    try:
        import openvsp_config
    except ModuleNotFoundError:
        root = os.environ.get("OPENVSP_ROOT")
        if not root:
            raise RuntimeError(
                "OpenVSP Python API not found. Set OPENVSP_ROOT to the official OpenVSP distribution root."
            )
        python_root = Path(root) / "python"
        for child in ("openvsp", "openvsp_config", "degen_geom", "utilities"):
            sys.path.insert(0, str(python_root / child))
        import openvsp_config
    openvsp_config.LOAD_GRAPHICS = False
    import openvsp as vsp

    return vsp


def interpolation_name(value: int, vsp: ModuleType) -> str:
    mapping = {int(vsp.LINEAR): "linear"}
    if int(value) not in mapping:
        raise RuntimeError(f"Unsupported OpenVSP interpolation type: {value}")
    return mapping[int(value)]


def _parm(vsp: ModuleType, container: str, name: str, group: str) -> str:
    parm_id = vsp.FindParm(container, name, group)
    if not parm_id:
        raise RuntimeError(f"OpenVSP parameter unavailable: {group}.{name}")
    return parm_id


def _set(vsp: ModuleType, container: str, name: str, group: str, value: float) -> None:
    vsp.SetParmVal(_parm(vsp, container, name, group), float(value))


def _get(vsp: ModuleType, container: str, name: str, group: str) -> float:
    return float(vsp.GetParmVal(_parm(vsp, container, name, group)))


def _drain_errors(vsp: ModuleType) -> list[str]:
    manager = vsp.ErrorMgrSingleton.getInstance()
    messages = []
    while manager.GetNumTotalErrors():
        messages.append(manager.PopLastError().GetErrorString())
    return messages


def _xsec_parm_map(vsp: ModuleType, xsec_id: str) -> dict[tuple[str, str], str]:
    return {
        (vsp.GetParmGroupName(parm_id), vsp.GetParmName(parm_id)): parm_id
        for parm_id in vsp.GetXSecParmIDs(xsec_id)
    }


def _configure_sections(vsp: ModuleType, prop_id: str, resolved: ResolvedBladeSpec) -> None:
    sections = resolved.airfoil_sections
    surface_id = vsp.GetXSecSurf(prop_id, 0)
    while vsp.GetNumXSec(surface_id) > len(sections):
        vsp.CutXSec(prop_id, 1)
        vsp.Update()
        surface_id = vsp.GetXSecSurf(prop_id, 0)
    while vsp.GetNumXSec(surface_id) < len(sections):
        count = vsp.GetNumXSec(surface_id)
        vsp.InsertXSec(prop_id, max(0, count - 2), vsp.XS_FILE_AIRFOIL)
        vsp.Update()
        surface_id = vsp.GetXSecSurf(prop_id, 0)
    actual_count = vsp.GetNumXSec(surface_id)
    if actual_count != len(sections):
        raise RuntimeError(
            f"OpenVSP PROP created {actual_count} sections; "
            f"ResolvedBladeSpec requires {len(sections)}"
        )

    neutral_modifiers = {
        ("XSec", "SectTess_U"): 6.0,
        ("XSecCurve", "Invert"): 0.0,
        ("XSecCurve", "Scale"): 1.0,
        ("XSecCurve", "DeltaX"): 0.0,
        ("XSecCurve", "DeltaY"): 0.0,
        ("XSecCurve", "ShiftLE"): 0.0,
        ("XSecCurve", "Theta"): 0.0,
        ("Close", "LE_Close_Type"): 0.0,
        ("Close", "TE_Close_Type"): 0.0,
        ("Trim", "LE_Trim_Type"): 0.0,
        ("Trim", "TE_Trim_Type"): 0.0,
        ("Cap", "LE_Cap_Type"): 1.0,
        ("Cap", "LE_Cap_Length"): 1.0,
        ("Cap", "LE_Cap_Offset"): 0.0,
        ("Cap", "LE_Cap_Strength"): 0.5,
        ("Cap", "TE_Cap_Type"): 1.0,
        ("Cap", "TE_Cap_Length"): 1.0,
        ("Cap", "TE_Cap_Offset"): 0.0,
        ("Cap", "TE_Cap_Strength"): 0.5,
        ("Flap", "TE_Flap_Flag"): 0.0,
    }
    for index in range(len(sections)):
        vsp.ChangeXSecShape(surface_id, index, vsp.XS_FILE_AIRFOIL)
    vsp.Update()
    surface_id = vsp.GetXSecSurf(prop_id, 0)
    for index, section in enumerate(sections):
        xsec_id = vsp.GetXSec(surface_id, index)
        upper = [vsp.vec3d(point[0], point[1], 0.0) for point in section.airfoil.upper]
        lower = [vsp.vec3d(point[0], point[1], 0.0) for point in section.airfoil.lower]
        vsp.SetAirfoilPnts(xsec_id, upper, lower)
        parameters = _xsec_parm_map(vsp, xsec_id)
        radius_id = parameters.get(("XSec", "RadiusFrac"))
        if not radius_id:
            raise RuntimeError("OpenVSP XSec RadiusFrac parameter unavailable")
        vsp.SetParmVal(radius_id, section.r_over_R)
        for key, value in neutral_modifiers.items():
            parm_id = parameters.get(key)
            if parm_id:
                vsp.SetParmVal(parm_id, value)
    vsp.Update()


def _set_curve(vsp: ModuleType, prop_id: str, index: int, curve: ResolvedCurve) -> None:
    vsp.SetPCurve(
        prop_id,
        index,
        list(curve.parameter_vector),
        list(curve.value_vector),
        vsp.LINEAR,
    )
    vsp.Update()


def _configure_geometry(vsp: ModuleType, prop_id: str, resolved: ResolvedBladeSpec) -> None:
    spec = resolved.source_bladespec
    _set(vsp, prop_id, "Diameter", "Design", spec.diameter_mm / MM_PER_INCH)
    _set(vsp, prop_id, "NumBlade", "Design", 1)
    _set(vsp, prop_id, "PropMode", "Design", 0)
    _set(vsp, prop_id, "Rotate", "Design", 0)
    _set(vsp, prop_id, "ConstructXoC", "Design", spec.reference_axis_x_over_c)
    _set(vsp, prop_id, "FeatherAxisXoC", "Design", spec.reference_axis_x_over_c)
    _set(vsp, prop_id, "FeatherOffsetXoC", "Design", 0)
    _set(vsp, prop_id, "Feather", "Design", 0)
    _set(vsp, prop_id, "UseBeta34Flag", "Design", 0)
    _set(vsp, prop_id, "Precone", "Design", 0)
    _set(
        vsp,
        prop_id,
        "ReverseFlag",
        "Design",
        1 if spec.rotation_direction is RotationDirection.REVERSE else 0,
    )
    _set(vsp, prop_id, "CylindricalSectionsFlag", "Design", 0)
    _set(vsp, prop_id, "AFLimit", "Design", spec.root_radius_ratio)

    _set_curve(vsp, prop_id, vsp.PROP_THICK, resolved.thickness_curve)
    _configure_sections(vsp, prop_id, resolved)

    for name, value in (
        ("LECluster", 0.2),
        ("TECluster", 0.2),
        ("InCluster", 0.25),
        ("OutCluster", 0.25),
    ):
        _set(vsp, prop_id, name, "Design", value)
    for name, value in (
        ("CapUMinOption", 1),
        ("CapUMinLength", 1),
        ("CapUMinOffset", 0),
        ("CapUMinStrength", 0.5),
        ("CapUMaxOption", 1),
        ("CapUMaxLength", 1),
        ("CapUMaxOffset", 0),
        ("CapUMaxStrength", 0.5),
    ):
        _set(vsp, prop_id, name, "EndCap", value)
    _set(vsp, prop_id, "Tess_U", "Shape", 41)
    _set(vsp, prop_id, "Tess_W", "Shape", 81)
    _set(vsp, prop_id, "SmallPanelW", "PropGeom", 0.0017510362728820603)
    _set(vsp, prop_id, "MaxGrowth", "PropGeom", 1.1820996252126847)

    _set_curve(vsp, prop_id, vsp.PROP_CHORD, resolved.chord_curve)
    _set_curve(vsp, prop_id, vsp.PROP_TWIST, resolved.twist_curve)
    _set_curve(vsp, prop_id, vsp.PROP_RAKE, resolved.rake_curve)
    _set_curve(vsp, prop_id, vsp.PROP_SKEW, resolved.skew_curve)

    zero_radii = [spec.root_radius_ratio, 1.0]
    for index in (vsp.PROP_SWEEP, vsp.PROP_CLI, vsp.PROP_AXIAL, vsp.PROP_TANGENTIAL):
        vsp.SetPCurve(prop_id, index, zero_radii, [0.0, 0.0], vsp.LINEAR)
    vsp.Update()


def _configure_step_export(vsp: ModuleType) -> None:
    vehicle = vsp.GetVehicleID()
    settings = {
        "LenUnit": vsp.LEN_IN,
        "Tolerance": 1e-6,
        "SplitSurfs": 1,
        "SplitSubSurfs": 0,
        "MergePoints": 0,
        "ToCubic": 0,
        "ToCubicTol": 1e-6,
        "TrimTE": 0,
        "MergeLETE": 0,
        "ExportPropMainSurf": 1,
    }
    for name, value in settings.items():
        _set(vsp, vehicle, name, "STEPSettings", value)


def _curve_readback(vsp: ModuleType, prop_id: str, index: int, value_name: str) -> dict:
    return {
        "interpolation": interpolation_name(vsp.PCurveGetType(prop_id, index), vsp),
        "points": [
            {"r_over_R": float(radius), value_name: float(value)}
            for radius, value in zip(
                vsp.PCurveGetTVec(prop_id, index), vsp.PCurveGetValVec(prop_id, index)
            )
        ],
    }


def readback_bladespec(vsp: ModuleType, prop_id: str, name: str, schema_version: str) -> dict:
    surface_id = vsp.GetXSecSurf(prop_id, 0)
    sections = []
    for index in range(vsp.GetNumXSec(surface_id)):
        xsec_id = vsp.GetXSec(surface_id, index)
        parameters = _xsec_parm_map(vsp, xsec_id)
        radius = float(vsp.GetParmVal(parameters[("XSec", "RadiusFrac")]))
        sections.append(
            {
                "r_over_R": radius,
                "airfoil": {
                    "type": "coordinates",
                    "upper": [
                        [float(point.x()), float(point.y())]
                        for point in vsp.GetAirfoilUpperPnts(xsec_id)
                    ],
                    "lower": [
                        [float(point.x()), float(point.y())]
                        for point in vsp.GetAirfoilLowerPnts(xsec_id)
                    ],
                },
            }
        )
    return {
        "schema_version": schema_version,
        "name": name,
        "units": "mm",
        "diameter_mm": _get(vsp, prop_id, "Diameter", "Design") * MM_PER_INCH,
        "root_radius_ratio": _get(vsp, prop_id, "AFLimit", "Design"),
        "reference_axis_x_over_c": _get(vsp, prop_id, "ConstructXoC", "Design"),
        "rotation_direction": (
            "reverse" if round(_get(vsp, prop_id, "ReverseFlag", "Design")) else "normal"
        ),
        "airfoil_sections": sections,
        "chord_distribution": _curve_readback(vsp, prop_id, vsp.PROP_CHORD, "chord_over_R"),
        "twist_distribution": _curve_readback(vsp, prop_id, vsp.PROP_TWIST, "twist_deg"),
        "rake_distribution": _curve_readback(vsp, prop_id, vsp.PROP_RAKE, "rake_over_R"),
        "skew_distribution": _curve_readback(vsp, prop_id, vsp.PROP_SKEW, "skew_over_R"),
        "thickness_distribution": _curve_readback(vsp, prop_id, vsp.PROP_THICK, "thickness_ratio"),
    }


def build_and_export(resolved: ResolvedBladeSpec, output_dir: Path) -> AdapterResult:
    spec = resolved.source_bladespec
    vsp = _load_openvsp()
    output_dir.mkdir(parents=True, exist_ok=True)
    vsp.VSPRenew()
    vsp.ClearVSPModel()
    if vsp.FindGeoms():
        raise RuntimeError("OpenVSP adapter did not start from a blank model")
    prop_id = vsp.AddGeom("PROP", "")
    vsp.SetGeomName(prop_id, spec.name)
    _configure_geometry(vsp, prop_id, resolved)
    errors = _drain_errors(vsp)
    if errors:
        raise RuntimeError(f"OpenVSP geometry errors: {errors}")

    readback = readback_bladespec(vsp, prop_id, spec.name, spec.schema_version)
    vsp3_path = output_dir / "blade_openvsp.vsp3"
    step_path = output_dir / "blade_openvsp.step"
    vsp.WriteVSPFile(str(vsp3_path), vsp.SET_ALL)
    _configure_step_export(vsp)
    vsp.ExportFile(str(step_path), vsp.SET_ALL, vsp.EXPORT_STEP)
    errors = _drain_errors(vsp)
    if errors:
        raise RuntimeError(f"OpenVSP export errors: {errors}")
    return AdapterResult(prop_id, vsp3_path, step_path, readback, errors)
