# Test suites

Product backend, API, and end-to-end CAD tests live in `backend/tests` so they
are packaged and configured by `backend/pyproject.toml`. Run all of them from
the workspace root with `./scripts/test_backend.sh`.

Frontend production verification runs from `frontend` with `npm run build`.
Browser automation is planned for Sprint 02.
