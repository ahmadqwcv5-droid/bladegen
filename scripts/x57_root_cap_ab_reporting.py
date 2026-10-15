#!/usr/bin/env python3
"""Reporting and evidence-bundle helpers for the X57 root-cap A/B diagnostic.

This module deliberately has no dependency on OpenVSP or the production blade
pipeline.  The experiment supervisor can therefore still create useful timing,
report, and integrity artifacts after an arm times out or exits early.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import zipfile
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TIMING_FIELDS = (
    "scope",
    "source_file",
    "record_type",
    "arm",
    "operation",
    "requested_r_over_R",
    "sampled_r_over_R",
    "station_role",
    "density_factor",
    "start_monotonic_ns",
    "end_monotonic_ns",
    "elapsed_seconds",
    "status",
    "returncode",
    "timed_out",
    "error",
    "command",
)

KNOWN_ARMS = ("A_original", "B_root_cap_intervention", "A2_original_repeat")
ZIP_EXCLUSIONS_FILENAME = "zip_exclusions.json"
MANIFEST_FILENAME = "evidence_manifest.json"
REPORT_FILENAME = "X57_ROOT_CAP_AB_REPORT.md"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _atomic_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=TIMING_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in TIMING_FIELDS})
    temporary.replace(path)


def _as_path_list(paths: Iterable[Path | str] | None) -> list[Path]:
    return [Path(path) for path in paths] if paths is not None else []


def _relative_display(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _arm_from_path(path: Path, root: Path) -> str:
    parts = path.resolve().parts
    for arm in KNOWN_ARMS:
        if arm in parts:
            return arm
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return ""
    if len(relative.parts) > 1:
        candidate = relative.parts[0]
        if candidate.lower() not in {"analysis", "logs", "evidence"}:
            return candidate
    return ""


def _number(value: Any) -> float | int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value if math.isfinite(float(value)) else None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def _event_context(event: Mapping[str, Any], path: Path, root: Path) -> dict[str, Any]:
    return {
        "arm": (
            event.get("arm")
            or event.get("arm_label")
            or event.get("experiment_arm")
            or _arm_from_path(path, root)
        ),
        "requested_r_over_R": event.get("requested_r_over_R"),
        "sampled_r_over_R": event.get("sampled_r_over_R", event.get("r_over_R")),
        "station_role": event.get("station_role", event.get("role")),
        "density_factor": event.get("density_factor"),
    }


def _event_operation(event: Mapping[str, Any]) -> str:
    return str(event.get("operation") or "unknown")


def _event_kind(event: Mapping[str, Any]) -> str:
    kind = str(event.get("event", "")).lower()
    if kind == "operation_start":
        return "start"
    if kind == "operation_end":
        return "end"
    return "instant"


def _event_key(
    operation: str, context: Mapping[str, Any]
) -> tuple[str, str, str, str, str, str]:
    return (
        operation,
        str(context.get("arm", "")),
        str(context.get("requested_r_over_R", "")),
        str(context.get("sampled_r_over_R", "")),
        str(context.get("station_role", "")),
        str(context.get("density_factor", "")),
    )


def _timing_row(
    *,
    root: Path,
    path: Path,
    record_type: str,
    operation: str,
    context: Mapping[str, Any],
    start_ns: Any = None,
    end_ns: Any = None,
    elapsed: Any = None,
    status: Any = None,
    returncode: Any = None,
    timed_out: Any = None,
    error: Any = None,
    command: Any = None,
) -> dict[str, Any]:
    arm = str(context.get("arm") or "")
    return {
        "scope": arm or ("analysis" if "analysis" in path.parts else "supervisor"),
        "source_file": _relative_display(path, root),
        "record_type": record_type,
        "arm": arm,
        "operation": operation,
        "requested_r_over_R": context.get("requested_r_over_R"),
        "sampled_r_over_R": context.get("sampled_r_over_R"),
        "station_role": context.get("station_role"),
        "density_factor": context.get("density_factor"),
        "start_monotonic_ns": _number(start_ns),
        "end_monotonic_ns": _number(end_ns),
        "elapsed_seconds": _number(elapsed),
        "status": status or "UNKNOWN",
        "returncode": returncode,
        "timed_out": timed_out,
        "error": error,
        "command": command,
    }


def _rows_from_event_log(path: Path, root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    active: dict[tuple[str, str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            rows.append(
                _timing_row(
                    root=root,
                    path=path,
                    record_type="event_log_parse_error",
                    operation=f"parse_line_{line_number}",
                    context={"arm": _arm_from_path(path, root)},
                    status="ERROR",
                    error=f"JSONDecodeError: {exc}",
                )
            )
            continue
        if not isinstance(event, Mapping):
            continue
        kind = _event_kind(event)
        operation = _event_operation(event)
        context = _event_context(event, path, root)
        key = _event_key(operation, context)
        if kind == "start":
            active[key].append(dict(event))
            continue
        if kind != "end":
            continue

        start = active[key].pop() if active[key] else {}
        elapsed = _number(event.get("elapsed_seconds"))
        end_ns = _number(event.get("monotonic_ns", event.get("end_monotonic_ns")))
        start_ns = _number(start.get("monotonic_ns", start.get("start_monotonic_ns")))
        if start_ns is None and end_ns is not None and elapsed is not None:
            start_ns = int(float(end_ns) - float(elapsed) * 1e9)
        if elapsed is None and start_ns is not None and end_ns is not None:
            elapsed = (float(end_ns) - float(start_ns)) / 1e9
        rows.append(
            _timing_row(
                root=root,
                path=path,
                record_type="event_operation",
                operation=operation,
                context=context,
                start_ns=start_ns,
                end_ns=end_ns,
                elapsed=elapsed,
                status=event.get("status", "COMPLETED"),
                error=event.get("error"),
            )
        )

    for key, starts in active.items():
        for start in starts:
            context = _event_context(start, path, root)
            rows.append(
                _timing_row(
                    root=root,
                    path=path,
                    record_type="event_operation",
                    operation=key[0],
                    context=context,
                    start_ns=start.get("monotonic_ns", start.get("start_monotonic_ns")),
                    status="INCOMPLETE",
                    error="operation_start has no matching operation_end",
                )
            )
    return rows


def _looks_like_launcher(record: Mapping[str, Any]) -> bool:
    return (
        "elapsed_seconds" in record
        and any(key in record for key in ("returncode", "timed_out", "command", "argv"))
    )


def _iter_launcher_records(
    value: Any, label: str = "launcher"
) -> Iterable[tuple[str, Mapping[str, Any]]]:
    if isinstance(value, Mapping):
        if _looks_like_launcher(value):
            yield label, value
            return
        for key, nested in value.items():
            yield from _iter_launcher_records(nested, f"{label}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from _iter_launcher_records(nested, f"{label}[{index}]")


def _rows_from_launcher(path: Path, root: Path) -> list[dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [
            _timing_row(
                root=root,
                path=path,
                record_type="launcher_parse_error",
                operation="launcher",
                context={"arm": _arm_from_path(path, root)},
                status="ERROR",
                error=f"{type(exc).__name__}: {exc}",
            )
        ]

    rows: list[dict[str, Any]] = []
    for label, record in _iter_launcher_records(value):
        timed_out = bool(record.get("timed_out", False))
        returncode = record.get("returncode")
        if timed_out:
            status = "TIMEOUT"
        elif returncode in (None, 0):
            status = str(record.get("status") or "COMPLETED")
        else:
            status = str(record.get("status") or "ERROR")
        argv = record.get("command") or record.get("argv")
        command = " ".join(map(str, argv)) if isinstance(argv, list) else argv
        context = {
            "arm": record.get("arm") or record.get("arm_label") or _arm_from_path(path, root),
            "requested_r_over_R": record.get("requested_r_over_R"),
            "sampled_r_over_R": record.get("sampled_r_over_R"),
            "station_role": record.get("station_role"),
            "density_factor": record.get("density_factor"),
        }
        rows.append(
            _timing_row(
                root=root,
                path=path,
                record_type="launcher",
                operation=str(record.get("operation") or label),
                context=context,
                start_ns=record.get("start_monotonic_ns"),
                end_ns=record.get("end_monotonic_ns"),
                elapsed=record.get("elapsed_seconds"),
                status=status,
                returncode=returncode,
                timed_out=timed_out,
                error=record.get("error"),
                command=command,
            )
        )
    return rows


def collect_operation_timings(
    evidence_dir: Path | str,
    *,
    output_path: Path | str | None = None,
    event_paths: Iterable[Path | str] | None = None,
    launcher_paths: Iterable[Path | str] | None = None,
) -> list[dict[str, Any]]:
    """Collect operation and process timings and atomically write ``timings.csv``.

    By default every JSONL file below ``evidence_dir`` is treated as an event
    stream and files whose names contain ``launch`` are inspected for one or
    more launcher result dictionaries.  Explicit path lists make this usable
    while a partial run is still being assembled.
    """

    root = Path(evidence_dir).resolve()
    destination = Path(output_path) if output_path is not None else root / "timings.csv"
    events = _as_path_list(event_paths)
    if event_paths is None:
        events = sorted(root.rglob("*.jsonl"))
    launchers = _as_path_list(launcher_paths)
    if launcher_paths is None:
        launchers = sorted(
            path for path in root.rglob("*.json") if "launch" in path.name.lower()
        )

    rows: list[dict[str, Any]] = []
    for path in events:
        if path.is_file():
            rows.extend(_rows_from_event_log(path, root))
    for path in launchers:
        if path.is_file():
            rows.extend(_rows_from_launcher(path, root))
    rows.sort(
        key=lambda row: (
            str(row.get("source_file", "")),
            float(row["start_monotonic_ns"] or -1),
            str(row.get("operation", "")),
        )
    )
    _atomic_csv(destination, rows)
    return rows


def _dig(value: Any, dotted_path: str) -> Any:
    current = value
    for part in dotted_path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _first(value: Any, *paths: str, default: Any = None) -> Any:
    for path in paths:
        candidate = _dig(value, path)
        if candidate is not None:
            return candidate
    return default


def _display(value: Any, *, digits: int = 9) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value)
        return f"{value:.{digits}g}"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, allow_nan=False)
    return str(value)


def _status(value: Any, default: str = "UNAVAILABLE") -> str:
    if isinstance(value, Mapping):
        value = _first(value, "status", "outcome", "result", default=default)
    if value is None or value == "":
        return default
    return str(value)


def _station_rows(summary: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    candidates = (
        _first(summary, "station_comparison", "stations", "measurements.stations"),
        _first(summary, "analysis.station_comparison", "analysis.stations"),
    )
    for candidate in candidates:
        if isinstance(candidate, list):
            return [row for row in candidate if isinstance(row, Mapping)]
        if isinstance(candidate, Mapping):
            nested = candidate.get("rows")
            if isinstance(nested, list):
                return [row for row in nested if isinstance(row, Mapping)]
            rows = []
            for station, row in candidate.items():
                if isinstance(row, Mapping):
                    enriched = dict(row)
                    enriched.setdefault("sampled_r_over_R", station)
                    rows.append(enriched)
            if rows:
                return rows
    return []


def _arm_record(row: Mapping[str, Any], arm: str) -> Mapping[str, Any]:
    names = {
        "A": ("A", "a", "A_original", "a_original"),
        "B": ("B", "b", "B_root_cap_intervention", "b_root_cap_intervention"),
        "A2": ("A2", "a2", "A2_original_repeat", "a2_original_repeat"),
    }.get(arm, (arm, arm.lower()))
    for name in names:
        nested = row.get(name)
        if isinstance(nested, Mapping):
            return nested
    return row


def _metric_triplet(row: Mapping[str, Any], arm: str) -> str:
    arm_lower = arm.lower()
    nested = _arm_record(row, arm)
    rms = _first(
        nested,
        "production.rms_mm",
        "production.contour_rms_mm",
        "production_rms_mm",
        "contour_rms_mm",
        "rms_mm",
        f"{arm}_production.rms_mm",
        f"{arm}_production.contour_rms_mm",
        f"{arm_lower}_production.rms_mm",
        f"{arm_lower}_production_rms_mm",
    )
    p95 = _first(
        nested,
        "production.p95_mm",
        "production.contour_p95_mm",
        "production_p95_mm",
        "contour_p95_mm",
        "p95_mm",
        f"{arm}_production.p95_mm",
        f"{arm}_production.contour_p95_mm",
        f"{arm_lower}_production.p95_mm",
        f"{arm_lower}_production_p95_mm",
    )
    maximum = _first(
        nested,
        "production.sampled_max_mm",
        "production.contour_max_mm",
        "production_sampled_max_mm",
        "contour_max_mm",
        "sampled_max_mm",
        f"{arm}_production.sampled_max_mm",
        f"{arm}_production.contour_max_mm",
        f"{arm_lower}_production.sampled_max_mm",
        f"{arm_lower}_production_sampled_max_mm",
    )
    return " / ".join(_display(value) for value in (rms, p95, maximum))


def _independent_max(row: Mapping[str, Any], arm: str) -> Any:
    arm_lower = arm.lower()
    nested = _arm_record(row, arm)
    return _first(
        nested,
        "independent.sampled_max_mm",
        "independent.sampled_max_4x_mm",
        "independent_4x.sampled_max_mm",
        "independent_4x_sampled_max_mm",
        f"{arm}_independent_4x.sampled_max_mm",
        f"{arm_lower}_independent_4x.sampled_max_mm",
        f"{arm_lower}_independent_4x_sampled_max_mm",
    )


def _render_station_table(summary: Mapping[str, Any]) -> str:
    rows = _station_rows(summary)
    header = (
        "| sampled r/R | role | A production RMS / P95 / sampled max mm | "
        "B production RMS / P95 / sampled max mm | A independent 4x max mm | "
        "B independent 4x max mm | direct A–B 4x max mm | result |\n"
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |"
    )
    if not rows:
        return header + "\n| — | — | — | — | — | — | — | INCOMPLETE / unavailable |"
    rendered = [header]
    for row in rows:
        station = _first(row, "sampled_r_over_R", "r_over_R", "station")
        role = _station_role(row)
        direct = _first(
            row,
            "a_vs_b.independent_4x_sampled_max_mm",
            "a_vs_b.independent_4x.sampled_max_mm",
            "a_vs_b_4x.sampled_max_mm",
            "a_vs_b_4x_sampled_max_mm",
            "A_vs_B_direct_4x.sampled_max_mm",
            "direct_a_vs_b_4x.sampled_max_mm",
            "direct_a_vs_b_4x_sampled_max_mm",
        )
        result = _first(row, "result", "status", "effect")
        if result is None and row.get("material_effect_at_station") is not None:
            result = (
                "MATERIAL_EFFECT"
                if row.get("material_effect_at_station")
                else "NO_MATERIAL_EFFECT"
            )
        if result is None:
            result = "—"
        rendered.append(
            "| "
            + " | ".join(
                (
                    _display(station),
                    _display(role),
                    _metric_triplet(row, "A"),
                    _metric_triplet(row, "B"),
                    _display(_independent_max(row, "A")),
                    _display(_independent_max(row, "B")),
                    _display(direct),
                    _display(result),
                )
            )
            + " |"
        )
    return "\n".join(rendered)


def _topology_by_arm(summary: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    topology = _first(summary, "topology", "whole_output_topology", "analysis.topology", default={})
    result: dict[str, Mapping[str, Any]] = {}
    if isinstance(topology, Mapping):
        for key, value in topology.items():
            if isinstance(value, Mapping):
                result[str(key)] = value
        if any(key in topology for key in ("shape_type", "solids", "faces")):
            result.setdefault("generated output", topology)
    arms = summary.get("arms")
    if isinstance(arms, Mapping):
        for arm, value in arms.items():
            if not isinstance(value, Mapping):
                continue
            topology_value = _first(value, "topology", "measurement.topology")
            if isinstance(topology_value, Mapping):
                result.setdefault(str(arm), topology_value)
    return result


def _render_topology_table(summary: Mapping[str, Any]) -> str:
    rows = _topology_by_arm(summary)
    header = (
        "| arm/output | shape type | solids | shells | faces | free edges | closed shell | "
        "BRepCheck valid |\n| --- | --- | ---: | ---: | ---: | ---: | --- | --- |"
    )
    if not rows:
        return header + "\n| — | — | — | — | — | — | — | unavailable |"
    rendered = [header]
    for arm, row in rows.items():
        rendered.append(
            "| "
            + " | ".join(
                (
                    arm,
                    _display(_first(row, "shape_type", "type")),
                    _display(_first(row, "solids", "solid_count")),
                    _display(_first(row, "shells", "shell_count")),
                    _display(_first(row, "faces", "face_count")),
                    _display(_first(row, "free_edges", "free_edge_count")),
                    _display(_first(row, "closed_shell", "closed")),
                    _display(_first(row, "brepcheck_valid", "valid")),
                )
            )
            + " |"
        )
    return "\n".join(rendered)



def _markdown_cell(value: Any) -> str:
    return _display(value).replace("|", "\\|").replace("\n", "<br>")


def _render_baseline_table(baseline: Any) -> str:
    header = (
        "| sampled r/R | A vs retained raw 4x sampled max mm | Δ production RMS mm | "
        "Δ production P95 mm | Δ production sampled max mm | Δ chord mm | Δ twist deg | "
        "Δ axis error mm | Δ TE mm | passed |\n"
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"
    )
    rows = baseline.get("station_results", []) if isinstance(baseline, Mapping) else []
    if not isinstance(rows, list) or not rows:
        return header + "\n| — | — | — | — | — | — | — | — | — | unavailable |"
    rendered = [header]
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        production = row.get("production_deltas", {})
        additional = row.get("additional_chord_twist_axis_te_deltas", {})
        rendered.append(
            "| "
            + " | ".join(
                _markdown_cell(value)
                for value in (
                    row.get("sampled_r_over_R"),
                    row.get("A_vs_retained_raw_4x_sampled_max_mm"),
                    _first(production, "rms_mm"),
                    _first(production, "p95_mm"),
                    _first(production, "sampled_max_mm"),
                    _first(additional, "actual_chord_mm", "chord_mm"),
                    _first(additional, "actual_twist_deg", "twist_deg"),
                    _first(
                        additional,
                        "reference_axis_position_error_mm",
                        "axis_error_mm",
                    ),
                    _first(additional, "measured_te_mm", "te_mm"),
                    row.get("passed"),
                )
            )
            + " |"
        )
    return "\n".join(rendered)


def _render_generated_outcome_differences(readback: Any) -> str:
    header = (
        "| generated/derived output | A value | B value | B − A | changed |\n"
        "| --- | ---: | ---: | ---: | --- |"
    )
    if not isinstance(readback, Mapping):
        return header + "\n| — | — | — | — | unavailable |"
    rows = _first(readback, "generated_mesh_metric_comparison", default=[])
    if not isinstance(rows, list) or not rows:
        rows = _first(
            readback, "generated_full_parameter_difference_warning", default=[]
        )
    if not isinstance(rows, list) or not rows:
        return header + "\n| — | — | — | — | none recorded |"
    rendered = [header]
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        a_value = _first(row, "A_generated_value", "A_value")
        b_value = _first(row, "B_generated_value", "B_value")
        delta = _first(row, "B_minus_A", "delta")
        changed = _first(row, "changed", default=a_value != b_value)
        rendered.append(
            "| "
            + " | ".join(
                _markdown_cell(value)
                for value in (
                    row.get("semantic_parameter"),
                    a_value,
                    b_value,
                    delta,
                    changed,
                )
            )
            + " |"
        )
    return "\n".join(rendered)


def _render_launcher_table(summary: Mapping[str, Any]) -> str:
    header = (
        "| launcher | return code | timed out | elapsed seconds | log |\n"
        "| --- | ---: | --- | ---: | --- |"
    )
    launchers = _first(summary, "arm_launchers", "launchers", default={})
    if not isinstance(launchers, Mapping) or not launchers:
        return header + "\n| — | — | — | — | unavailable / not launched |"
    rendered = [header]
    for name, launcher in launchers.items():
        if not isinstance(launcher, Mapping):
            continue
        rendered.append(
            "| "
            + " | ".join(
                _markdown_cell(value)
                for value in (
                    name,
                    launcher.get("returncode"),
                    launcher.get("timed_out"),
                    launcher.get("elapsed_seconds"),
                    launcher.get("log_path"),
                )
            )
            + " |"
        )
    return "\n".join(rendered)


def _render_a2_table(summary: Mapping[str, Any]) -> tuple[str, str]:
    header = (
        "| sampled r/R | A production RMS / P95 / max mm | "
        "A2 production RMS / P95 / max mm | A2 vs A direct 4x max mm | "
        "production deltas RMS / P95 / max mm | passed |\n"
        "| ---: | ---: | ---: | ---: | ---: | --- |"
    )
    a2 = _first(summary, "A2_reproduction", "a2_reproduction", default=None)
    if not isinstance(a2, Mapping):
        arms = _first(summary, "arms", default={})
        launchers = _first(summary, "arm_launchers", "launchers", default={})
        arm_record = (
            arms.get("A2_original_repeat") if isinstance(arms, Mapping) else None
        )
        launcher = (
            launchers.get("A2_original_repeat")
            if isinstance(launchers, Mapping)
            else None
        )
        launched = isinstance(arm_record, Mapping) or isinstance(launcher, Mapping)
        if launched:
            detail = {
                "arm_status": _status(arm_record, "UNAVAILABLE"),
                "returncode": (
                    launcher.get("returncode") if isinstance(launcher, Mapping) else None
                ),
                "timed_out": (
                    launcher.get("timed_out") if isinstance(launcher, Mapping) else None
                ),
            }
            return "INCOMPLETE", (
                header
                + "\n| — | — | — | — | — | launched but repeat result incomplete: "
                + _markdown_cell(detail)
                + " |"
            )
        return "NOT_RUN", header + "\n| — | — | — | — | — | not run |"
    passed = a2.get("passed")
    status = "PASS" if passed is True else "FAIL" if passed is False else "INCOMPLETE"
    rows = a2.get("station_results", [])
    if not isinstance(rows, list) or not rows:
        return status, header + "\n| — | — | — | — | — | unavailable |"
    rendered = [header]
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        deltas = _first(row, "production_metric_deltas", "production_deltas", default={})
        delta_triplet = " / ".join(
            _display(_first(deltas, name))
            for name in ("rms_mm", "p95_mm", "sampled_max_mm")
        )
        rendered.append(
            "| "
            + " | ".join(
                (
                    _markdown_cell(row.get("sampled_r_over_R")),
                    _metric_triplet(row, "A"),
                    _metric_triplet(row, "A2"),
                    _markdown_cell(
                        _first(
                            row,
                            "A2_vs_A_direct_4x_sampled_max_mm",
                            "A2_vs_A_direct_4x.sampled_max_mm",
                            "A_vs_A2_direct_4x.sampled_max_mm",
                        )
                    ),
                    delta_triplet,
                    _markdown_cell(row.get("passed")),
                )
            )
            + " |"
        )
    return status, "\n".join(rendered)


def _full_comparison_rows(summary: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = _first(summary, "comparison.stations", "analysis.comparison.stations", default=[])
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, Mapping)]


def _render_upper_deficit_table(summary: Mapping[str, Any]) -> str:
    row = next(
        (
            item
            for item in _full_comparison_rows(summary)
            if _number(item.get("sampled_r_over_R")) is not None
            and abs(float(item["sampled_r_over_R"]) - 0.22302) <= 5.0e-13
        ),
        None,
    )
    header = (
        "| arm | x/c band | arc RMS / P95 / sampled max mm | maximum query x/c,y/c | "
        "signed normal at maximum mm | signed normal min / max mm |\n"
        "| --- | --- | ---: | --- | ---: | ---: |"
    )
    if row is None:
        return header + "\n| — | 0.13–0.18 | — | — | — | unavailable |"
    rendered = [header]
    for arm, key in (("A", "A_upper_deficit_band"), ("B", "B_upper_deficit_band")):
        band = row.get(key)
        if not isinstance(band, Mapping):
            rendered.append(f"| {arm} | 0.13–0.18 | — | — | — | unavailable |")
            continue
        arc = band.get("arc_weighted", {})
        arc_triplet = " / ".join(
            _display(_first(arc, name))
            for name in ("rms_mm", "p95_mm", "sampled_max_mm")
        )
        signed_range = " / ".join(
            _display(band.get(name))
            for name in ("signed_normal_min_mm", "signed_normal_max_mm")
        )
        rendered.append(
            "| "
            + " | ".join(
                (
                    arm,
                    _markdown_cell(band.get("band_x_over_c", [0.13, 0.18])),
                    arc_triplet,
                    _markdown_cell(band.get("maximum_query_x_over_c_y_over_c")),
                    _markdown_cell(
                        band.get("signed_normal_actual_projection_minus_expected_mm_at_max")
                    ),
                    signed_range,
                )
            )
            + " |"
        )
    return "\n".join(rendered)


def _expanded_station_rows(summary: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = _first(
        summary,
        "expanded_station_comparison",
        "expanded_comparison.stations",
        "conditional_expanded_comparison.stations",
        default=[],
    )
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, Mapping)]
    return []


def _render_expanded_table(summary: Mapping[str, Any]) -> str:
    rows = _expanded_station_rows(summary)
    if rows:
        return _render_station_table({"station_comparison": rows})
    conditional = _first(summary, "conditional_expanded_analysis", default={})
    statuses = []
    if isinstance(conditional, Mapping):
        for arm, result in conditional.items():
            statuses.append(
                f"{arm}={_status(result, 'UNAVAILABLE')}"
                if isinstance(result, Mapping)
                else f"{arm}=UNAVAILABLE"
            )
    suffix = "; ".join(statuses) if statuses else "not triggered or unavailable"
    return (
        "| sampled r/R | status |\n| ---: | --- |\n"
        f"| — | {suffix} |"
    )



def _station_role(row: Mapping[str, Any]) -> Any:
    diagnostic = _first(row, "diagnostic_role", "station_role", "role")
    plan_roles = _first(row, "station_roles", "roles")
    if diagnostic is not None and plan_roles is not None:
        return f"{_display(diagnostic)}; station roles={_display(plan_roles)}"
    return diagnostic if diagnostic is not None else plan_roles


def _section_checks(row: Mapping[str, Any], arm: str) -> Mapping[str, Any]:
    checks = _first(
        row,
        f"{arm}_section_checks",
        f"{arm}.section_checks",
        f"{arm.lower()}_section_checks",
        f"{arm.lower()}.section_checks",
        default={},
    )
    return checks if isinstance(checks, Mapping) else {}


def _section_dimensions(checks: Mapping[str, Any]) -> str:
    fields = (
        ("chord", "actual_chord_mm"),
        ("twist", "actual_twist_deg"),
        ("axis", "reference_axis_position_error_mm"),
        ("TE", "measured_te_mm"),
    )
    return "; ".join(f"{label}={_display(checks.get(key))}" for label, key in fields)


def _section_wires(checks: Mapping[str, Any]) -> str:
    fields = (
        ("edges", "section_edges"),
        ("wires", "resulting_wires"),
        ("valid", "wire_valid"),
        ("closed", "wire_closed"),
        ("countPass", "wire_count_pass"),
        ("validPass", "wire_valid_pass"),
        ("closedPass", "wire_closed_pass"),
    )
    return "; ".join(f"{label}={_display(checks.get(key))}" for label, key in fields)


def _section_delta(row: Mapping[str, Any]) -> str:
    delta = _first(
        row,
        "section_B_minus_A",
        "section_metric_deltas",
        "section_deltas",
        default={},
    )
    if not isinstance(delta, Mapping):
        return "—"
    fields = (
        ("chord", "actual_chord_mm"),
        ("twist", "actual_twist_deg"),
        ("axis", "reference_axis_position_error_mm"),
        ("TE", "measured_te_mm"),
    )
    return "; ".join(f"{label}={_display(delta.get(key))}" for label, key in fields)


def _render_engineering_wire_table(rows: Sequence[Mapping[str, Any]]) -> str:
    header = (
        "| sampled r/R | role | A chord/twist/axis/TE | B chord/twist/axis/TE | "
        "B−A deltas | A wire checks | B wire checks | wire integrity same |\n"
        "| ---: | --- | --- | --- | --- | --- | --- | --- |"
    )
    if not rows:
        return header + "\n| — | — | — | — | — | — | — | unavailable |"
    rendered = [header]
    for row in rows:
        a_checks = _section_checks(row, "A")
        b_checks = _section_checks(row, "B")
        rendered.append(
            "| "
            + " | ".join(
                _markdown_cell(value)
                for value in (
                    _first(row, "sampled_r_over_R", "r_over_R", "station"),
                    _station_role(row),
                    _section_dimensions(a_checks),
                    _section_dimensions(b_checks),
                    _section_delta(row),
                    _section_wires(a_checks),
                    _section_wires(b_checks),
                    row.get("section_wire_integrity_same"),
                )
            )
            + " |"
        )
    return "\n".join(rendered)


def _render_harness_integrity(summary: Mapping[str, Any]) -> str:
    integrity = _first(summary, "integrity", "diagnostic_integrity", default={})
    nested = _first(
        summary,
        "harness_source_integrity",
        "harness_integrity",
        "integrity.harness_source_integrity",
        default=None,
    )
    source = nested if isinstance(nested, Mapping) else integrity
    if not isinstance(source, Mapping):
        return "- Harness-source integrity: **UNAVAILABLE IN SUMMARY**"
    unchanged = _first(
        source,
        "unchanged",
        "harness_sources_unchanged",
        "sources_unchanged",
        "matched",
        "passed",
        default="unavailable",
    )
    checks = _first(
        source,
        "identity_checks_passed",
        "checked_before_each_launch",
        "checks_passed",
        "harness_prelaunch_identity_checks_passed",
        default="not separately summarized",
    )
    before = _first(
        source,
        "harness_source_hashes_before",
        "source_hashes_before",
        "before_sha256",
        "before_digest",
        "initial_sha256",
    )
    after = _first(
        source,
        "harness_source_hashes_after",
        "source_hashes_after",
        "after_sha256",
        "after_digest",
        "final_sha256",
    )
    return "\n".join(
        (
            f"- Harness sources unchanged: **{_markdown_cell(unchanged)}**",
            f"- Pre-launch harness identity checks: **{_markdown_cell(checks)}**",
            f"- Harness source hashes before: {_markdown_cell(before)}",
            f"- Harness source hashes after: {_markdown_cell(after)}",
        )
    )

def _render_qualification(summary: Mapping[str, Any]) -> str:
    qualification = _first(summary, "qualification", default={})
    if not isinstance(qualification, Mapping) or not qualification:
        return "- Detailed qualification flags unavailable in the summary."
    return "\n".join(
        f"- `{key}`: **{_markdown_cell(value)}**"
        for key, value in sorted(qualification.items())
    )

def render_report(summary: Mapping[str, Any]) -> str:
    """Render the root-cap A/B report without assuming that every arm finished."""

    outcome = _status(
        _first(summary, "diagnostic_outcome", "experiment_outcome", "outcome", "status"),
        "INCOMPLETE",
    )
    failure = _first(summary, "failure", "supervisor_failure", default=None)
    last_active = _first(
        summary,
        "last_active_operation",
        "runtime.last_active_operation",
        default="unavailable",
    )
    baseline = _first(summary, "baseline_reproduction", "a_reproduction", default={})
    baseline_status = _status(baseline, "UNAVAILABLE")
    baseline_detail = _first(
        baseline,
        "detail",
        "reason",
        default="No completed A-reproduction result was supplied.",
    )
    baseline_threshold = _first(baseline, "threshold_mm", default="unavailable")
    intervention = _first(
        summary,
        "intervention",
        "experiment_plan.intervention",
        default={},
    )
    parameter = _first(
        intervention, "semantic_parameter", "parameter", default="EndCap.CapUMinOption"
    )
    a_value = _first(intervention, "A_original", "a_value", "before", default="unavailable")
    b_value = _first(
        intervention,
        "B_root_cap_intervention",
        "b_value",
        "after",
        default="unavailable",
    )
    readback = _first(summary, "readback_diff", "readback", "intervention_readback", default={})
    readback_status = _status(
        _first(readback, "status", "intervention_status", "accepted"), "UNAVAILABLE"
    )
    confounds = _first(
        readback,
        "confounds",
        "unexpected_changes",
        "unrelated_authored_parameter_changes",
        default="unavailable",
    )
    invariants = _first(
        summary,
        "constraints.invariants",
        "experiment_plan.invariants",
        "invariants",
        default=[],
    )
    if not isinstance(invariants, list):
        invariants = [invariants]
    invariant_lines = (
        "\n".join(f"- {_display(item)}" for item in invariants)
        or "- Unavailable in summary."
    )
    integrity = _first(summary, "integrity", "diagnostic_integrity", default={})
    source_unchanged = _first(
        integrity,
        "production_sources_unchanged",
        "production_and_diagnostic_sources_unchanged_during_run",
        default="unavailable",
    )
    originals_unchanged = _first(
        integrity,
        "original_artifacts_unchanged",
        "failed_job_artifacts_unchanged_during_run",
        default="unavailable",
    )
    original_job = _first(
        summary, "original_statuses.original_job", "original_product_job", default="FAILED"
    )
    internal = _first(
        summary,
        "original_statuses.retained_complete_internal_validation",
        "existing_complete_internal_validator",
        default="FAIL",
    )
    external = _first(
        summary,
        "original_statuses.external_nasa_fidelity",
        "external_nasa_fidelity",
        default="UNVERIFIED",
    )
    tested_head = _first(summary, "git.head", "evidence_identity.git.head", "tested_head")
    recommendation = _first(
        summary,
        "smallest_next_action",
        "recommendation",
        default="Await review of the bounded A/B evidence before changing production geometry.",
    )
    combined_boundary = _first(
        summary,
        "combined_generation_export_boundary",
        "path_boundary",
        "inference_boundary",
        default=(
            "The experiment observes the combined production adapter/OpenVSP surface-generation "
            "and raw STEP export path; it does not independently identify an internal generation "
            "operation versus STEP translation."
        ),
    )
    a2_status, a2_table = _render_a2_table(summary)

    return f"""# X-57 Root-Cap A/B Report

