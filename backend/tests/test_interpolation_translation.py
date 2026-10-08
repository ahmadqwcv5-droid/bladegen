from types import SimpleNamespace

import pytest

from bladegen.adapters.openvsp_adapter import interpolation_name

FAKE_VSP = SimpleNamespace(LINEAR=17, PCHIP=29)


def test_resolved_adapter_accepts_only_linear_readback():
    assert interpolation_name(17, FAKE_VSP) == "linear"
    with pytest.raises(RuntimeError):
        interpolation_name(29, FAKE_VSP)


def test_unknown_backend_interpolation_is_rejected():
    with pytest.raises(RuntimeError):
        interpolation_name(99, FAKE_VSP)
