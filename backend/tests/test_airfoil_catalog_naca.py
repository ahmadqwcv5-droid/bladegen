from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_direct_naca_catalog_supports_valid_codes_and_rejects_unsupported_math() -> None:
    valid = client.get("/api/airfoils/naca-2309")
    assert valid.status_code == 200
    assert valid.json()["airfoil"] == {"type": "naca4", "code": "2309"}

    invalid = client.get("/api/airfoils/naca-1012")
    assert invalid.status_code == 422
    assert "requires a nonzero camber position" in invalid.text
