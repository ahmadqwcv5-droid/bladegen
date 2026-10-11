"""Deterministic, bounded DAT/CSV airfoil coordinate import."""

from __future__ import annotations

import csv
import hashlib
import io
import math
from dataclasses import dataclass
from pathlib import Path

from bladegen.airfoils.geometry_metrics import AirfoilMetrics, measure_airfoil
from bladegen.models import AirfoilCoordinates

MAX_UPLOAD_BYTES = 1_000_000
MAX_COORDINATE_POINTS = 4_000
ORDER_TOLERANCE = 1e-10
NORMALIZED_TOLERANCE = 0.01


@dataclass(frozen=True)
class ImportedAirfoil:
    airfoil: AirfoilCoordinates
    import_format: str
    original_sha256: str
    metrics: AirfoilMetrics
    title: str | None
    normalization: str


def _decode(content: bytes) -> str:
    if not content:
        raise ValueError("The selected airfoil file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(f"Airfoil file exceeds the {MAX_UPLOAD_BYTES}-byte safety limit")
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Airfoil files must use UTF-8 text encoding") from exc


def _number(value: str, line: int) -> float:
    try:
        result = float(value.strip())
    except ValueError as exc:
        raise ValueError(f"Invalid numeric coordinate on line {line}") from exc
    if not math.isfinite(result):
        raise ValueError(f"Non-finite coordinate on line {line}")
    return result


def _strict_direction(points: list[tuple[float, float]], increasing: bool, label: str) -> None:
    differences = [right[0] - left[0] for left, right in zip(points, points[1:])]
    valid = all(value > ORDER_TOLERANCE for value in differences) if increasing else all(
        value < -ORDER_TOLERANCE for value in differences
    )
    if not valid:
        direction = "leading edge to trailing edge" if increasing else "trailing edge to leading edge"
        raise ValueError(f"{label} surface is not strictly ordered {direction}")


def _split_single_contour(points: list[tuple[float, float]]) -> tuple[list, list]:
    if len(points) < 5:
        raise ValueError("A single-contour airfoil requires at least five coordinate rows")
    minimum = min(point[0] for point in points)
    candidates = [index for index, point in enumerate(points) if abs(point[0] - minimum) <= ORDER_TOLERANCE]
    interior = [index for index in candidates if 0 < index < len(points) - 1]
    if len(interior) != 1:
        raise ValueError("Leading edge is ambiguous; expected one interior minimum-x point")
    leading_index = interior[0]
    first = points[: leading_index + 1]
    second = points[leading_index:]
    if len(first) < 3 or len(second) < 3:
        raise ValueError("Both upper and lower surfaces require at least three points")
    _strict_direction(first, increasing=False, label="First")
    _strict_direction(second, increasing=True, label="Second")
    first_mean = sum(point[1] for point in first[1:-1]) / max(1, len(first) - 2)
    second_mean = sum(point[1] for point in second[1:-1]) / max(1, len(second) - 2)
    if first_mean <= second_mean + 1e-8:
        raise ValueError(
            "Unsupported contour ordering: expected trailing-edge upper → leading edge → trailing-edge lower"
        )
    return list(reversed(first)), second


def _parse_dat(text: str) -> tuple[list, list, str | None]:
    points: list[tuple[float, float]] = []
    title: str | None = None
    for line_number, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        fields = stripped.replace(",", " ").split()
        if len(fields) != 2:
            if not points and title is None:
                title = stripped
                continue
            raise ValueError(f"Unsupported DAT row on line {line_number}; expected exactly x y")
        try:
            point = (_number(fields[0], line_number), _number(fields[1], line_number))
        except ValueError:
            if not points and title is None:
                title = stripped
                continue
            raise
        points.append(point)
    return (*_split_single_contour(points), title)


def _parse_csv(text: str) -> tuple[list, list, str | None]:
    rows = list(csv.reader(io.StringIO(text)))
    rows = [row for row in rows if row and any(field.strip() for field in row)]
    if not rows:
        raise ValueError("The selected CSV file is empty")
    header = [field.strip().lower() for field in rows[0]]
    if "x" not in header or "y" not in header:
        raise ValueError("CSV requires a header containing x and y columns")
    x_index, y_index = header.index("x"), header.index("y")
    surface_index = header.index("surface") if "surface" in header else None
    points: list[tuple[float, float]] = []
    surfaces: dict[str, list[tuple[float, float]]] = {"upper": [], "lower": []}
    for line_number, row in enumerate(rows[1:], start=2):
        required = max(x_index, y_index, surface_index or 0)
        if len(row) <= required:
            raise ValueError(f"CSV row {line_number} is missing required columns")
        point = (_number(row[x_index], line_number), _number(row[y_index], line_number))
        if surface_index is None:
            points.append(point)
        else:
            label = row[surface_index].strip().lower()
            if label not in surfaces:
                raise ValueError(f"CSV row {line_number} surface must be upper or lower")
            surfaces[label].append(point)
    if surface_index is None:
        upper, lower = _split_single_contour(points)
    else:
        upper, lower = surfaces["upper"], surfaces["lower"]
        if len(upper) < 3 or len(lower) < 3:
            raise ValueError("CSV must provide at least three upper and three lower points")
        if upper[0][0] > upper[-1][0]:
            upper.reverse()
        if lower[0][0] > lower[-1][0]:
            lower.reverse()
        _strict_direction(upper, increasing=True, label="Upper")
        _strict_direction(lower, increasing=True, label="Lower")
    return upper, lower, None


def _normalize(
    upper: list[tuple[float, float]],
    lower: list[tuple[float, float]],
    requested: bool,
) -> tuple[list[tuple[float, float]], list[tuple[float, float]], str]:
    leading_x = 0.5 * (upper[0][0] + lower[0][0])
    leading_y = 0.5 * (upper[0][1] + lower[0][1])
    trailing_x = 0.5 * (upper[-1][0] + lower[-1][0])
    chord = trailing_x - leading_x
    if chord <= 1e-9:
        raise ValueError("Leading and trailing edges do not define a positive chord")
    already_normalized = (
        abs(leading_x) <= NORMALIZED_TOLERANCE
        and abs(trailing_x - 1.0) <= NORMALIZED_TOLERANCE
        and abs(chord - 1.0) <= NORMALIZED_TOLERANCE
    )
    if not already_normalized and not requested:
        raise ValueError(
            "Coordinates are not normalized to unit chord; retry with explicit normalization enabled"
        )
    if not requested:
        return upper, lower, "preserved normalized source coordinates"

    def transform(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
        return [((x_value - leading_x) / chord, (y_value - leading_y) / chord) for x_value, y_value in points]

    return transform(upper), transform(lower), (
        f"translated by LE ({leading_x:.12g}, {leading_y:.12g}) and divided by chord {chord:.12g}"
    )


def import_airfoil(content: bytes, filename: str, *, normalize: bool = False) -> ImportedAirfoil:
    """Parse one supported file into the exact neutral coordinate representation."""
    text = _decode(content)
    suffix = Path(filename).suffix.lower()
    if suffix == ".dat":
        upper, lower, title = _parse_dat(text)
        import_format = "dat-single-contour"
    elif suffix == ".csv":
        upper, lower, title = _parse_csv(text)
        import_format = "csv-explicit-surfaces" if "surface" in text.splitlines()[0].lower() else "csv-single-contour"
    else:
        raise ValueError("Unsupported airfoil format; use .dat or .csv")
    if len(upper) + len(lower) > MAX_COORDINATE_POINTS:
        raise ValueError(f"Airfoil exceeds the {MAX_COORDINATE_POINTS}-point safety limit")
    upper, lower, normalization = _normalize(upper, lower, normalize)
    airfoil = AirfoilCoordinates(type="coordinates", upper=upper, lower=lower)
    metrics = measure_airfoil(airfoil.upper, airfoil.lower)
    return ImportedAirfoil(
        airfoil=airfoil,
        import_format=import_format,
        original_sha256=hashlib.sha256(content).hexdigest(),
        metrics=metrics,
        title=title,
        normalization=normalization,
    )
