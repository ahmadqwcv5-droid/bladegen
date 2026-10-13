#!/usr/bin/env python3
"""Measure the Sprint 04B validation plus canonical-preview request budget."""

from __future__ import annotations

import json
import platform
import statistics
import time

import numpy as np
from fastapi.testclient import TestClient

from benchmark_curve_resolution import synthetic_spec

from api.main import app


def percentile95(values: list[float]) -> float:
    return float(np.percentile(np.asarray(values), 95, method="linear"))


def measure(client: TestClient, payload: dict, repetitions: int = 20) -> dict:
    def operation() -> None:
        validation = client.post("/api/validate", json=payload)
        preview = client.post("/api/design-preview", json=payload)
        if validation.status_code != 200 or preview.status_code != 200:
            raise RuntimeError(
                f"validation={validation.status_code}, preview={preview.status_code}"
            )

    started = time.perf_counter()
    operation()
    cold = time.perf_counter() - started
    warm = []
    for _ in range(repetitions):
        started = time.perf_counter()
        operation()
        warm.append(time.perf_counter() - started)
    return {
        "cold_first_seconds": cold,
        "warm_repetitions": repetitions,
        "warm_median_seconds": statistics.median(warm),
        "warm_p95_seconds": percentile95(warm),
        "warm_max_seconds": max(warm),
        "requests_per_operation": {
            "validate": 1,
            "design_preview": 1,
            "cad_build": 0,
        },
        "pchip_constructors_per_operation": 10,
    }


def main() -> None:
    with TestClient(app) as client:
        result = {
            "machine": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "numpy": np.__version__,
            },
            "cases": {
                str(count): measure(
                    client,
                    synthetic_spec(count).model_dump(mode="json"),
                )
                for count in (40, 200)
            },
        }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
