#!/usr/bin/env bash
set -euo pipefail
workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${workspace_root}/scripts/openvsp_env.sh"
cd "${workspace_root}"
"${workspace_root}/.venv/bin/python" -m bladegen.cli doctor
exec .venv/bin/uvicorn api.main:app --app-dir backend --host 127.0.0.1 --port "${BLADEGEN_API_PORT:-8000}"
