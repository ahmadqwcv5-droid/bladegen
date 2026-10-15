#!/usr/bin/env bash

# Intended to be sourced. Explicit selection is authoritative; an invalid value
# is deliberately left for BladeGen's fail-closed runtime doctor to reject.
bladegen_workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -z "${OPENVSP_ROOT+x}" ]]; then
  export OPENVSP_ROOT="${bladegen_workspace_root}/.tooling/openvsp-3.54.0-bladegen-fixed-plane.1/opt/OpenVSP"
fi
unset bladegen_workspace_root
