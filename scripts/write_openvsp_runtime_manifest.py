#!/usr/bin/env python3
"""Create the self-verifying manifest for a staged fixed-plane runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import sysconfig
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value: object) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def command_version(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    lines = [line.strip() for line in (result.stdout + result.stderr).splitlines()]
    return next(line for line in lines if line)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--patch", type=Path, required=True)
    parser.add_argument("--build-log", type=Path, required=True)
    parser.add_argument("--compiler", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    relative_artifacts = [
        "LICENSE",
        "python/openvsp/openvsp/__init__.py",
        "python/openvsp/openvsp/vsp.py",
        "python/openvsp/openvsp/_vsp.so",
        "python/openvsp_config/openvsp_config/__init__.py",
        "share/bladegen/upstream.lock.json",
        "share/bladegen/0001-bladegen-fixed-radial-sections.patch",
        "share/bladegen/build.log",
    ]
    missing = [
        relative for relative in relative_artifacts if not (root / relative).is_file()
    ]
    if missing:
        raise SystemExit(f"Staged runtime is incomplete; missing: {missing}")
    build = lock["build"]
    upstream = lock["upstream"]
    payload = {
        "schema": "bladegen.openvsp-runtime.v1",
        "build_id": build["id"],
        "construction_contract": build["contract"],
        "capability": build["capability"],
        "upstream_version": upstream["version"],
        "upstream_commit": upstream["commit"],
        "source_repository": upstream["repository"],
        "source_archive_sha256": upstream["archive"]["sha256"],
        "source_archive_size_bytes": upstream["archive"]["size_bytes"],
        "dependency_identity": lock["dependency_identity"],
        "patch_sha256": sha256(args.patch),
        "python_abi": f"{sys.version_info.major}.{sys.version_info.minor}",
        "python_soabi": sysconfig.get_config_var("SOABI"),
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "libc": list(platform.libc_ver()),
        },
        "toolchain": {
            "compiler": command_version([args.compiler, "--version"]),
            "cmake": command_version(["cmake", "--version"]),
            "swig": command_version(["swig", "-version"]),
            "python": platform.python_version(),
        },
        "cmake_options": build["cmake_options"],
        "artifacts": {
            relative: sha256(root / relative) for relative in relative_artifacts
        },
    }
    payload["fingerprint"] = canonical_hash(payload)
    output = root / "bladegen-runtime-manifest.json"
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
