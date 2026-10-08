"""OCP/OpenCascade sewing-only solidification for OpenVSP STEP faces."""

from __future__ import annotations

from pathlib import Path

from OCP.Bnd import Bnd_Box
from OCP.BRep import BRep_Tool
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid, BRepBuilderAPI_Sewing
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepLib import BRepLib
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import (
    STEPControl_ManifoldSolidBrep,
    STEPControl_Reader,
    STEPControl_Writer,
)
from OCP.StlAPI import StlAPI_Writer
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SHELL, TopAbs_SOLID
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS
from OCP.TopTools import TopTools_IndexedDataMapOfShapeListOfShape, TopTools_IndexedMapOfShape


def read_step(path: Path):
    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise RuntimeError(f"Unable to read STEP: {path}")
    if reader.TransferRoots() == 0:
        raise RuntimeError(f"STEP contains no transferable roots: {path}")
    return reader.OneShape()


def shapes(shape, kind) -> list:
    indexed = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, kind, indexed)
    return [indexed.FindKey(index) for index in range(1, indexed.Extent() + 1)]


ADAPTIVE_VOLUME_TOLERANCE = 1e-9


def _mass(shape, kind: str) -> float:
    properties = GProp_GProps()
    if kind == "surface":
        BRepGProp.SurfaceProperties_s(shape, properties)
    elif kind == "volume":
        BRepGProp.VolumeProperties_s(shape, properties)
    else:
        raise ValueError(kind)
    return float(properties.Mass())


def _volume_properties(shape, tolerance: float = ADAPTIVE_VOLUME_TOLERANCE) -> dict:
    """Return authoritative adaptive-GK volume plus fixed-rule diagnostics."""
    adaptive = GProp_GProps()
    estimated_error = float(
        BRepGProp.VolumePropertiesGK_s(shape, adaptive, tolerance, True, True, False, False, False)
    )
    if estimated_error < 0.0:
        raise RuntimeError("Adaptive OpenCascade volume integration failed")
    fixed = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, fixed)
    return {
        "volume_mm3": float(adaptive.Mass()),
        "volume_method": "OpenCascade BRepGProp.VolumePropertiesGK_s adaptive Gauss-Kronrod",
        "volume_relative_tolerance": tolerance,
        "volume_estimated_relative_error": estimated_error,
        "fixed_rule_volume_mm3_diagnostic": float(fixed.Mass()),
        "fixed_minus_adaptive_mm3": float(fixed.Mass() - adaptive.Mass()),
    }


def _bbox(shape) -> dict:
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box)
    xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
    return {
        "min_mm": [float(xmin), float(ymin), float(zmin)],
        "max_mm": [float(xmax), float(ymax), float(zmax)],
        "extent_mm": [float(xmax - xmin), float(ymax - ymin), float(zmax - zmin)],
    }


def _edge_status(shape) -> tuple[int, int, dict[str, int]]:
    mapping = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, mapping)
    free = 0
    degenerate = 0
    distribution: dict[str, int] = {}
    for index in range(1, mapping.Extent() + 1):
        count = int(mapping.FindFromIndex(index).Size())
        distribution[str(count)] = distribution.get(str(count), 0) + 1
        if count == 1:
            edge = TopoDS.Edge_s(mapping.FindKey(index))
            if BRep_Tool.Degenerated_s(edge):
                degenerate += 1
            else:
                free += 1
    return free, degenerate, distribution


def inspect_shape(shape) -> dict:
    solids = shapes(shape, TopAbs_SOLID)
    shells = shapes(shape, TopAbs_SHELL)
    faces = shapes(shape, TopAbs_FACE)
    free, degenerate, adjacency = _edge_status(shape)
    result = {
        "shape_type": str(shape.ShapeType()).split(".")[-1].replace("TopAbs_", ""),
        "solids": len(solids),
        "shells": len(shells),
        "faces": len(faces),
        "free_edges": free,
        "degenerate_single_face_edges": degenerate,
        "edge_face_adjacency": adjacency,
        "closed_shell": (
            len(shells) == 1 and free == 0 and BRep_Tool.IsClosed_s(TopoDS.Shell_s(shells[0]))
        ),
        "brepcheck_valid": bool(BRepCheck_Analyzer(shape).IsValid()),
        "surface_area_mm2": _mass(shape, "surface"),
        "bbox": _bbox(shape),
    }
    if solids:
        result.update(_volume_properties(shape))
    else:
        result["volume_mm3"] = None
    return result