## Outcome

Diagnostic outcome: **{outcome}**.

- Supervisor failure: {_display(failure) if failure else "none recorded"}
- Last active operation: {_display(last_active)}

This is a controlled diagnostic of the combined OpenVSP generation/export path. Experimental
arm B is not an accepted product solid and this report does not change the original job status.

## Launcher results

{_render_launcher_table(summary)}

Commands recorded by the supervisor are retained in `commands.txt`; available subprocess output
is retained in the referenced logs. This report does not claim complete command or stdout/stderr
coverage unless the evidence explicitly proves it. A nonzero return code or timeout remains a
genuine incomplete result; completion is not inferred from partial files.

## A — original configuration reproduction

- Reproduction status: **{baseline_status}**
- Detail: {_display(baseline_detail)}
- Predeclared per-metric threshold: {_display(baseline_threshold)} mm

{_render_baseline_table(baseline)}

The predeclared reproduction criteria remain diagnostic repeatability limits; they do not replace
the production geometry tolerances. B is causally interpretable only when A reproduces the
retained raw geometry and recorded production metrics within these limits.

## Intervention and readback

- Single authored intervention: `{parameter}`
- A value: {_display(a_value)}
- B value: {_display(b_value)}
- Intervention/readback status: **{readback_status}**
- Unexpected unrelated changes/confounds: {_display(confounds)}

