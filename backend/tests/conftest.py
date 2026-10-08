from __future__ import annotations

from pathlib import Path

import pytest

from bladegen.pipeline import build

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = WORKSPACE_ROOT / "examples/x57_finite_te_multi_airfoil.json"


@pytest.fixture(scope="session")
def built_x57(tmp_path_factory):
    pytest.importorskip("openvsp")
    output = tmp_path_factory.mktemp("bladegen_x57")
    return build(SPEC_PATH, output)