def write_stl(shape, output_path: Path, linear_deflection_mm: float = 0.1) -> None:
    """Tessellate the validated final solid and write its preview STL."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mesh = BRepMesh_IncrementalMesh(shape, linear_deflection_mm, False, 0.2, True)
    mesh.Perform()
    if not mesh.IsDone():
        raise RuntimeError("OpenCascade preview tessellation failed")
    writer = StlAPI_Writer()
    if not writer.Write(shape, str(output_path)):
        raise RuntimeError("OpenCascade STL export failed")


def solidify_step(source_step: Path, output_step: Path, tolerance_mm: float = 1e-9) -> dict:
    source = read_step(source_step)
    source_faces = shapes(source, TopAbs_FACE)
    if not source_faces:
        raise RuntimeError("OpenVSP STEP contains no faces")

    sewing = BRepBuilderAPI_Sewing(tolerance_mm, True, True, True, False)
    for face in source_faces:
        sewing.Add(face)
    sewing.Perform()
    sewed = sewing.SewedShape()
    shells = shapes(sewed, TopAbs_SHELL)
    if len(shells) != 1:
        raise RuntimeError(f"Sewing produced {len(shells)} shells")
    shell = TopoDS.Shell_s(shells[0])
    shell_info = inspect_shape(shell)
    if not shell_info["closed_shell"] or not shell_info["brepcheck_valid"]:
        raise RuntimeError("Sewing did not produce one valid closed shell")

    maker = BRepBuilderAPI_MakeSolid(shell)
    if not maker.IsDone():
        raise RuntimeError("BRepBuilderAPI_MakeSolid failed")
    solid = maker.Solid()
    if not BRepLib.OrientClosedSolid_s(solid):
        raise RuntimeError("BRepLib.OrientClosedSolid_s failed")
    before = inspect_shape(solid)
    if before["solids"] != 1 or not before["brepcheck_valid"]:
        raise RuntimeError("Created solid is invalid")

    output_step.parent.mkdir(parents=True, exist_ok=True)
    writer = STEPControl_Writer()
    if writer.Transfer(solid, STEPControl_ManifoldSolidBrep) != IFSelect_RetDone:
        raise RuntimeError("STEPControl_Writer transfer failed")
    if writer.Write(str(output_step)) != IFSelect_RetDone:
        raise RuntimeError("STEPControl_Writer write failed")

    reimported = inspect_shape(read_step(output_step))
    bbox_delta = max(
        abs(left - right)
        for key in ("min_mm", "max_mm")
        for left, right in zip(before["bbox"][key], reimported["bbox"][key])
    )
    checks = {
        "one_solid": reimported["solids"] == 1,
        "one_shell": reimported["shells"] == 1,
        "zero_free_edges": reimported["free_edges"] == 0,
        "closed_shell": reimported["closed_shell"],
        "brepcheck_valid": reimported["brepcheck_valid"],
        "volume_delta_mm3": abs(before["volume_mm3"] - reimported["volume_mm3"]),
        "bbox_max_abs_delta_mm": bbox_delta,
    }
    if not all(
        checks[key]
        for key in ("one_solid", "one_shell", "zero_free_edges", "closed_shell", "brepcheck_valid")
    ):
        raise RuntimeError(f"STEP round-trip failed: {checks}")

    return {
        "source": inspect_shape(source),
        "sewing_tolerance_mm": tolerance_mm,
        "sewing": {
            "free_edges": int(sewing.NbFreeEdges()),
            "contiguous_edges": int(sewing.NbContigousEdges()),
            "multiple_edges": int(sewing.NbMultipleEdges()),
            "degenerated_shapes": int(sewing.NbDegeneratedShapes()),
            "deleted_faces": int(sewing.NbDeletedFaces()),
            "added_faces": 0,
        },
        "shell": shell_info,
        "solid_before_export": before,
        "solid_after_reimport": reimported,
        "roundtrip": checks,
    }
