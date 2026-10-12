#!/usr/bin/env bash

# This file is intended to be sourced by BladeGen launchers and interactive
# shells. An explicitly configured OPENVSP_ROOT always takes precedence.
bladegen_workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -z "${OPENVSP_ROOT:-}" ]]; then
  for bladegen_openvsp_candidate in \
    "${bladegen_workspace_root}/.tooling/openvsp-3.54.0/opt/OpenVSP" \
    "/opt/OpenVSP" \
    "/tmp/openvsp_root/opt/OpenVSP"; do
    if [[ -d "${bladegen_openvsp_candidate}/python/openvsp_config" ]]; then
      export OPENVSP_ROOT="${bladegen_openvsp_candidate}"
      break
    fi
  done
fi

if [[ -z "${OPENVSP_ROOT:-}" || ! -d "${OPENVSP_ROOT}/python/openvsp_config" ]]; then
  echo "OpenVSP 3.54.0 runtime not found. Run ./scripts/setup_openvsp.sh first." >&2
  return 1 2>/dev/null || exit 1
fi

bladegen_cminpack_dir="${bladegen_workspace_root}/.tooling/openvsp-3.54.0/usr/lib/x86_64-linux-gnu"
if [[ -d "${bladegen_cminpack_dir}" ]]; then
  case ":${LD_LIBRARY_PATH:-}:" in
    *":${bladegen_cminpack_dir}:"*) ;;
    *) export LD_LIBRARY_PATH="${bladegen_cminpack_dir}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}" ;;
  esac
elif [[ -d /tmp/cminpack_root/usr/lib/x86_64-linux-gnu ]]; then
  export LD_LIBRARY_PATH="/tmp/cminpack_root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
fi

unset bladegen_cminpack_dir bladegen_openvsp_candidate bladegen_workspace_root
