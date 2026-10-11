"""Small persistent local registry for parametric and imported airfoils."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from datetime import UTC, datetime
from pathlib import Path

from bladegen.airfoils.canonical import naca_4digit_coordinates
from bladegen.airfoils.geometry_metrics import measure_airfoil
from bladegen.airfoils.importers import ImportedAirfoil

DEFAULT_NACA_CODES = ("0008", "0010", "0012", "2412", "4412", "4415")
PROFILE_ID = re.compile(r"^(?:naca|imported)-[a-z0-9-]+$")


def canonical_coordinate_sha256(airfoil: dict) -> str:
    payload = json.dumps(airfoil, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def default_library_root() -> Path:
    configured = os.getenv("BLADEGEN_AIRFOIL_LIBRARY")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[3] / "user_data" / "airfoils"


def _naca_record(code: str, *, include_coordinates: bool) -> dict:
    upper, lower = naca_4digit_coordinates(code)
    airfoil = {"type": "naca4", "code": code}
    record = {
        "profile_id": f"naca-{code}",
        "display_name": f"NACA {code}",
        "category": "naca4",
        "source": "BladeGen canonical NACA 4-digit generator",
        "license": "not applicable (parametric mathematical definition)",
        "point_counts": {"upper": len(upper), "lower": len(lower)},
        "metrics": measure_airfoil(upper, lower).to_dict(),
        "airfoil": airfoil,
    }
    if include_coordinates:
        record["source_coordinates"] = {
            "type": "coordinates",
            "upper": upper,
            "lower": lower,
        }
    return record


class AirfoilLibrary:
    """Atomic file-backed registry; BladeSpecs never depend on this registry."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or default_library_root()).resolve()
        self.profile_root = self.root / "profiles"
        self.index_path = self.root / "index.json"
        self._lock = threading.RLock()

    def _ensure(self) -> None:
        self.profile_root.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self._write_json(self.index_path, {"schema_version": 1, "profiles": []})

    @staticmethod
    def _write_json(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)

    def _index(self) -> dict:
        self._ensure()
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Local airfoil library index is unreadable") from exc
        if payload.get("schema_version") != 1 or not isinstance(payload.get("profiles"), list):
            raise RuntimeError("Local airfoil library index has an unsupported schema")
        return payload

    def catalog(self) -> list[dict]:
        with self._lock:
            imported = self._index()["profiles"]
        naca = [_naca_record(code, include_coordinates=False) for code in DEFAULT_NACA_CODES]
        return naca + sorted(imported, key=lambda row: row["display_name"].casefold())

    def get(self, profile_id: str) -> dict:
        if not PROFILE_ID.fullmatch(profile_id):
            raise KeyError(profile_id)
        if profile_id.startswith("naca-"):
            code = profile_id.removeprefix("naca-")
            return _naca_record(code, include_coordinates=True)
        path = self.profile_root / f"{profile_id}.json"
        if not path.is_file():
            raise KeyError(profile_id)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Imported profile {profile_id} is unreadable") from exc

    def add_imported(
        self,
        imported: ImportedAirfoil,
        *,
        display_name: str,
        original_filename: str,
        source: str | None = None,
        license_info: str | None = None,
        notes: str | None = None,
    ) -> dict:
        name = display_name.strip()
        if not name or len(name) > 120:
            raise ValueError("Display name must contain 1–120 characters")
        airfoil = imported.airfoil.model_dump(mode="json")
        canonical_sha = canonical_coordinate_sha256(airfoil)
        profile_id = f"imported-{imported.original_sha256[:12]}-{canonical_sha[:8]}"
        safe_original = Path(original_filename).name[:255]
        metadata = {
            "profile_id": profile_id,
            "display_name": name,
            "category": "imported",
            "original_filename": safe_original,
            "source": (source or "").strip() or "unknown",
            "license": (license_info or "").strip() or "unknown",
            "import_format": imported.import_format,
            "original_sha256": imported.original_sha256,
            "canonical_coordinate_sha256": canonical_sha,
            "point_counts": {
                "upper": len(imported.airfoil.upper),
                "lower": len(imported.airfoil.lower),
            },
            "metrics": imported.metrics.to_dict(),
            "notes": (notes or "").strip() or None,
            "normalization": imported.normalization,
            "created_at": datetime.now(UTC).isoformat(),
        }
        record = {**metadata, "airfoil": airfoil}
        with self._lock:
            index = self._index()
            self._write_json(self.profile_root / f"{profile_id}.json", record)
            index["profiles"] = [
                row for row in index["profiles"] if row.get("profile_id") != profile_id
            ] + [metadata]
            self._write_json(self.index_path, index)
        return record
