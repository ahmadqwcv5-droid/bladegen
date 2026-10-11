# Supported airfoil import formats

Airfoil uploads must be UTF-8 text, at most 1,000,000 bytes and 4,000 coordinate
points. File extensions are deterministic: `.dat` selects DAT parsing and
`.csv` selects CSV parsing. Other extensions are rejected.

## DAT single contour

One optional nonnumeric title line may precede rows containing exactly `x y`:

```text
Example finite-TE profile
1.0  0.005
0.5  0.060
0.0  0.000
0.5 -0.040
1.0 -0.005
```

The required order is trailing-edge upper → leading edge → trailing-edge lower.
The importer finds one unambiguous interior minimum-x leading edge, reverses the
upper branch, and emits both surfaces leading-edge to trailing-edge. Lower-first,
duplicate-x, or ambiguous layouts are rejected rather than guessed.

## CSV single contour

CSV requires an `x,y` header and uses the same contour order:

```csv
x,y
1.0,0.005
0.5,0.060
0.0,0.000
0.5,-0.040
1.0,-0.005
```

## CSV explicit surfaces

An optional `surface` column may label every row `upper` or `lower`. Each group
must contain at least three points. Either direction is accepted per group and
is deterministically converted to leading-edge-to-trailing-edge order.

```csv
x,y,surface
0.0,0.0,upper
0.5,0.06,upper
1.0,0.0,upper
0.0,0.0,lower
0.5,-0.04,lower
1.0,0.0,lower
```

## Normalization policy

Coordinates already within 0.01 chord of the standard LE≈0, mean TE≈1 unit
domain are preserved exactly, including legitimate small negative x/c values.
No clamping, smoothing, refitting, or implicit resampling occurs.

Other scales are rejected unless **Explicitly normalize** is selected. Explicit
normalization translates the mean LE to the origin and divides x and y by the
positive mean-TE chord. The exact transformation is recorded in library
metadata and previewed before application.

## Rejected input

BladeGen rejects empty/oversized files, non-UTF-8 content, NaN/infinity,
unsupported rows or extensions, missing surfaces, fewer than three points per
surface, duplicate/degenerate chordwise ordering, ambiguous leading edges,
crossing upper/lower surfaces, and non-unit coordinates without explicit
normalization. An import error leaves the active BladeSpec and selected station
unchanged.

Historical multi-block formats, Lednicer two-table DAT variants, automatic
database downloads, and heuristic recovery of malformed contours are outside
Sprint 03A.
