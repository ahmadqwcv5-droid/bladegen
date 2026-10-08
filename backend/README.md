# BladeGen backend

This package owns the backend-neutral BladeSpec v0.2 model, canonical curve and
airfoil resolution, OpenVSP adapter, OCP solidification/validation, CLI, and
FastAPI service. It contains no imports from `00_research_archive`.

Run `bladegen build ../examples/x57_finite_te_multi_airfoil.json --output ../output/manual`
or `uvicorn api.main:app --app-dir backend` from the workspace root.
