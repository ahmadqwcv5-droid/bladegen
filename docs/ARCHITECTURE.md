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

The React editor owns only transient row identities and numeric input drafts;
serialized projects remain pure BladeSpec v0.2. At submission it freezes a
canonical JSON snapshot and binds artifacts to the returned job ID. Comparing
the live editor with that snapshot drives the stale-preview state, and an older
poll response cannot replace a newer active job.

Final-CAD stations are planned from each submitted BladeSpec: explicit airfoil
stations, adjacent profile-morphing midpoints, and the union of independent
curve controls. Root and tip use recorded inward cuts derived from the actual
domain and adjacent spacing. OpenVSP's `AFLimit` is not treated as the product
root because version 3.54.0 clamps it at 0.20; the first XSec `RadiusFrac` is
the authoritative geometric root.