### Generated/derived outcome differences (not additional authored inputs)

{_render_generated_outcome_differences(readback)}

These calculated OpenVSP outputs remain visible as warnings and causal evidence. They are not
classified as extra authored interventions or readback confounds.

Dependent parameter state and full semantic readback remain authoritative in
`experiment_plan.json` and `readback_diff.json`. An ignored, clamped, or confounded setting is not
evidence against root-cap influence.

## Primary station comparison

Production and independent statistics remain distinct. All maxima are sampled maxima, not
continuous Hausdorff bounds. No best-fit alignment or per-arm scaling is applied.

{_render_station_table(summary)}

### Primary engineering and section-wire checks

The combined cells report chord mm, twist deg, reference-axis-position error mm, and measured TE
mm. Wire cells retain edge/wire counts, validity/closure states, and all three production wire
pass flags.

{_render_engineering_wire_table(_full_comparison_rows(summary))}

## Worst-station signed upper-surface deficit

At sampled r/R 0.22302, the requested-frame x/c 0.13–0.18 band is compared without registration.
Negative signed normal values mean the projected actual contour lies below the unchanged expected
upper surface in the shared requested normal direction.

{_render_upper_deficit_table(summary)}

## A2 original-configuration repeat

- Repeat status: **{a2_status}**
- A2 is required only after a material A/B effect and must restore A within the predeclared
  repeatability limits before the effect is called reproduced.

