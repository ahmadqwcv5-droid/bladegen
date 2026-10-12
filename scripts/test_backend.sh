#!/usr/bin/env bash
set -euo pipefail
workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${workspace_root}/scripts/openvsp_env.sh"
cd "${workspace_root}"
exec .venv/bin/pytest backend/tests
