# FP02-C1 compact-evidence omissions

The compact evidence ZIP intentionally omits large binary CAD and browser trace
artifacts. It includes the original Q02/Q03/Q04 definitions, Q04.R1, reports,
machine-readable matrix/browser/test summaries, retained measurement records,
plots, CSVs and small section BRePs.

Omitted from the ZIP but retained in the workspace:

- all full matrix job trees under
  `fp02_c1_20261015T075331Z/corrected/matrix/fp02_c1_matrix_20261015T083858Z/jobs/`;
- baseline and fresh full STEP/VSP3/STL files;
- Playwright trace/video directories;
- the 86 MB final browser X-57 STEP, supplied separately as
  `qualification/fp02_c1/artifacts/x57_hlp_final_browser.step`.

Key full STEP hashes:

- retained failed Q02: `285d06d6b7f4e2ee7526727cc26328bb614be4cf173834664ebebabaa167d07b`;
- fresh final-matrix Q02: `6414059111922985e73c3101c80d3221cce96e00cc2490f010219a05cef67ba1`;
- fresh final-matrix Q03: `99b76ad7987c29dec1c3faefa5ab546cd989cbbe272c931a442e13285093b618`;
- fresh final-matrix Q04.R1: `d6f073ee954497825fdfa0dee74b81f0d22d049c664f1b79ad8cca1fd75873e6`;
- final browser X-57: `a50dfbff9da673bdabde10b48b33d5dbbf89b66b3435788b55c690d507cb5974`.

These files are not claimed to be present inside the compact ZIP.
