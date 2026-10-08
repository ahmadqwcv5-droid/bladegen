#!/usr/bin/env bash
set -euo pipefail
workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -x "${workspace_root}/.venv/bin/python" ]]; then uv venv --python 3.12 "${workspace_root}/.venv"; fi
uv pip install --link-mode copy --python "${workspace_root}/.venv/bin/python" -e "${workspace_root}/backend[dev]"
