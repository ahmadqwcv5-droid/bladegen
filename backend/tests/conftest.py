from __future__ import annotations

from pathlib import Path

import pytest

from bladegen.pipeline import build

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = WORKSPACE_ROOT / "examples/custom_multi_airfoil_finite_te.json"


@pytest.fixture(scope="session")
def built_blade(tmp_path_factory):
    pytest.importorskip("openvsp")
    output = tmp_path_factory.mktemp("bladegen_build")
    return build(SPEC_PATH, output)
