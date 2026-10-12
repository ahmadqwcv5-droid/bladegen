from __future__ import annotations

import json
import sys

from bladegen import cli


def test_build_propeller_cli_uses_separate_engine_command(monkeypatch, capsys, tmp_path):
    spec_path = tmp_path / "propeller.json"
    output_path = tmp_path / "result"
    progress_path = tmp_path / "progress.json"
    spec_path.write_text("{}\n", encoding="utf-8")
    calls = []

    def fake_build(spec, output, progress):
        calls.append((spec, output, progress))
        return {
            "status": "PASS",
            "assembly_validation": {"passed": True, "final_after_reimport": {"solids": 1}},
            "outputs": {"propeller_solid_step": str(output / "propeller_solid.step")},
        }

    monkeypatch.setattr(cli, "build_propeller", fake_build)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "bladegen",
            "build-propeller",
            str(spec_path),
            "--output",
            str(output_path),
            "--progress-file",
            str(progress_path),
        ],
    )
    assert cli.main() == 0
    assert calls == [(spec_path, output_path, progress_path)]
    summary = json.loads(capsys.readouterr().out)
    assert summary["build_type"] == "propeller"
    assert summary["solid"]["solids"] == 1


def test_build_propeller_cli_returns_failure_exit_code(monkeypatch, tmp_path):
    spec_path = tmp_path / "propeller.json"
    spec_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        cli,
        "build_propeller",
        lambda *_: {
            "status": "FAIL",
            "assembly_validation": {"passed": False, "final_after_reimport": {}},
            "outputs": {},
        },
    )
    monkeypatch.setattr(sys, "argv", ["bladegen", "build-propeller", str(spec_path)])
    assert cli.main() == 1
