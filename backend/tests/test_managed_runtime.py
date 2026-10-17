from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import sysconfig
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from api.services.jobs import Job, JobManager
from bladegen.runtime import manager as runtime


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_hash(value: dict) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(data.encode()).hexdigest()


def _runtime_root(tmp_path: Path, **overrides) -> tuple[Path, dict]:
    root = tmp_path / "runtime" / "opt" / "OpenVSP"
    relative_files = (
        "python/openvsp/openvsp/__init__.py",
        "python/openvsp/openvsp/_vsp.so",
    )
    for relative in relative_files:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"fixture:{relative}".encode())
    payload = {
        "schema": runtime.MANIFEST_SCHEMA,
        "build_id": runtime.EXPECTED_BUILD_ID,
        "construction_contract": runtime.CONSTRUCTION_CONTRACT,
        "capability": runtime.EXPECTED_CAPABILITY,
        "upstream_version": "3.54.0",
        "upstream_commit": runtime.EXPECTED_UPSTREAM_COMMIT,
        "patch_sha256": runtime.EXPECTED_PATCH_SHA256,
        "python_abi": f"{sys.version_info.major}.{sys.version_info.minor}",
        "python_soabi": sysconfig.get_config_var("SOABI"),
        "platform": {"system": platform.system(), "machine": platform.machine()},
        "artifacts": {relative: _sha256(root / relative) for relative in relative_files},
    }
    payload.update(overrides)
    payload["fingerprint"] = _canonical_hash(payload)
    (root / runtime.INSTALL_MANIFEST).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    return root, payload


def _successful_probe(root: Path, payload: dict, **overrides) -> SimpleNamespace:
    module_path = root / "python/openvsp/openvsp/__init__.py"
    native_path = root / "python/openvsp/openvsp/_vsp.so"
    response = {
        "build_id": runtime.EXPECTED_BUILD_ID,
        "construction_contract": runtime.CONSTRUCTION_CONTRACT,
        "capability": True,
        "openvsp_version": runtime.EXPECTED_NATIVE_VERSION,
        "python_module_path": str(module_path),
        "native_module_path": str(native_path),
        "python_module_sha256": payload["artifacts"]["python/openvsp/openvsp/__init__.py"],
        "native_module_sha256": payload["artifacts"]["python/openvsp/openvsp/_vsp.so"],
    }
    response.update(overrides)
    return SimpleNamespace(returncode=0, stdout=json.dumps(response), stderr="")


def test_runtime_probe_binds_native_identity_paths_and_hashes(monkeypatch, tmp_path):
    root, payload = _runtime_root(tmp_path)
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda *args, **kwargs: _successful_probe(root, payload),
    )
    identity = runtime.inspect_runtime(root)
    assert identity.build_id == runtime.EXPECTED_BUILD_ID
    assert identity.native_module_path == (root / "python/openvsp/openvsp/_vsp.so").resolve()
    assert identity.fingerprint == payload["fingerprint"]


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ({"build_id": "stock-openvsp"}, "build_id"),
        ({"construction_contract": "upstream"}, "construction_contract"),
        ({"capability": "wrong-capability"}, "capability"),
        ({"python_abi": "0.0"}, "python_abi"),
        ({"patch_sha256": "0" * 64}, "patch_sha256"),
    ],
)
def test_manifest_identity_mismatches_fail_closed(tmp_path, mutation, expected):
    root, _ = _runtime_root(tmp_path, **mutation)
    with pytest.raises(runtime.RuntimeReadinessError, match=expected):
        runtime.inspect_runtime(root, probe=False)


def test_missing_stock_partial_tampered_and_invalid_explicit_roots_fail(tmp_path):
    stock = tmp_path / "stock"
    stock.mkdir()
    with pytest.raises(runtime.RuntimeReadinessError, match="unmanaged or partial"):
        runtime.inspect_runtime(stock, probe=False)
    root, payload = _runtime_root(tmp_path / "tampered")
    (root / next(iter(payload["artifacts"]))).write_text("changed", encoding="utf-8")
    with pytest.raises(runtime.RuntimeReadinessError, match="tampered"):
        runtime.inspect_runtime(root, probe=False)
    with pytest.raises(runtime.RuntimeReadinessError, match="must be absolute"):
        runtime.inspect_runtime("relative/runtime", probe=False)


