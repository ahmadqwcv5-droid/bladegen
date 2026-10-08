#!/usr/bin/env bash
set -euo pipefail
workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -z "${OPENVSP_ROOT:-}" && -d /tmp/openvsp_root/opt/OpenVSP ]]; then export OPENVSP_ROOT=/tmp/openvsp_root/opt/OpenVSP; fi
if [[ -d /tmp/cminpack_root/usr/lib/x86_64-linux-gnu ]]; then export LD_LIBRARY_PATH="/tmp/cminpack_root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"; fi
cd "${workspace_root}"
exec .venv/bin/pytest backend/tests
