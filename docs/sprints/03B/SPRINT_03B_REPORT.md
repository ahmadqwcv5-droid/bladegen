# Sprint 03B report

## Result

**STRONG PASS.** BladeGen now links stable station selection, canonical 2D
inspection/comparison, and mathematically positioned Three.js station guides
without confusing current editor state with the last successful CAD result.
The complete frontend suite, production build, focused real Chromium workflow,
and all 92 backend tests pass. Five fresh CAD acceptance cases retained one
closed valid solid, zero non-degenerate free edges, stable STEP round trips,
and all existing geometry tolerances.

The implementation is on `sprint/03b-interactive-blade-inspection`. The
BladeSpec schema, resolver, OpenVSP adapter, OCP solidifier, validation engine,
and `00_research_archive` were not modified.

## Station identity and selection

Each table row has a transient `crypto.randomUUID()` identity held beside the
BladeSpec. The ID is deliberately never serialized. Single selection and both
comparison selections store IDs rather than array indices; an index is derived
only when reading the current ordered station array.

Insertion preserves all existing IDs. Radius, profile, thickness, and physical
TE edits therefore keep the intended row selected. Removing another row does
not move selection. Removing the selected row chooses the row now occupying
that position, or the preceding row when the removed row was last. Import,
example load, and reset create fresh IDs and deterministically select the first
station, with the second station as comparison B when available.

The table exposes an orange selected row, orange Station A, teal Station B, a
text status cell, an explicit station/radius summary, and native keyboard-
operable buttons/selects with visible focus indication.

## Three.js station guides

The reusable `stationGuides.ts` helper uses the documented blade coordinate
system directly:

```text
R = diameter_mm / 2
station_y_mm = R * station_r_over_R
```

The STL bounding box only sizes the restrained translucent plane and outline;
it never determines Y. Each guide is an XZ plane whose normal is parallel to
the radial Y axis, plus an outline and marker in the same scene coordinates as
the OCP-derived STL. Examples verified by tests include D=400 mm at r/R 0.20,
0.60, and 1.00 (Y=40, 120, and 200 mm), root r/R 0.18 (Y=36 mm), and D=720 mm
at r/R 0.40 (Y=144 mm).

`BladeViewer` retains one scene, renderer, canvas, controls instance, and STL
load for a given artifact URL. Station changes replace only the guide group.
Every removed plane, line, marker geometry, and material is disposed. Camera
orbit/pan/zoom, Face/Edge/Isometric, Fit, resize, and expand/restore operate on
the same scene. Changing guide selection does not frame the camera or reload
the STL.

The legend reports station number, r/R, and exact world Y. Orange represents
the selected station or Station A; teal represents Station B. The toggle hides
the overlay without changing CAD. UI text states that these are visual radial-
location guides, not measured BRep intersections or final STEP cross-sections.

## Current design versus generated CAD

The existing submitted-BladeSpec snapshot remains authoritative for the STL.
Guides are enabled only when all three conditions hold:

1. a successful preview artifact exists;
2. its submitted snapshot equals the current canonical BladeSpec JSON; and
3. the asynchronous design-preview response is successful and explicitly
   associated with that same editor revision.

Every preview request captures its canonical revision before the 250 ms
debounce. The UI enters pending state immediately. Superseded or aborted
responses cannot relabel the new revision, and a validation failure clears the
current association. Old 2D contours/charts are not shown as current during
debounce or failure.

When inputs change, the previous STL and its job label may remain visible, but
all current-design guides are hidden and an explicit stale warning is shown.
They stay hidden while revised CAD runs and after a failed revised build. A
successful new job replaces the artifact atomically; guides return only if the
submitted snapshot still matches the editor revision.

## Airfoil comparison

Comparison mode uses only `POST /api/design-preview` station payloads. It does
not recreate NACA equations, TE resolution, interpolation, or thickness logic
in JavaScript. A and B are independent controlled selections and default to
different stations where possible.

The engineer can switch between:

- **Source Profiles** — the original canonical airfoil definitions; and
- **Resolved Design Profiles** — effective-thickness and physical-TE geometry
  returned by the backend.

