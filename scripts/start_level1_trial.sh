#!/usr/bin/env bash
set -euo pipefail

workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
api_port="${BLADEGEN_API_PORT:-8012}"
ui_port="${BLADEGEN_UI_PORT:-5175}"
export BLADEGEN_BUILD_TIMEOUT=900
export BLADEGEN_API_PORT="${api_port}"
export BLADEGEN_API_TARGET="http://127.0.0.1:${api_port}"

source "${workspace_root}/scripts/openvsp_env.sh"
cd "${workspace_root}"

echo "BladeGen profile: level1-trial"
echo "Worker timeout: ${BLADEGEN_BUILD_TIMEOUT} seconds per design"
echo "Backend: http://127.0.0.1:${api_port}"
echo "Frontend: http://127.0.0.1:${ui_port}"
echo "Checking managed fixed-plane runtime before launch..."
"${workspace_root}/.venv/bin/python" -m bladegen.cli doctor

backend_pid=""
frontend_pid=""
stop_owned_processes() {
  [[ -z "${frontend_pid}" ]] || kill "${frontend_pid}" 2>/dev/null || true
  [[ -z "${backend_pid}" ]] || kill "${backend_pid}" 2>/dev/null || true
  [[ -z "${frontend_pid}" ]] || wait "${frontend_pid}" 2>/dev/null || true
  [[ -z "${backend_pid}" ]] || wait "${backend_pid}" 2>/dev/null || true
}
trap stop_owned_processes EXIT INT TERM

"${workspace_root}/.venv/bin/uvicorn" api.main:app \
  --app-dir backend --host 127.0.0.1 --port "${api_port}" &
backend_pid="$!"

(
  cd "${workspace_root}/frontend"
  exec npm run dev -- --host 127.0.0.1 --port "${ui_port}"
) &
frontend_pid="$!"

echo "Level 1 trial services started. Press Ctrl+C once to stop both owned processes."
wait -n "${backend_pid}" "${frontend_pid}"