{a2_table}

## Conditional expanded-station comparison

These cuts are made only from the already-generated A/B files after a reproduced primary effect.
They investigate spatial extent; they are not a replacement for the unchanged 41-station product
acceptance run.

{_render_expanded_table(summary)}

### Expanded engineering and section-wire checks

{_render_engineering_wire_table(_expanded_station_rows(summary))}

## Whole-output topology

Topology is reported separately from contour agreement. In particular, a no-root-cap B surface
may be useful diagnostic evidence while remaining unsuitable as a closed-solid deliverable.

{_render_topology_table(summary)}

## Generation/export inference boundary

{_display(combined_boundary)}

A repeatable A/B change supports a causal effect of the tested root-cap treatment on exported
geometry under this configuration. It does not by itself identify the exact internal OpenVSP
mechanism, establish a general production correction, or qualify B as manufacturable CAD.

## Controlled constraints and integrity

Held invariants reported by the run:

{invariant_lines}

- Tested HEAD: {_display(tested_head)}
- Production/diagnostic sources unchanged during execution: {_display(source_unchanged)}
- Original retained job artifacts unchanged during execution: {_display(originals_unchanged)}

### Diagnostic harness-source integrity

{_render_harness_integrity(summary)}

Harness identity is reported separately from production-source and retained-artifact integrity;
one does not imply another.

