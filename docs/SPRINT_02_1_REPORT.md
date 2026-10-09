# Sprint 02.1 report

## Result

**STRONG PASS.** Progress is emitted by the real CAD subprocess, preview and
artifact identity is bound to immutable successful results, the Three.js
viewer is larger and expandable, imported projects are backend-validated
before replacement, and the section-wire checks are required validation
gates. Real Chromium and OpenVSP/OCP acceptance runs completed successfully.

The validated geometry architecture, BladeSpec v0.2, engineering tolerances,
and CAD engine were not changed.

## Backend progress

The CLI accepts an optional `--progress-file`. The pipeline writes one
structured `progress.json` update in the job directory using a temporary file
and `os.replace`. The API job manager reads only that job's file while the
existing isolated subprocess runs. Invalid or partial files are ignored,
updates cannot move backward, and a progress-write failure does not invalidate
an otherwise successful CAD build.

| Confirmed milestone / current operation | Percent |
|---|---:|
| Queued / input validation starts | 0% |
| BladeSpec validated; canonical resolution starts | 5% |
| Curves and airfoils resolved; OpenVSP starts | 18% |
| OpenVSP export/readback passed; OCP solidification starts | 52% |
| Valid solid STEP completed; preview generation starts | 72% |
| Preview completed; independent STEP validation starts | 80% |
| Independent validation passed; artifacts are written | 95% |
| Required artifacts successfully written | 100% |

The status endpoint now returns `stage`, `stage_label`, `progress_percent`,
`message`, and actual `elapsed_seconds` while preserving the existing job
fields. Percentages change only at confirmed stage boundaries; there is no
timer-derived numeric progress and no unsupported remaining-time estimate.

On subprocess failure the manager refreshes and retains the last confirmed
stage and percentage. Timeouts report the configured duration and current
stage. Captured stdout and stderr are retained as `build_stdout.log` and
`build_stderr.log` inside the private job directory. Workspace and job paths are
redacted from public errors, and only allow-listed product artifacts remain
downloadable through the API.

## Product reliability changes

- `activeJob` is now independent of `displayedResult`. A displayed result owns
  its successful job ID, submitted BladeSpec snapshot, artifacts, validation
  data, and completion time. A running or failed Job B cannot relabel Result A;
  successful Result B replaces the preview and artifacts atomically.
- Job-ID guards prevent late polling and artifact responses from older jobs
  from overwriting current state. A synchronous submission guard prevents
  duplicate build requests before React state has updated.
- The reusable progress component exposes an accessible progress bar, backend
  stage text, actual elapsed time, status, activity indicator, and categorized
  input/build/topology/geometry failure messages.
- JSON import performs runtime structural checks, then calls `/api/validate`.
  The editor is replaced only after authoritative backend validation succeeds;
  rejected imports preserve the current project. Coordinate airfoils and all
  independent distributions pass through without conversion.

## Viewer

The desktop editor/viewer layout is 55/45 and the normal viewer uses
`height: clamp(480px, 65vh, 850px)`. Responsive breakpoints collapse the layout
without horizontal viewer overflow.

Expanded mode uses the same viewer DOM, scene, mesh, controls, and WebGL
context, so expand/restore does not reload the STL or duplicate GPU resources.
It supports Escape, orbit/pan/zoom, Fit to Model, Isometric, Front, and Side
views. A container `ResizeObserver` updates renderer size, camera aspect, and
projection. Cleanup cancels the animation frame, disconnects the observer,
disposes controls/geometries/materials/renderer, and releases the context.
Late STL responses are discarded and disposed. Loading and failure overlays
are explicit.

## CAD validation gate

Each independently measured final-STEP section now records and requires:

- exactly one resulting wire;
- `wire_valid == true`;
- `wire_closed == true`.

These checks supplement rather than replace whole-solid BRep, closed-shell,
free-edge, round-trip, and geometry-tolerance checks. A focused parameterized
test proves that failure of any one wire condition fails the required geometry
summary.

## Fresh CAD regression results

All values below came from the final STEP after re-import during the Sprint
02.1 run. They match the tracked Sprint 02 acceptance matrix at its published
precision.

| Case | Solid / shell | Closed / valid / free edges | Volume mm³ | Chord max mm | Twist max deg | Axis max mm | TE max mm |
|---|---:|---:|---:|---:|---:|---:|---:|
| 3 sections, root 0.25 | 1 / 1 | true / true / 0 | 28,910.418807 | 0.002337 | 0.001784 | 0.000102 | 0.002046 |
| 5-section baseline | 1 / 1 | true / true / 0 | 38,559.346223 | 0.004043 | 0.001591 | 0.004526 | 0.016732 |
| 8 sections, root 0.18 | 1 / 1 | true / true / 0 | 35,725.270721 | 0.004573 | 0.001570 | 0.004419 | 0.007775 |
| NACA 0008, effective t/c 0.10 | 1 / 1 | true / true / 0 | 24,135.299077 | 0.002337 | 0.001784 | 0.000102 | 0.002047 |

Every round-trip retained one solid, one shell, zero non-degenerate free
edges, a closed shell, and valid BRepCheck. The largest measured round-trip
volume delta was `6.91e-9 mm³`; the largest bounding-box coordinate delta was
`7.50e-12 mm`. Adaptive Gauss–Kronrod volume integration and all existing
tolerances remain unchanged.

## Executed verification

```bash
./scripts/test_backend.sh
# 44 passed, 1 pre-existing Starlette/httpx deprecation warning, 326.44 s

cd frontend && npm test -- --reporter=dot
# 3 files, 24 tests passed

cd frontend && npm run build
# TypeScript + Vite production build passed; 28 modules transformed

cd frontend && npm run test:e2e
# 2 passed in 58.2 s: mocked failure/race plus real backend OpenVSP/OCP Chromium flow
```

The real browser scenario loaded the example, edited a parameter, observed
backend progress above zero and then 100%, loaded the OCP STL, expanded the
viewer, exercised orbit/zoom/fit, restored it with Escape, downloaded the STEP,
edited the input, and observed the stale-result warning. The mocked scenario
proved that failed Job B remains attributed to B and cannot relabel Result A.

## Browser evidence

- [Progress during the real build](screenshots/sprint02_1_progress.png)
- [Successful real build](screenshots/sprint02_1_success.png)
- [Normal viewer](screenshots/sprint02_1_viewer_normal.png)
- [Expanded viewer](screenshots/sprint02_1_viewer_expanded.png)
- Failed-job evidence: `frontend/e2e/job-failure.spec.ts`, executed successfully
  as recorded above.

## Known limitations

- Build execution remains intentionally serialized to one isolated CAD worker.
- Stage percentages represent confirmed engineering milestones, not elapsed
  time or an ETA; a long OpenVSP operation may remain at 18%.
- The production bundle reports Vite's non-failing warning that the Three.js
  bundle exceeds 500 kB. Code splitting is a future performance improvement,
  not a correctness blocker.
- Coordinate airfoils remain editable through their neutral JSON data rather
  than a graphical point editor.

## Run commands

In separate terminals from the repository root:

```bash
./scripts/start_backend.sh
./scripts/start_frontend.sh
```

Open `http://127.0.0.1:5173`. To run browser acceptance after dependencies and
the Playwright Chromium bundle are installed:

```bash
cd frontend
npx playwright install chromium
npm run test:e2e
```
