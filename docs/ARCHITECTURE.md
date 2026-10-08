# Architecture

```text
React editor/viewer
       │ HTTP BladeSpec v0.2
FastAPI ── single-worker queue ── isolated Python subprocess
                                      │
BladeSpec → canonical resolver → OpenVSP PROP/STEP faces
                                      │
                              OCP sew/make solid
                                      │
                         qualify → STEP + STL + JSON
```

`backend/bladegen/models` is the neutral contract. `curves` and `airfoils` own
product mathematics; `adapters` is the only OpenVSP translation boundary;
`solid` and `validation` make OCP authoritative for topology and measurements.
The API accepts no filesystem paths, generates UUID job directories, allows one
active CAD subprocess, applies a configurable timeout (`BLADEGEN_BUILD_TIMEOUT`,
default 300 s), and serves only allow-listed artifacts. No product module imports
from `00_research_archive`.

Future airfoil-library adapters can provide parametric families, named profiles,
or imported DAT/CSV coordinates with metadata/provenance while still resolving
to the current neutral coordinate representation.