Both profiles share one SVG view box with `preserveAspectRatio="xMidYMid meet"`;
x/c and y/c therefore retain equal geometric scale. Upper and lower surfaces,
LE/TE references, solid orange A, dashed teal B, and a color-independent legend
are included. Measurements report r/R, profile name/type, chord, effective t/c,
geometric maximum t/c, maximum camber/c, x/c of maximum thickness, and requested
physical TE. Embedded coordinate profiles retain their coordinate identity and
are never assigned an invented NACA name.

Comparison is read-only: it neither mutates BladeSpec nor calls Generate.

## Verification

Executed on 2026-10-12 with OpenVSP 3.54.0 and
cadquery-ocp/OpenCascade 7.9.3.1:

```text
cd frontend && npm test
15 test files, 67 tests passed in 10.95 s

cd frontend && npm run build
TypeScript/Vite passed; 38 modules transformed

cd frontend && npx playwright test e2e/sprint03b.spec.ts --project=chromium
1 real Chromium workflow passed in 2.3 min (two real CAD builds)

cd frontend && npm run test:e2e
7 Chromium tests passed in 11.9 min

./scripts/test_backend.sh
92 passed, 1 Starlette/httpx deprecation warning in 447.18 s
```

The browser test asserted—not merely photographed—one canvas, numeric world Y,
one STL fetch per successful artifact, no STL reload while changing stations or
camera modes, dual labels/coordinates, equal-scale source/resolved comparison,
stale suppression, a distinct successful revised job, and restored matching
guides.

The first browser attempt could not load OpenVSP because the machine's temporary
runtime had been cleared. The official 3.54.0 Ubuntu package and `libcminpack1`
were restored under the already documented `/tmp` paths; no repository file was
changed. A subsequent run reached the revised build but exposed a test-only wait
bug: the stale suffix changed the preview label before the job identity changed.
The wait was corrected to require the new active job to succeed and its eight-
character ID to replace the old one. The final workflow passed. The first full-suite run then exposed a genuine narrow-layout regression: the wider station table increased the editor grid item's minimum content width, placing the chart endpoint beyond a 520 px viewport. Editor and section min-width were explicitly contained and the station table bounded to local scrolling. The affected Patch 03A.1 workflow passed alone and again within the final 7/7 full-suite run.

See [the acceptance matrix](SPRINT_03B_ACCEPTANCE_MATRIX.md) for individual
criteria and fresh CAD measurements.

## Screenshot evidence

- [Single selected station in 3D](screenshots/sprint03b/single_station_3d.png)
- [Two comparison stations in 3D](screenshots/sprint03b/two_comparison_stations_3d.png)
- [Source-profile comparison](screenshots/sprint03b/source_profile_comparison.png)
- [Resolved-profile comparison](screenshots/sprint03b/resolved_profile_comparison.png)
- [Stale CAD with guides hidden](screenshots/sprint03b/stale_cad_guides_hidden.png)
- [Matching revised CAD with guides restored](screenshots/sprint03b/matching_new_cad_guides_restored.png)

## Remaining limitations

- Guides identify a design station's radial plane; they are intentionally not
  interactive BRep section extractions.
- Labels are outside the WebGL canvas rather than camera-facing 3D text.
- Guide extent is sized from the model bounds, while its engineering Y remains
  exact. Very unusual geometry can therefore produce a visually large plane.
- The comparison is geometric only. It makes no aerodynamic, structural,
  efficiency, thrust, or optimization claim.
- Build execution remains one serialized CAD worker.
- Vite retains its non-failing Three.js chunk-size warning.

## Manual check

1. Start backend and frontend, load the five-section example, and generate.
2. Inspect station 3 and confirm the legend says r/R 0.6000, Y 120.000 mm.
3. Orbit, switch views, expand/restore, and confirm the guide remains present.
4. Open Compare Stations; select A=0.20 and B=0.80 and confirm Y=40/160 mm.
5. Switch Source/Resolved and inspect the canonical measurement table.
6. Edit a chord value and confirm the old CAD remains labeled while guides hide.
7. Generate again and confirm guides return only after the new job succeeds.
