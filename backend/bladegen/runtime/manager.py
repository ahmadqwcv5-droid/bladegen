"""Fail-closed selection of BladeGen's managed OpenVSP build flavor."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import platform
import subprocess
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

EXPECTED_BUILD_ID = "openvsp-3.54.0-bladegen-fixed-plane.1"
CONSTRUCTION_CONTRACT = "bladegen.fixed-radial-sections.v1"
EXPECTED_CAPABILITY = "fixed_radial_sections_v1"
EXPECTED_NATIVE_VERSION = "OpenVSP 3.54.0"
EXPECTED_UPSTREAM_COMMIT = "db6c6fe8f4eca27d7517f4ae0b2078abdd3fd927"
EXPECTED_PATCH_SHA256 = "0dd6f87b867ccaeb6518f8f01f7093e4e1a05f02d0c5a268c66cc1d157ed71d3"
INSTALL_MANIFEST = "bladegen-runtime-manifest.json"
MANIFEST_SCHEMA = "bladegen.openvsp-runtime.v1"
WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUNTIME_ROOT = WORKSPACE_ROOT / ".tooling" / EXPECTED_BUILD_ID / "opt" / "OpenVSP"
PROBE_TIMEOUT_SECONDS = 30


class RuntimeReadinessError(RuntimeError):
    """The selected CAD engine cannot satisfy the fixed-plane contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def python_package_paths(root: Path) -> tuple[Path, ...]:
    python_root = root / "python"
    return tuple(
        python_root / child for child in ("openvsp", "openvsp_config", "degen_geom", "utilities")
    )


@dataclass(frozen=True)
class RuntimeIdentity:
    root: Path
    selection: str
    build_id: str
    construction_contract: str
    capability: str
    upstream_version: str
    upstream_commit: str
    patch_sha256: str
    fingerprint: str
    manifest_path: Path
    artifact_hashes: dict[str, str]
    python_module_path: Path | None = None
    native_module_path: Path | None = None
    openvsp_version: str | None = None

    def safe_dict(self) -> dict[str, Any]:
        return {
            "build_id": self.build_id,
            "construction_contract": self.construction_contract,
            "capability": self.capability,
            "upstream_version": self.upstream_version,
            "upstream_commit": self.upstream_commit,
            "patch_sha256": self.patch_sha256,
            "fingerprint": self.fingerprint,
            "openvsp_version": self.openvsp_version,
        }

    def private_dict(self) -> dict[str, Any]:
        payload = self.safe_dict()
        payload.update(
            {
                "selection": self.selection,
                "root": str(self.root),
                "manifest_path": str(self.manifest_path),
                "python_module_path": (
                    str(self.python_module_path) if self.python_module_path else None
                ),
                "native_module_path": (
                    str(self.native_module_path) if self.native_module_path else None
                ),
                "artifact_hashes": dict(self.artifact_hashes),
            }
        )
        return payload


def selected_runtime_root(explicit_root: str | Path | None = None) -> tuple[Path, str]:
    if explicit_root is not None:
        raw = str(explicit_root)
        selection = "explicit_argument"
    elif "OPENVSP_ROOT" in os.environ:
        raw = os.environ["OPENVSP_ROOT"]
        selection = "OPENVSP_ROOT"
    else:
        raw = str(DEFAULT_RUNTIME_ROOT)
        selection = "managed_default"
    if not raw.strip():
        raise RuntimeReadinessError("OPENVSP_ROOT is set but empty; no fallback is permitted.")
    root = Path(raw).expanduser()
    if not root.is_absolute():
        raise RuntimeReadinessError(f"Selected OpenVSP root must be absolute: {root}")
    return root.resolve(), selection


