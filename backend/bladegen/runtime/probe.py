"""Fresh-process native binding probe. Do not import this in FastAPI request code."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from pathlib import Path

from .manager import python_package_paths


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    for path in reversed(python_package_paths(root)):
        sys.path.insert(0, str(path))
    config = importlib.import_module("openvsp_config")
    config.LOAD_GRAPHICS = False
    vsp = importlib.import_module("openvsp")
    native = importlib.import_module("openvsp._vsp")
    module_path = Path(vsp.__file__).resolve()
    native_path = Path(native.__file__).resolve()
    payload = {
        "build_id": vsp.GetBladeGenBuildID(),
        "construction_contract": vsp.GetBladeGenConstructionContract(),
        "capability": bool(vsp.HasBladeGenFixedRadialSectionsV1()),
        "openvsp_version": vsp.GetVSPVersion(),
        "python_module_path": str(module_path),
        "native_module_path": str(native_path),
        "python_module_sha256": _sha256(module_path),
        "native_module_sha256": _sha256(native_path),
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
