# BladeGen Level 1 Alpha

BladeGen turns a backend-neutral BladeSpec v0.2 JSON document into one validated
blade solid. The real pipeline is BladeSpec → canonical resolution → headless
OpenVSP → OCP sewing/solidification → STEP re-import qualification. The browser
app edits the specification, submits a serialized build job, previews the OCP-
derived STL, and downloads STEP and validation artifacts.

## Supported scope

- One blade; NACA 4-digit or coordinate profiles.
- Independent chord, twist, rake, skew, and thickness station grids.
- Physical finite trailing-edge thickness with measured tolerance reporting.
- One valid closed STEP solid, OCP preview STL, and machine-readable validation.

Not yet included: multi-blade assemblies, manufacturing hubs, aero analysis,
optimization, VSPAERO, authentication, or cloud execution.

## Prerequisites and installation

The tested machine uses Python 3.12, the uv package manager, OpenVSP 3.54.0's official Linux Python
API, cadquery-ocp/OpenCascade 7.9.3.1, Node 24.14.0, and npm 11.9.0.

```bash
./scripts/setup_backend.sh
cd frontend && npm install && cd ..
```

Set `OPENVSP_ROOT` to the unpacked official OpenVSP distribution. The scripts
also detect this machine.s `/tmp/openvsp_root/opt/OpenVSP` installation.

## Run

In separate terminals:

```bash
./scripts/start_backend.sh
./scripts/start_frontend.sh
```

Open `http://127.0.0.1:5173`. Build jobs are serialized and isolated in child
processes. Outputs live under `output/runs/<job_id>/`.

CLI build:

```bash
OPENVSP_ROOT=/tmp/openvsp_root/opt/OpenVSP LD_LIBRARY_PATH=/tmp/cminpack_root/usr/lib/x86_64-linux-gnu .venv/bin/bladegen build \
  examples/x57_finite_te_multi_airfoil.json --output output/manual
```

Tests and production UI build:

```bash
./scripts/test_backend.sh
cd frontend && npm run build
```

## Limitations and licensing

OpenVSP is distributed under the NASA Open Source Agreement; OpenCascade uses
LGPL-2.1 with its additional exception. NumPy/SciPy are BSD-family, Pydantic,
FastAPI, React, Three.js, and Vite are MIT-licensed. This is dependency
awareness, not legal advice; redistribution rights, including NASA OSA terms,
must be reviewed for the intended distribution. No PropGen or other third-party
application source was copied.

See [architecture](docs/ARCHITECTURE.md), [geometry conventions](docs/GEOMETRY_CONVENTIONS.md),
and [validation policy](docs/VALIDATION_POLICY.md).