def test_native_capability_and_mixed_probe_are_rejected(monkeypatch, tmp_path):
    root, payload = _runtime_root(tmp_path)
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda *args, **kwargs: _successful_probe(root, payload, capability=False),
    )
    with pytest.raises(runtime.RuntimeReadinessError, match="capability"):
        runtime.inspect_runtime(root)
    outside = tmp_path / "outside.so"
    outside.write_bytes(b"not selected")
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda *args, **kwargs: _successful_probe(root, payload, native_module_path=str(outside)),
    )
    with pytest.raises(runtime.RuntimeReadinessError, match="outside selected runtime"):
        runtime.inspect_runtime(root)


def test_stale_fingerprint_and_already_imported_mixed_binding_fail(monkeypatch, tmp_path):
    root, _ = _runtime_root(tmp_path)
    with pytest.raises(runtime.RuntimeReadinessError, match="changed after readiness"):
        runtime.inspect_runtime(root, probe=False, expected_fingerprint="0" * 64)
    foreign = ModuleType("openvsp")
    foreign.__file__ = str(tmp_path / "foreign" / "openvsp" / "__init__.py")
    monkeypatch.setitem(sys.modules, "openvsp", foreign)
    with pytest.raises(runtime.RuntimeReadinessError, match="restart"):
        runtime._check_existing_imports(root)


def _job_identity(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        root=tmp_path / "runtime",
        fingerprint="f" * 64,
        build_id=runtime.EXPECTED_BUILD_ID,
        construction_contract=runtime.CONSTRUCTION_CONTRACT,
    )


def test_worker_rejects_changed_runtime_provenance(monkeypatch, tmp_path):
    manager = JobManager(run_root=tmp_path / "runs")
    identity = _job_identity(tmp_path)
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    input_path = job_dir / "blade_spec_input.json"
    input_path.write_text("{}", encoding="utf-8")
    job = Job(
        job_id="a" * 32,
        output_dir=job_dir,
        runtime_root=str(identity.root),
        runtime_fingerprint=identity.fingerprint,
        runtime_build_id=identity.build_id,
        runtime_contract=identity.construction_contract,
    )

    def completed(*args, **kwargs):
        for name in (
            "blade_solid.step",
            "blade_preview.stl",
            "validation.json",
        ):
            (job_dir / name).write_text("fresh", encoding="utf-8")
        (job_dir / "engine_manifest.json").write_text(
            json.dumps(
                {
                    "state": "COMPLETED",
                    "actually_loaded_runtime": {
                        "fingerprint": "changed",
                        "build_id": identity.build_id,
                        "construction_contract": identity.construction_contract,
                    },
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", completed)
    manager._run(job, input_path)
    manager._executor.shutdown(wait=False)
    assert job.status == "failed"
    assert "required artifact" in (job.error or "")


def test_worker_native_error_timeout_and_partial_output_never_succeed(monkeypatch, tmp_path):
    for mode in ("native_error", "timeout", "partial"):
        manager = JobManager(timeout_seconds=7, run_root=tmp_path / f"runs-{mode}")
        identity = _job_identity(tmp_path)
        job_dir = tmp_path / f"job-{mode}"
        job_dir.mkdir()
        input_path = job_dir / "blade_spec_input.json"
        input_path.write_text("{}", encoding="utf-8")
        job = Job(
            job_id=(mode[0] * 32),
            output_dir=job_dir,
            runtime_root=str(identity.root),
            runtime_fingerprint=identity.fingerprint,
            runtime_build_id=identity.build_id,
            runtime_contract=identity.construction_contract,
        )

        def run(*args, **kwargs):
            if mode == "timeout":
                raise subprocess.TimeoutExpired(args[0], 7, output="partial")
            if mode == "native_error":
                return SimpleNamespace(returncode=9, stdout="", stderr="native failure")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", run)
        manager._run(job, input_path)
        manager._executor.shutdown(wait=False)
        assert job.status == "failed"
