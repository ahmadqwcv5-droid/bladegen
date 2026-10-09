"""Atomic, best-effort progress reporting for isolated CAD builds."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

PROGRESS_FILENAME: Final = "progress.json"


@dataclass(frozen=True)
class ProgressState:
    stage: str
    stage_label: str
    progress_percent: int
    message: str


QUEUED_PROGRESS = ProgressState(
    stage="queued",
    stage_label="Queued",
    progress_percent=0,
    message="Waiting for the CAD worker",
)


class ProgressReporter:
    """Write monotonic stage transitions without making them a build dependency."""

    def __init__(self, path: Path | None) -> None:
        self.path = path
        self._progress_percent = -1

    def report(self, state: ProgressState) -> None:
        if state.progress_percent < self._progress_percent:
            return
        if not 0 <= state.progress_percent <= 100:
            raise ValueError("Progress percentage must be between 0 and 100")
        self._progress_percent = state.progress_percent
        if self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
            temporary.write_text(json.dumps(asdict(state)) + "\n", encoding="utf-8")
            os.replace(temporary, self.path)
        except OSError:
            # Progress is observational. A reporting failure must never turn a
            # geometrically valid CAD build into a failed build.
            return


def read_progress(path: Path) -> ProgressState | None:
    """Return one complete atomic update, or None for absent/invalid content."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return ProgressState(
            stage=str(payload["stage"]),
            stage_label=str(payload["stage_label"]),
            progress_percent=int(payload["progress_percent"]),
            message=str(payload["message"]),
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None
