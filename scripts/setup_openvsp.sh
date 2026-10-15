#!/usr/bin/env bash
set -euo pipefail
workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "setup_openvsp.sh now installs BladeGen's managed fixed-plane runtime."
exec "${workspace_root}/scripts/setup_openvsp_fixed_plane.sh" "$@"
