# Architecture

```text
Local airfoil registry ── catalog/import ─┐
                                         v
React editor ── BladeSpec v0.2 ── FastAPI design preview
     │                                   │
     │                     canonical airfoils + SciPy curves
     │                                   │
     └── Generate ── single-worker queue ─┴─ isolated Python subprocess
                                                │
          BladeSpec → canonical resolver → OpenVSP PROP/STEP faces
                                                │
                                        OCP sew/make solid
                                                │
                                   qualify → STEP + STL + JSON
```

Full-propeller generation is a separate operation over the same validated
blade service:

```text
PropellerSpec v0.1
  ├── complete BladeSpec v0.2 ── existing blade pipeline (one invocation)
  └── AssemblySpec                    │
                                      v
                         validated blade_solid.step
                                      │ exact OCP copies/rotations
                                      v
                    X-axis hub union → X-axis bore cut
                                      │
                                      v
                    propeller STEP round-trip qualification
```

`bladegen.assembly` owns placement, primitives, Boolean operations, collision
checks, bore measurement, and topology qualification. It has no React or
FastAPI dependency. `bladegen.propeller_pipeline.build_propeller()` is the
reusable application boundary; the `build-propeller` CLI and FastAPI job layer
both call it. Blade and propeller requests share the same one-worker queue, so
OpenVSP is never driven by independent concurrent queues. Only the reference
blade invokes OpenVSP; all additional blades use exact OCP transforms.

`backend/bladegen/models` is the neutral contract. `curves` and `airfoils` own
product mathematics; `adapters` is the only OpenVSP translation boundary;
`solid` and `validation` make OCP authoritative for topology and measurements.
The API accepts no filesystem paths, generates UUID job directories, allows one
active CAD subprocess, applies a configurable timeout (`BLADEGEN_BUILD_TIMEOUT`,
default 300 s), and serves only allow-listed artifacts. No product module imports
from `00_research_archive`.

The transport boundary remains replaceable: a future desktop shell may retain
React plus the local API or call the Python engine through another supported
application layer. Sprint 04A does not select a desktop framework. OpenVSP
runtime discovery remains configurable through `OPENVSP_ROOT`; the current
installation/launch scripts are Linux-specific and other platforms still need
separate packaging and qualification.

The file-backed Airfoil Library lives outside BladeSpec. Parametric NACA entries
call the canonical generator; imported DAT/CSV profiles are validated into the
existing neutral coordinate representation and stored atomically under
`user_data/airfoils` (or `BLADEGEN_AIRFOIL_LIBRARY`). Selecting one copies exact
coordinates into BladeSpec, so CAD rebuilds never depend on registry state.

The design-preview API is a non-CAD read model over the canonical Python source
of truth. It returns resolved source/finite-TE contours and SciPy-evaluated
distribution samples in engineering display units. React debounces and cancels
requests and rejects stale revisions. It does not duplicate NACA or PCHIP
mathematics and never starts OpenVSP or writes STEP/STL artifacts.

The React editor owns only transient row identities, profile display names, and
numeric input drafts; serialized projects remain pure BladeSpec v0.2. At
submission it freezes a canonical JSON snapshot and binds artifacts to the
returned job ID. Comparing the live editor with that snapshot drives the stale-
preview state, and an older poll response cannot replace a newer active job.

Final-CAD stations are planned from each submitted BladeSpec: explicit airfoil
stations, adjacent profile-morphing midpoints, and the union of independent
curve controls. Root and tip use recorded inward cuts derived from the actual
domain and adjacent spacing. OpenVSP's `AFLimit` is not treated as the product
root because version 3.54.0 clamps it at 0.20; the first XSec `RadiusFrac` is
the authoritative geometric root.