def _read_manifest(root: Path, selection: str) -> tuple[dict[str, Any], Path]:
    manifest_path = root / INSTALL_MANIFEST
    if not root.is_dir():
        raise RuntimeReadinessError(
            f"Compatible OpenVSP runtime not found at {root}. "
            "Run ./scripts/setup_openvsp_fixed_plane.sh."
        )
    if not manifest_path.is_file():
        raise RuntimeReadinessError(
            f"Selected OpenVSP root is unmanaged or partial ({selection}): missing "
            f"{INSTALL_MANIFEST}. Run ./scripts/setup_openvsp_fixed_plane.sh."
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeReadinessError(f"Invalid runtime manifest at {manifest_path}: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != MANIFEST_SCHEMA:
        raise RuntimeReadinessError("Unsupported managed runtime manifest schema.")
    return manifest, manifest_path


def _validate_manifest(root: Path, selection: str) -> RuntimeIdentity:
    manifest, manifest_path = _read_manifest(root, selection)
    expected = {
        "build_id": EXPECTED_BUILD_ID,
        "construction_contract": CONSTRUCTION_CONTRACT,
        "capability": EXPECTED_CAPABILITY,
        "upstream_version": "3.54.0",
        "upstream_commit": EXPECTED_UPSTREAM_COMMIT,
        "patch_sha256": EXPECTED_PATCH_SHA256,
    }
    mismatches = [
        f"{key}={manifest.get(key)!r} (expected {value!r})"
        for key, value in expected.items()
        if manifest.get(key) != value
    ]
    runtime_platform = manifest.get("platform") or {}
    if runtime_platform.get("system") != platform.system():
        mismatches.append(
            f"platform.system={runtime_platform.get('system')!r} (expected {platform.system()!r})"
        )
    if runtime_platform.get("machine") != platform.machine():
        mismatches.append(
            f"platform.machine={runtime_platform.get('machine')!r} "
            f"(expected {platform.machine()!r})"
        )
    expected_soabi = sysconfig.get_config_var("SOABI")
    if manifest.get("python_soabi") != expected_soabi:
        mismatches.append(
            f"python_soabi={manifest.get('python_soabi')!r} (expected {expected_soabi!r})"
        )
    python_abi = manifest.get("python_abi")
    expected_abi = f"{sys.version_info.major}.{sys.version_info.minor}"
    if python_abi != expected_abi:
        mismatches.append(f"python_abi={python_abi!r} (expected {expected_abi!r})")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        mismatches.append("artifacts must be a non-empty path-to-SHA256 mapping")
        artifacts = {}
    fingerprint_payload = {key: value for key, value in manifest.items() if key != "fingerprint"}
    fingerprint = _canonical_hash(fingerprint_payload)
    if manifest.get("fingerprint") != fingerprint:
        mismatches.append("manifest fingerprint does not match its contents")
    for relative, expected_hash in artifacts.items():
        relative_path = Path(relative)
        path = (root / relative_path).resolve()
        if relative_path.is_absolute() or not _within(path, root):
            mismatches.append(f"unsafe artifact path: {relative}")
            continue
        if not path.is_file():
            mismatches.append(f"missing runtime artifact: {relative}")
            continue
        actual_hash = _sha256(path)
        if actual_hash != expected_hash:
            mismatches.append(f"tampered runtime artifact: {relative}")
    if mismatches:
        raise RuntimeReadinessError(
            "Incompatible managed OpenVSP runtime: " + "; ".join(mismatches)
        )
    return RuntimeIdentity(
        root=root,
        selection=selection,
        build_id=manifest["build_id"],
        construction_contract=manifest["construction_contract"],
        capability=manifest["capability"],
        upstream_version=manifest["upstream_version"],
        upstream_commit=manifest["upstream_commit"],
        patch_sha256=manifest["patch_sha256"],
        fingerprint=fingerprint,
        manifest_path=manifest_path,
        artifact_hashes=dict(artifacts),
    )


def _probe_runtime(identity: RuntimeIdentity, timeout_seconds: int) -> RuntimeIdentity:
    command = [
        sys.executable,
        "-m",
        "bladegen.runtime.probe",
        "--root",
        str(identity.root),
    ]
    env = os.environ.copy()
    env["PYTHONNOUSERSITE"] = "1"
    env.pop("OPENVSP_ROOT", None)
    try:
        result = subprocess.run(
            command,
            cwd=WORKSPACE_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeReadinessError(
            f"OpenVSP readiness probe timed out after {timeout_seconds} seconds."
        ) from exc
    if result.returncode:
        detail = (result.stderr or result.stdout or "probe failed").strip()[-2000:]
        raise RuntimeReadinessError(f"OpenVSP readiness probe failed: {detail}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeReadinessError("OpenVSP readiness probe returned invalid JSON.") from exc
    expected = {
        "build_id": identity.build_id,
        "construction_contract": identity.construction_contract,
        "capability": True,
        "openvsp_version": EXPECTED_NATIVE_VERSION,
    }
    mismatch = [
        f"{key}={payload.get(key)!r} (expected {value!r})"
        for key, value in expected.items()
        if payload.get(key) != value
    ]
    module_path = Path(payload.get("python_module_path", "")).resolve()
    native_path = Path(payload.get("native_module_path", "")).resolve()
    for label, path in (("Python module", module_path), ("native module", native_path)):
        if not path.is_file() or not _within(path, identity.root):
            mismatch.append(f"{label} resolved outside selected runtime: {path}")
    if mismatch:
        raise RuntimeReadinessError("Mixed or incompatible OpenVSP binding: " + "; ".join(mismatch))
    expected_module_hash = identity.artifact_hashes.get(str(module_path.relative_to(identity.root)))
    expected_native_hash = identity.artifact_hashes.get(str(native_path.relative_to(identity.root)))
    if expected_module_hash != payload.get("python_module_sha256"):
        mismatch.append("Python module hash is not bound by the installed manifest")
    if expected_native_hash != payload.get("native_module_sha256"):
        mismatch.append("native module hash is not bound by the installed manifest")
    if mismatch:
        raise RuntimeReadinessError("Mixed or changed OpenVSP binding: " + "; ".join(mismatch))
    return RuntimeIdentity(
        **{
            **identity.__dict__,
            "python_module_path": module_path,
            "native_module_path": native_path,
            "openvsp_version": payload.get("openvsp_version"),
        }
    )


def inspect_runtime(
    explicit_root: str | Path | None = None,
    *,
    probe: bool = True,
    timeout_seconds: int = PROBE_TIMEOUT_SECONDS,
    expected_fingerprint: str | None = None,
) -> RuntimeIdentity:
    root, selection = selected_runtime_root(explicit_root)
    identity = _validate_manifest(root, selection)
    if expected_fingerprint and identity.fingerprint != expected_fingerprint:
        raise RuntimeReadinessError(
            "Selected runtime changed after readiness was established; submit the build again."
        )
    return _probe_runtime(identity, timeout_seconds) if probe else identity


def require_runtime_ready(
    explicit_root: str | Path | None = None,
    *,
    expected_fingerprint: str | None = None,
) -> RuntimeIdentity:
    return inspect_runtime(
        explicit_root,
        probe=True,
        expected_fingerprint=expected_fingerprint,
    )


def _check_existing_imports(root: Path) -> None:
    imported = [
        module
        for name, module in sys.modules.items()
        if (name == "openvsp" or name.startswith("openvsp.")) and module is not None
    ]
    paths = [
        Path(path).resolve() for module in imported if (path := getattr(module, "__file__", None))
    ]
    if any(not _within(path, root) for path in paths):
        raise RuntimeReadinessError(
            "A different OpenVSP native package is already imported; restart this CAD worker."
        )


def load_openvsp_runtime(
    *, expected_fingerprint: str | None = None
) -> tuple[ModuleType, RuntimeIdentity]:
    identity = inspect_runtime(probe=False, expected_fingerprint=expected_fingerprint)
    _check_existing_imports(identity.root)
    for path in reversed(python_package_paths(identity.root)):
        value = str(path)
        if value not in sys.path:
            sys.path.insert(0, value)
    openvsp_config = importlib.import_module("openvsp_config")
    config_path = Path(openvsp_config.__file__).resolve()
    if not _within(config_path, identity.root):
        raise RuntimeReadinessError(
            f"Mixed OpenVSP configuration package loaded from {config_path}; restart the worker."
        )
    openvsp_config.LOAD_GRAPHICS = False
    vsp = importlib.import_module("openvsp")
    native = importlib.import_module("openvsp._vsp")
    module_path = Path(vsp.__file__).resolve()
    native_path = Path(native.__file__).resolve()
    if not _within(module_path, identity.root) or not _within(native_path, identity.root):
        raise RuntimeReadinessError(
            "OpenVSP Python/native module paths do not share the selected root."
        )
    openvsp_version = vsp.GetVSPVersion()
    build_id = vsp.GetBladeGenBuildID()
    contract = vsp.GetBladeGenConstructionContract()
    capability = bool(vsp.HasBladeGenFixedRadialSectionsV1())
    if (build_id, contract, capability, openvsp_version) != (
        EXPECTED_BUILD_ID,
        CONSTRUCTION_CONTRACT,
        True,
        EXPECTED_NATIVE_VERSION,
    ):
        raise RuntimeReadinessError(
            f"Loaded native engine is incompatible: build={build_id!r}, "
            f"contract={contract!r}, capability={capability!r}, "
            f"version={openvsp_version!r}."
        )
    for path in (module_path, native_path):
        relative = str(path.relative_to(identity.root))
        if identity.artifact_hashes.get(relative) != _sha256(path):
            raise RuntimeReadinessError(f"Loaded module is changed or unbound: {relative}")
    loaded = RuntimeIdentity(
        **{
            **identity.__dict__,
            "python_module_path": module_path,
            "native_module_path": native_path,
            "openvsp_version": openvsp_version,
        }
    )
    return vsp, loaded