## Qualification boundaries

{_render_qualification(summary)}

- Original product job: **{_display(original_job)}**
- Retained blade complete internal validation: **{_display(internal)}**
- External NASA fidelity: **{_display(external)}**
- Experimental B: diagnostic only; no automatic full-CAD acceptance.
- Raw-surface topology or a changed section alone is not complete geometry acceptance.
- No production geometry correction is implemented by this evidence helper.

## Smallest justified next action

{_display(recommendation)}
"""

def write_report(
    evidence_dir: Path | str,
    summary: Mapping[str, Any],
    *,
    filename: str = REPORT_FILENAME,
) -> Path:
    """Render and atomically write the Markdown report."""

    path = Path(evidence_dir) / filename
    _atomic_text(path, render_report(summary))
    return path


def _bundle_files(root: Path, manifest_path: Path, zip_path: Path) -> list[Path]:
    result: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.is_symlink():
            raise ValueError(f"Refusing to bundle symbolic link: {path}")
        resolved = path.resolve()
        if resolved in {manifest_path.resolve(), zip_path.resolve()}:
            continue
        result.append(path)
    return result



def _verify_archive_members(
    archive_path: Path,
    root: Path,
    manifest_path: Path,
    file_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Hash decompressed ZIP members and compare them with manifest digests."""

    expected: dict[str, dict[str, Any]] = {}
    prefix = Path(root.name)
    for record in file_records:
        if not record.get("included_in_zip"):
            continue
        member = (prefix / str(record["relative_path"])).as_posix()
        expected[member] = {
            "sha256": str(record["sha256"]),
            "size_bytes": int(record["size_bytes"]),
            "source": "evidence_manifest.files",
        }
    manifest_member = (prefix / manifest_path.name).as_posix()
    expected[manifest_member] = {
        "sha256": _sha256_file(manifest_path),
        "size_bytes": manifest_path.stat().st_size,
        "source": "local manifest self-check",
    }

    results: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive_path, "r") as archive:
        corrupt_member = archive.testzip()
        infos = archive.infolist()
        names = [info.filename for info in infos if not info.is_dir()]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        missing = sorted(set(expected) - set(names))
        unexpected = sorted(set(names) - set(expected))
        if corrupt_member is not None or duplicates or missing or unexpected:
            raise RuntimeError(
                "ZIP structure verification failed: "
                f"crc_member={corrupt_member!r}, duplicates={duplicates}, "
                f"missing={missing}, unexpected={unexpected}"
            )
        info_by_name = {info.filename: info for info in infos if not info.is_dir()}
        for member, identity in sorted(expected.items()):
            digest = hashlib.sha256()
            with archive.open(member, "r") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            actual_sha256 = digest.hexdigest()
            actual_size = int(info_by_name[member].file_size)
            matched = (
                actual_sha256 == identity["sha256"]
                and actual_size == identity["size_bytes"]
            )
            results.append(
                {
                    "member": member,
                    "source": identity["source"],
                    "expected_sha256": identity["sha256"],
                    "actual_sha256": actual_sha256,
                    "expected_size_bytes": identity["size_bytes"],
                    "actual_size_bytes": actual_size,
                    "matched": matched,
                }
            )
    failures = [row for row in results if not row["matched"]]
    if failures:
        raise RuntimeError(f"ZIP member SHA-256 verification failed: {failures}")
    return {
        "algorithm": "SHA-256 over decompressed archive member bytes",
        "verified_member_count": len(results),
        "manifest_file_member_count": len(results) - 1,
        "manifest_self_member_verified": True,
        "crc_verified": True,
        "missing_member_count": 0,
        "unexpected_member_count": 0,
        "duplicate_member_count": 0,
        "all_member_hashes_verified": True,
    }

