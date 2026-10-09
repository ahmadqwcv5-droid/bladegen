"""Independent OCP measurements of multi-airfoil final solid STEP files."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.GCPnts import GCPnts_UniformAbscissa
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt
from OCP.ShapeAnalysis import ShapeAnalysis_FreeBounds
from OCP.TopAbs import TopAbs_EDGE, TopAbs_VERTEX
from OCP.TopoDS import TopoDS
from OCP.TopTools import TopTools_HSequenceOfShape
from scipy.spatial import cKDTree

from bladegen.models import BladeSpec
from bladegen.solid.ocp_solidify import read_step, shapes
from bladegen.validation.expected_geometry import placed_contour, section_transform
from bladegen.validation.station_plan import plan_validation_stations


def symmetric_distances(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    return np.concatenate((cKDTree(right).query(left)[0], cKDTree(left).query(right)[0]))


def _section_shape(solid, radius_mm: float, station: float):
    plane = gp_Pln(gp_Pnt(0.0, radius_mm * station, 0.0), gp_Dir(0.0, 1.0, 0.0))
    operation = BRepAlgoAPI_Section(solid, plane, False)
    operation.Build()
    if not operation.IsDone():
        raise RuntimeError(f"OCP section failed at r/R={station}")
    return operation.Shape()


def _wire_diagnostics(section_shape) -> tuple[int, bool, bool]:
    edge_sequence = TopTools_HSequenceOfShape()
    for edge in shapes(section_shape, TopAbs_EDGE):
        edge_sequence.Append(edge)
    wire_sequence = TopTools_HSequenceOfShape()
    ShapeAnalysis_FreeBounds.ConnectEdgesToWires_s(edge_sequence, 1e-7, False, wire_sequence)
    if wire_sequence.Length() != 1:
        return wire_sequence.Length(), False, False
    wire = TopoDS.Wire_s(wire_sequence.Value(1))
    return 1, bool(BRepCheck_Analyzer(wire).IsValid()), bool(BRep_Tool.IsClosed_s(wire))


def _sample_edges(section_shape, points_per_edge: int = 2500) -> list[np.ndarray]:
    result = []
    for edge_shape in shapes(section_shape, TopAbs_EDGE):
        curve = BRepAdaptor_Curve(TopoDS.Edge_s(edge_shape))
        sampler = GCPnts_UniformAbscissa(curve, points_per_edge)
        if not sampler.IsDone():
            raise RuntimeError("Arc-length section sampling failed")
        points = []
        for index in range(1, sampler.NbPoints() + 1):
            point = curve.Value(sampler.Parameter(index))
            points.append((point.X(), point.Z()))
        result.append(np.asarray(points, dtype=float))
    return result


def _vertices(section_shape) -> np.ndarray:
    result = []
    for vertex_shape in shapes(section_shape, TopAbs_VERTEX):
        point = BRep_Tool.Pnt_s(TopoDS.Vertex_s(vertex_shape))
        result.append((point.X(), point.Z()))
    return np.asarray(result, dtype=float)


def _endpoints(vertices: np.ndarray, state) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    _, expected_chord, expected_normal = section_transform(state)
    chord_projection = vertices @ expected_chord
    leading = vertices[int(np.argmin(chord_projection))]
    maximum = float(np.max(chord_projection))
    te_mask = chord_projection >= maximum - 0.05 * state.chord_mm
    trailing = vertices[te_mask]
    normal_projection = trailing @ expected_normal
    low = trailing[int(np.argmin(normal_projection))]
    high = trailing[int(np.argmax(normal_projection))]
    midpoint = 0.5 * (low + high)
    chord_vector = midpoint - leading
    chord_direction = chord_vector / np.linalg.norm(chord_vector)
    actual_normal = np.array([-chord_direction[1], chord_direction[0]])
    te_gap = abs(float((high - low) @ actual_normal))
    return leading, midpoint, chord_vector, te_gap


def _interp_surface(local: np.ndarray, grid: np.ndarray) -> np.ndarray:
    order = np.argsort(local[:, 0])
    x = local[order, 0]
    y = local[order, 1]
    unique_x, unique_indices = np.unique(x, return_index=True)
    return np.interp(grid, unique_x, y[unique_indices])


def _identity_metrics(
    edge_points: list[np.ndarray], leading: np.ndarray, chord_vector: np.ndarray
) -> tuple[float, float]:
    chord = float(np.linalg.norm(chord_vector))
    direction = chord_vector / chord
    normal = np.array([-direction[1], direction[0]])
    candidates = []
    for points in edge_points:
        local = np.column_stack(((points - leading) @ direction, (points - leading) @ normal))
        if float(np.ptp(local[:, 0])) >= 0.75 * chord:
            candidates.append(local)
    if len(candidates) < 2:
        raise RuntimeError("Unable to identify upper/lower main section edges")
    candidates.sort(key=lambda points: float(np.mean(points[:, 1])))
    lower, upper = candidates[0], candidates[-1]
    grid = np.linspace(0.02 * chord, 0.98 * chord, 1201)
    lower_y = _interp_surface(lower, grid)
    upper_y = _interp_surface(upper, grid)
    thickness = float(np.max(upper_y - lower_y) / chord)
    camber = float(np.max(np.abs(0.5 * (upper_y + lower_y))) / chord)
    return thickness, camber


def measure_sections(step_path: Path, spec: BladeSpec) -> list[dict]:
    solid = read_step(step_path)
    radius = spec.diameter_mm / 2.0
    records = []
    plan = plan_validation_stations(spec)
    for planned in plan.stations:
        requested = planned.requested_r_over_R
        station = planned.sampled_r_over_R
        expected_contour, state, metadata = placed_contour(spec, station)
        section_shape = _section_shape(solid, radius, station)
        edges = shapes(section_shape, TopAbs_EDGE)
        wire_count, wire_valid, wire_closed = _wire_diagnostics(section_shape)
        edge_points = _sample_edges(section_shape)
        cad_contour = np.vstack(edge_points)
        leading, trailing_midpoint, chord_vector, te_gap = _endpoints(
            _vertices(section_shape), state
        )
        chord = float(np.linalg.norm(chord_vector))
        twist = 90.0 - math.degrees(math.atan2(chord_vector[1], chord_vector[0]))
        actual_reference = leading + spec.reference_axis_x_over_c * chord_vector
        expected_reference, _, _ = section_transform(state)
        distances = symmetric_distances(cad_contour, expected_contour)
        thickness_ratio, camber_ratio = _identity_metrics(edge_points, leading, chord_vector)
        chord_error = abs(chord - state.chord_mm)
        twist_error = abs(twist - state.twist_deg)
        axis_error = float(np.linalg.norm(actual_reference - expected_reference))
        rms = float(np.sqrt(np.mean(distances * distances)))
        p95 = float(np.percentile(distances, 95))
        maximum = float(np.max(distances))
        is_control = "airfoil_station" in planned.roles
        source_section = (
            next(section for section in spec.airfoil_sections if section.r_over_R == requested)
            if is_control
            else None
        )
        requested_te = source_section.trailing_edge_thickness_mm if source_section else None
        expected_te_at_sample = metadata["expected_te_mm"]
        endpoint_inferred_te = (
            te_gap + requested_te - expected_te_at_sample
            if planned.endpoint and requested_te is not None
            else None
        )
        records.append(
            {
                "requested_r_over_R": requested,
                "sampled_r_over_R": station,
                "station_kind": planned.station_kind,
                "station_roles": list(planned.roles),
                "endpoint": planned.endpoint,
                "sample_offset_r_over_R": planned.sample_offset_r_over_R,
                "direct_endpoint_measurement": planned.endpoint is None,
                "airfoil_code": (
                    source_section.airfoil.code
                    if source_section and source_section.airfoil.type == "naca4"
                    else ""
                ),
                "left_profile_r_over_R": metadata["left_profile_r_over_R"],
                "right_profile_r_over_R": metadata["right_profile_r_over_R"],
                "section_edges": len(edges),
                "resulting_wires": wire_count,
                "wire_valid": wire_valid,
                "wire_closed": wire_closed,
                "wire_count_pass": wire_count == 1,
                "wire_valid_pass": wire_valid,
                "wire_closed_pass": wire_closed,
                "expected_chord_mm": state.chord_mm,
                "actual_chord_mm": chord,
                "chord_absolute_error_mm": chord_error,
                "expected_twist_deg": state.twist_deg,
                "actual_twist_deg": twist,
                "twist_absolute_error_deg": twist_error,
                "reference_axis_position_error_mm": axis_error,
                "requested_te_mm": requested_te,
                "diagnostic_expected_te_mm": expected_te_at_sample,
                "expected_te_at_sample_mm": expected_te_at_sample,
                "measured_te_mm": te_gap,
                "te_absolute_error_mm": abs(te_gap - expected_te_at_sample),
                "te_relative_error": (
                    abs(te_gap - expected_te_at_sample) / expected_te_at_sample
                    if expected_te_at_sample != 0.0
                    else 0.0
                ),
                "inferred_endpoint_te_mm": endpoint_inferred_te,
                "inferred_endpoint_te_error_mm": (
                    abs(endpoint_inferred_te - requested_te)
                    if endpoint_inferred_te is not None and requested_te is not None
                    else None
                ),
                "measured_max_thickness_over_chord": thickness_ratio,
                "measured_max_camber_over_chord": camber_ratio,
                "contour_rms_mm": rms,
                "contour_p95_mm": p95,
                "contour_max_mm": maximum,
                "chord_pass": chord_error <= 0.05,
                "twist_pass": twist_error <= 0.05,
                "reference_axis_pass": axis_error <= 0.05,
                "contour_rms_pass": rms <= (0.03 if is_control else 0.05),
                "contour_p95_pass": p95 <= (0.06 if is_control else 0.10),
                "contour_max_pass": maximum <= (0.12 if is_control else 0.20),
                "te_pass": abs(te_gap - expected_te_at_sample) <= 0.02,
            }
        )
    return records
