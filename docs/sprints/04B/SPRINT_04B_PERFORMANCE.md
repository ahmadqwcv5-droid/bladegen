# Sprint 04B performance qualification

## Environment and method

Measurements were taken on Linux 6.17.0-22-generic x86_64 (glibc 2.39), Python
3.12.3, NumPy 2.5.3, Chromium through Playwright, and the repository working
tree based on `30d85b2cc8d696ed7f1ea5461ad205557fe2743b`. Each timed case records a
cold first operation separately, followed by 20 ordinary warm repetitions.
Median, interpolated p95, and maximum are reported without dropping outliers.

The evaluator comparison uses the same deterministic 40- and 200-control,
five-curve inputs. The legacy comparator reproduces the prior scalar behavior
of constructing PCHIP for each of the 5,001 verification locations. The
prepared comparator constructs each evaluator once and vectorizes those exact
same query locations. It is a same-run algorithm comparator, not a claimed
historical wall-clock recording.

Commands:

```text
cd backend && ../.venv/bin/python ../scripts/benchmark_curve_resolution.py
cd backend && ../.venv/bin/python ../scripts/benchmark_interactive_validation.py
cd frontend && npx vitest run src/editor/distributionImport.performance.test.ts --disableConsoleIntercept --reporter=verbose
cd frontend && npm run test:e2e
```

## Canonical evaluator: before and after

All values below are seconds. The authoritative 5,001-location verification
density, SciPy PCHIP, disabled extrapolation, exact-control behavior, adaptive
tolerances, and semantic checks are unchanged.

| Controls per curve | Phase | Cold | Warm median | Warm p95 | Warm max |
| ---: | --- | ---: | ---: | ---: | ---: |
| 40 | Legacy dense scalar evaluation | 2.702029 | 2.727403 | 2.877514 | 3.138743 |
| 40 | Prepared/vectorized dense evaluation | 0.001105 | 0.000950 | 0.000971 | 0.000979 |
| 40 | Current complete curve resolution | 0.006221 | 0.005679 | 0.005738 | 0.005800 |
| 200 | Legacy dense scalar evaluation | 3.185702 | 3.163275 | 3.250552 | 3.467738 |
| 200 | Prepared/vectorized dense evaluation | 0.001135 | 0.001009 | 0.001027 | 0.001042 |
| 200 | Current complete curve resolution | 0.015766 | 0.015716 | 0.015837 | 0.015921 |

PCHIP constructor counts for the dense phase are 25,005 legacy versus 5
prepared. Complete current resolution also constructs 5: one immutable
request-local evaluator for each of Chord, Twist, Rake, Skew, and Thickness.

## Interactive validation and canonical preview

This benchmark performs one real FastAPI `POST /api/validate` followed by one
real `POST /api/design-preview` for each operation. CAD requests are zero. Each
request is request-local and therefore constructs five PCHIP evaluators; the
two-request interactive operation reports 10 constructors.

| Controls per curve | Cold | Warm median | Warm p95 | Warm max | Requests per operation |
| ---: | ---: | ---: | ---: | ---: | --- |
| 40 | 0.031917 s | 0.017837 s | 0.028509 s | 0.094167 s | 1 validate, 1 preview, 0 CAD |
| 200 | 0.042968 s | 0.045413 s | 0.047175 s | 0.047416 s | 1 validate, 1 preview, 0 CAD |

Both provisional commit targets pass: p95 is below 1 second for 40 controls per
curve and below 2 seconds for 200 controls per curve.

## Browser-side import and acknowledgement

The import microbenchmark parses the delimited text and builds the complete
immutable candidate; it excludes a file-picker gesture and backend requests.

| Rows | Cold | Warm median | Warm p95 | Warm max |
| ---: | ---: | ---: | ---: | ---: |
| 40 | 0.737451 ms | 0.091480 ms | 0.178976 ms | 0.241520 ms |
| 200 | 0.333486 ms | 0.303403 ms | 0.344208 ms | 0.348757 ms |

The final consolidated Playwright run opened and acknowledged the actual Import
Distributions dialog 20 warm times: median 55.127 ms, p95 71.929 ms, maximum
75.054 ms. This passes the 100 ms visible-acknowledgement target. Browser-side
40-row parsing passes the 500 ms target with substantial margin.

The microbenchmarks intentionally contain no CAD work. The separate browser
qualification explicitly generated CAD only after import, review, Apply,
export/open, Undo/Redo, and a manual numerical edit had completed.
