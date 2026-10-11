# Airfoil library

BladeGen's library is a backend-neutral convenience layer. It never changes the
BladeSpec v0.2 contract and is not consulted during CAD generation.

## Profile categories

- **Parametric NACA 4-digit** profiles are generated on demand by
  `bladegen.airfoils.canonical.naca_4digit_coordinates`. The catalog starts with
  0008, 0010, 0012, 2412, 4412, and 4415. Any mathematically supported four-digit
  code can be entered directly.
- **Imported coordinates** come from a validated DAT or CSV upload. The exact
  normalized upper/lower coordinate arrays are stored with metadata and are
  embedded in BladeSpec when selected.

The selector searches names, filters NACA/imported categories, previews
canonical geometry and measurements, and applies only after explicit user
confirmation. Cancel never modifies the active project.

## Local persistence

Mutable application data defaults to:

```text
user_data/airfoils/
├── index.json
└── profiles/<profile-id>.json
```

The directory is Git-ignored. Set `BLADEGEN_AIRFOIL_LIBRARY` to use another
local directory. Writes use a temporary sibling followed by `os.replace`, so a
process never publishes a partial index or profile record.

Imported metadata includes display name, original safe filename, source,
license, notes, format, original-file SHA-256, canonical-coordinate SHA-256,
point counts, normalization policy, geometric thickness/camber, and creation
time. Missing source or licensing stays explicitly `unknown`; BladeGen does not
infer redistribution rights.

## Reproducibility boundary

Library metadata and project geometry are intentionally separate. Applying an
imported profile copies its exact neutral coordinates into the station's
BladeSpec definition. Exported projects therefore rebuild without the registry
or original upload. Changing a library record cannot mutate an existing saved
BladeSpec.

Coordinate profile selection also coordinates the active station's
`thickness_distribution` control to measured natural maximum t/c. Other
thickness controls and physical trailing-edge millimeter requirements remain
unchanged. The canonical resolver rejects hand-authored coordinate BladeSpecs
whose active t/c contradicts the profile geometry; this prevents OpenVSP
`PROP_THICK` from silently rescaling a profile relative to its 2D preview.

## API

```text
GET  /api/airfoils/catalog
GET  /api/airfoils/{profile_id}
POST /api/airfoils/import
POST /api/design-preview
```

The import request body is the bounded file content. Filename and metadata are
query fields; the server never accepts a client filesystem destination.
`/api/design-preview` accepts the current BladeSpec, calls the same canonical
airfoil resolver and SciPy curve evaluator used before OpenVSP, and creates no
STEP, STL, or CAD subprocess.