def finalize_evidence_bundle(
    evidence_dir: Path | str,
    *,
    zip_path: Path | str | None = None,
    manifest_path: Path | str | None = None,
    exclusions_path: Path | str | None = None,
) -> dict[str, Any]:
    """Verify evidence files, write a manifest, and create the review ZIP.

    Every file named ``blade_openvsp.step`` remains in its arm directory but is
    excluded from the ZIP.  Its absolute local path, size, and SHA-256 are
    recorded in ``zip_exclusions.json`` and in the manifest.
    """

    root = Path(evidence_dir).resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)
    archive_path = (
        Path(zip_path).resolve() if zip_path is not None else root.with_suffix(".zip")
    )
    manifest = (
        Path(manifest_path).resolve()
        if manifest_path is not None
        else root / MANIFEST_FILENAME
    )
    exclusions = (
        Path(exclusions_path).resolve()
        if exclusions_path is not None
        else root / ZIP_EXCLUSIONS_FILENAME
    )
    try:
        archive_path.relative_to(root)
    except ValueError:
        pass
    else:
        raise ValueError("ZIP path must be outside the evidence directory")
    if manifest.parent != root or exclusions.parent != root:
        raise ValueError("Manifest and exclusions JSON must be direct evidence-directory files")

    excluded_steps = sorted(
        path for path in root.rglob("blade_openvsp.step") if path.is_file()
    )
    exclusion_records = [
        {
            "relative_path": path.relative_to(root).as_posix(),
            "local_path": str(path.resolve()),
            "size_bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
            "reason": "full-model blade_openvsp.step retained locally; omitted from review ZIP",
        }
        for path in excluded_steps
    ]
    _atomic_json(
        exclusions,
        {
            "created_at_utc": _utc_now(),
            "policy": "exclude every full-model file named blade_openvsp.step from the ZIP only",
            "excluded_count": len(exclusion_records),
            "excluded_from_zip": exclusion_records,
        },
    )

    files = _bundle_files(root, manifest, archive_path)
    excluded_resolved = {path.resolve() for path in excluded_steps}
    file_records: list[dict[str, Any]] = []
    for path in files:
        expected = _sha256_file(path)
        actual = _sha256_file(path)
        file_records.append(
            {
                "relative_path": path.relative_to(root).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": expected,
                "expected_sha256": expected,
                "actual_sha256": actual,
                "sha256_verified": actual == expected,
                "included_in_zip": path.resolve() not in excluded_resolved,
            }
        )
    mismatches = [record for record in file_records if not record["sha256_verified"]]
    manifest_value = {
        "created_at_utc": _utc_now(),
        "evidence_root": str(root),
        "algorithm": "SHA-256",
        "manifest_self_inclusion": False,
        "manifest_self_inclusion_reason": "a file cannot contain a stable digest of itself",
        "zip_exclusion_policy": (
            "all files named blade_openvsp.step are retained locally and omitted from ZIP"
        ),
        "zip_post_build_verification_policy": {
            "required_for_success": True,
            "algorithm": "SHA-256 over decompressed member bytes",
            "comparison": "each included member versus its evidence-manifest digest and size",
            "also_rejects": ["missing members", "unexpected members", "duplicate members"],
        },
        "verification": {
            "checked_file_count": len(file_records),
            "mismatch_count": len(mismatches),
            "all_verified": not mismatches,
        },
        "files": file_records,
    }
    _atomic_json(manifest, manifest_value)
    if mismatches:
        raise RuntimeError(f"Evidence SHA-256 verification failed: {mismatches}")

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_archive = archive_path.with_name(f".{archive_path.name}.{os.getpid()}.tmp")
    with zipfile.ZipFile(
        temporary_archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        archive.write(manifest, Path(root.name) / manifest.name)
        for path in files:
            if path.resolve() in excluded_resolved:
                continue
            archive.write(path, Path(root.name) / path.relative_to(root))
    try:
        archive_verification = _verify_archive_members(
            temporary_archive, root, manifest, file_records
        )
    except BaseException:
        temporary_archive.unlink(missing_ok=True)
        raise
    temporary_archive.replace(archive_path)

    return {
        "evidence_directory": str(root),
        "manifest_path": str(manifest),
        "manifest_sha256": _sha256_file(manifest),
        "verified_file_count": len(file_records),
        "all_sha256_verified": True,
        "zip_path": str(archive_path),
        "zip_size_bytes": archive_path.stat().st_size,
        "zip_sha256": _sha256_file(archive_path),
        "zip_crc_verified": archive_verification["crc_verified"],
        "zip_member_hashes_verified": archive_verification[
            "all_member_hashes_verified"
        ],
        "zip_verified_member_count": archive_verification["verified_member_count"],
        "zip_verification": archive_verification,
        "excluded_full_model_step_count": len(exclusion_records),
        "zip_exclusions_path": str(exclusions),
    }


__all__ = [
    "collect_operation_timings",
    "finalize_evidence_bundle",
    "render_report",
    "write_report",
]
