from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routes import airfoils as airfoil_routes
from bladegen.airfoils.importers import import_airfoil
from bladegen.airfoils.library import AirfoilLibrary, canonical_coordinate_sha256

FIXTURES = Path(__file__).parent / "fixtures" / "airfoils"


@pytest.mark.parametrize(
    ("filename", "expected_format"),
    (
        ("independent_cambered_finite_te.dat", "dat-single-contour"),
        ("single_contour.csv", "csv-single-contour"),
        ("symmetric.csv", "csv-explicit-surfaces"),
    ),
)
def test_valid_dat_and_csv_imports_preserve_order_shape_and_checksums(
    filename: str, expected_format: str
) -> None:
    content = (FIXTURES / filename).read_bytes()
    result = import_airfoil(content, filename)
    assert result.import_format == expected_format
    assert result.original_sha256 == hashlib.sha256(content).hexdigest()
    assert result.airfoil.upper[0][0] == pytest.approx(0.0)
    assert result.airfoil.lower[0][0] == pytest.approx(0.0)
    assert result.airfoil.upper[-1][0] == pytest.approx(1.0)
    assert result.airfoil.lower[-1][0] == pytest.approx(1.0)
    assert all(
        right[0] > left[0] for left, right in zip(result.airfoil.upper, result.airfoil.upper[1:])
    )
    assert all(
        right[0] > left[0] for left, right in zip(result.airfoil.lower, result.airfoil.lower[1:])
    )
    digest = canonical_coordinate_sha256(result.airfoil.model_dump(mode="json"))
    assert digest == canonical_coordinate_sha256(result.airfoil.model_dump(mode="json"))


def test_independent_cambered_finite_te_metrics_are_geometric() -> None:
    result = import_airfoil(
        (FIXTURES / "independent_cambered_finite_te.dat").read_bytes(),
        "independent_cambered_finite_te.dat",
    )
    assert result.metrics.max_thickness_ratio == pytest.approx(0.11, abs=1e-12)
    assert result.metrics.max_thickness_x_over_c == pytest.approx(0.5, abs=1e-12)
    assert result.metrics.max_camber_ratio == pytest.approx(0.02, abs=1e-12)
    assert result.metrics.trailing_edge_gap_ratio == pytest.approx(0.01, abs=1e-12)
    assert result.airfoil.upper[2] == pytest.approx((0.5, 0.075))
    assert result.airfoil.lower[2] == pytest.approx((0.5, -0.035))


def test_symmetric_profile_reports_zero_camber() -> None:
    result = import_airfoil((FIXTURES / "symmetric.csv").read_bytes(), "symmetric.csv")
    assert result.metrics.max_thickness_ratio == pytest.approx(0.12, abs=1e-12)
    assert result.metrics.max_camber_ratio == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize(
    ("filename", "message"),
    (
        ("reversed.dat", "ordering"),
        ("degenerate.dat", "strictly ordered"),
        ("invalid_numeric.dat", "Non-finite"),
        ("missing_lower.csv", "three lower"),
        ("unsupported.txt", "Unsupported airfoil format"),
    ),
)
def test_invalid_imports_are_rejected_with_cause(filename: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        import_airfoil((FIXTURES / filename).read_bytes(), filename)


def test_empty_oversized_and_crossing_inputs_are_rejected() -> None:
    with pytest.raises(ValueError, match="empty"):
        import_airfoil(b"", "empty.dat")
    with pytest.raises(ValueError, match="safety limit"):
        import_airfoil(b"0" * 1_000_001, "large.dat")
    crossing = b"x,y,surface\n0,0,upper\n0.5,-.1,upper\n1,0,upper\n0,0,lower\n0.5,.1,lower\n1,0,lower\n"
    with pytest.raises(ValueError, match="cross"):
        import_airfoil(crossing, "crossing.csv")


def test_non_normalized_coordinates_require_explicit_normalization() -> None:
    content = b"Scaled\n100,1\n50,8\n0,0\n50,-3\n100,-1\n"
    with pytest.raises(ValueError, match="explicit normalization"):
        import_airfoil(content, "scaled.dat")
    result = import_airfoil(content, "scaled.dat", normalize=True)
    assert result.airfoil.upper[0] == pytest.approx((0.0, 0.0))
    assert result.airfoil.upper[-1][0] == pytest.approx(1.0)
    assert "divided by chord 100" in result.normalization


def test_registry_persists_metadata_and_exact_coordinates(tmp_path: Path) -> None:
    imported = import_airfoil(
        (FIXTURES / "independent_cambered_finite_te.dat").read_bytes(),
        "independent_cambered_finite_te.dat",
    )
    library = AirfoilLibrary(tmp_path / "airfoils")
    saved = library.add_imported(
        imported,
        display_name="Independent 11%",
        original_filename="../../unsafe/independent.dat",
        source="Test fixture definition",
    )
    assert saved["original_filename"] == "independent.dat"
    assert saved["license"] == "unknown"
    assert saved["metrics"]["max_thickness_ratio"] == pytest.approx(0.11)
    restarted = AirfoilLibrary(tmp_path / "airfoils")
    loaded = restarted.get(saved["profile_id"])
    assert loaded["airfoil"] == imported.airfoil.model_dump(mode="json")
    assert any(row["profile_id"] == saved["profile_id"] for row in restarted.catalog())


def test_real_api_import_catalog_and_profile(monkeypatch, tmp_path: Path) -> None:
    local = AirfoilLibrary(tmp_path / "airfoils")
    monkeypatch.setattr(airfoil_routes, "library", local)
    client = TestClient(app)
    content = (FIXTURES / "independent_cambered_finite_te.dat").read_bytes()
    response = client.post(
        "/api/airfoils/import",
        params={
            "filename": "independent.dat",
            "display_name": "Independent profile",
            "source": "Explicit test fixture",
        },
        content=content,
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code == 201, response.text
    imported = response.json()
    catalog = client.get("/api/airfoils/catalog").json()
    assert {"NACA 0012", "Independent profile"} <= {row["display_name"] for row in catalog}
    detail = client.get(f"/api/airfoils/{imported['profile_id']}")
    assert detail.status_code == 200
    assert detail.json()["canonical_coordinate_sha256"] == imported["canonical_coordinate_sha256"]

    invalid = client.post(
        "/api/airfoils/import",
        params={"filename": "bad.dat", "display_name": "Bad"},
        content=b"not coordinates",
    )
    assert invalid.status_code == 422
    assert len(local.catalog()) == len(catalog)
