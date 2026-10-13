# Bulk engineering input formats

Sprint 04B adds reviewed bulk input for blade distributions and airfoil-station
placement. Bulk input is an engineering edit: it does not choose a profile,
distribution, or station count for the user, and it never starts CAD generation.

## Distribution CSV and spreadsheet paste

Open **Import Distributions**. Either choose a UTF-8 CSV file or paste a
rectangular tab-separated block copied from a spreadsheet. A UTF-8 byte-order
mark is accepted. Blank lines are ignored; quoted CSV cells and doubled quotes
are supported. The safety limit is 5,000 data rows.

Version 1 requires a normalized radial column named `r_over_R`. Its values must
be finite, strictly increasing, unique, within `[0, 1]`, and span the current
project root through exactly `1`. The importer explains a root/tip mismatch; it
does not move the project root or extrapolate missing endpoints.

Recognized value columns are:

| Header | Distribution | Input unit | Stored value |
| --- | --- | --- | --- |
| `chord_mm` | Chord | mm | value / `(diameter_mm / 2)` |
| `chord_over_R` | Chord | normalized | unchanged |
| `twist_deg` | Twist | degrees | unchanged |
| `rake_mm` | Rake | mm | value / `(diameter_mm / 2)` |
| `rake_over_R` | Rake | normalized | unchanged |
| `skew_mm` | Skew | mm | value / `(diameter_mm / 2)` |
| `skew_over_R` | Skew | normalized | unchanged |
| `thickness_percent` | Thickness | percent t/c | value / 100 |
| `thickness_ratio` | Thickness | ratio | unchanged |

`row` is an informational index. The review states that it is not mapped into
BladeSpec. Any other column must be mapped or explicitly excluded; unknown
engineering data is not silently ignored. Units are selected explicitly and
are never inferred from magnitude or a generic `value` heading.

For example:

```csv
row,r_over_R,chord_mm,twist_deg,rake_mm,skew_mm
1,0.2,80,30,-2.5,-1.25
2,0.6,55,17.5,-0.25,0.625
3,1,30,5,1.75,2.5
```

The review shows the source, delimiter, row count, radial domain, mapped and
excluded columns, units, interpolation, old/new control counts, and a readable
row preview. Interpolation is chosen separately for every imported
distribution. **Apply Once** replaces only the selected distributions. Chord,
Twist, Rake, Skew, and Thickness may therefore keep independent radial grids by
being imported separately. Distribution import never creates airfoil stations.

The conversion uses the immutable diameter shown in the review. If dimensions
or the design change while the dialog is open, Apply is rejected instead of
reinterpreting the numbers against a newer radius.

The importer preserves signs, scientific notation, and JavaScript numeric
precision. It does not smooth, refit, simplify, resample, merge duplicates, or
convert blanks to zero. It rejects malformed row widths, blank required cells,
nonfinite values, duplicate radii, decreasing radii, invalid domains, and
non-positive Chord/Thickness values. **Sort rows by r/R** is an explicit review
action; it moves complete rows without changing or merging values.

Cancel, parse errors, backend rejection, stale reviews, and unchanged
candidates do not mutate the committed design. A successful bulk change is
validated once, refreshed once from the canonical backend preview, and recorded
as one Undo/Redo transaction. It does not call a CAD build endpoint.

## Airfoil-station setup

Open **Set Up Airfoil Stations**. Station locations are separate from
distribution controls.

- Uniform setup accepts 2 through 64 total stations, including root and tip.
- Explicit setup accepts a whitespace-, comma-, or semicolon-separated `r/R`
  list, including scientific notation.
- Locations must be finite, strictly increasing, unique, and match the current
  root and tip.
- The user selects an existing station/profile as the starting assignment and
  enters a finite, non-negative common physical trailing-edge thickness.
- Matching existing stations can be retained deliberately.
- Replacing Thickness with a two-point constant is a separate, explicit review
  option; it is never implied by a station count.

The review reports old/new station counts, retained and newly assigned counts,
the exact radii, trailing-edge value, and any Thickness control-count change.
The station/profile/TE/thickness changes are committed atomically as one design
edit.

To apply an existing library or imported profile to several stations, select
their checkboxes, choose **Apply Profile to Selected Stations**, review the
profile, and apply once. Constant-thickness coordination is explicit and is
only allowed when the full station set is selected, avoiding a silent global
Thickness rewrite for a partial profile selection.

## Individual edits and generation

Normal add/delete/radius/value editing remains available after bulk input.
Focused numeric fields expose the exact stored number rather than the rounded
three-decimal presentation string. Bulk edits make prior CAD stale, but CAD is
created only after the user explicitly chooses **Generate Blade** or
**Generate Propeller**.
