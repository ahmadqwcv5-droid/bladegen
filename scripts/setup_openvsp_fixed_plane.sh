#!/usr/bin/env bash
set -euo pipefail

runtime_id="openvsp-3.54.0-bladegen-fixed-plane.1"
workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
lock_file="${workspace_root}/vendor/openvsp_fixed_plane/upstream.lock.json"
patch_file="${workspace_root}/vendor/openvsp_fixed_plane/patches/0001-bladegen-fixed-radial-sections.patch"
python_bin="${workspace_root}/.venv/bin/python"
install_dir="${workspace_root}/.tooling/${runtime_id}"
runtime_root="${install_dir}/opt/OpenVSP"
stage_parent="${workspace_root}/.tooling/.${runtime_id}.staging"
failure_root="${workspace_root}/.tooling/fp01-build-failures"
build_timeout="${BLADEGEN_OPENVSP_BUILD_TIMEOUT:-7200}"
build_jobs="${BLADEGEN_OPENVSP_BUILD_JOBS:-4}"

fail() {
  echo "FP-01 setup failed: $*" >&2
  exit 1
}

[[ "$(uname -s)" == "Linux" && "$(uname -m)" == "x86_64" ]] || \
  fail "this qualified setup currently supports Linux x86_64 only"
[[ -x "${python_bin}" ]] || fail "run ./scripts/setup_backend.sh dependencies first (.venv is missing)"
[[ "$("${python_bin}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" == "3.12" ]] || \
  fail "the managed runtime is qualified for Python ABI 3.12"

for command in cmake c++ git make ninja timeout curl dpkg-deb sha256sum tar; do
  command -v "${command}" >/dev/null 2>&1 || fail "required command not found: ${command}"
done
"${python_bin}" -c 'import numpy' >/dev/null || fail "NumPy is required in the BladeGen virtualenv"
"${python_bin}" - <<'PY' || fail "CMake 3.24 or newer is required"
import re, subprocess
text = subprocess.check_output(["cmake", "--version"], text=True)
version = tuple(map(int, re.search(r"(\d+)\.(\d+)", text).groups()))
raise SystemExit(0 if version >= (3, 24) else 1)
PY

if [[ -f "${runtime_root}/bladegen-runtime-manifest.json" ]]; then
  if OPENVSP_ROOT="${runtime_root}" "${python_bin}" -m bladegen.cli runtime-info --json >/dev/null 2>&1; then
    echo "${runtime_id} is already verified at ${runtime_root}"
    exit 0
  fi
  echo "Existing managed runtime is partial, stale, or changed; a staged rebuild will be attempted."
fi

[[ ! -e "${stage_parent}" ]] || fail "staging path already exists: ${stage_parent}; inspect it before retrying"
mkdir -p "${stage_parent}" "${failure_root}"
build_log="${stage_parent}/build.log"
source_dir="${stage_parent}/source"
build_dir="${stage_parent}/build"
payload_dir="${stage_parent}/payload"
staged_root="${payload_dir}/opt/OpenVSP"
activated=0

cleanup() {
  status=$?
  if [[ ${status} -ne 0 && -f "${build_log}" ]]; then
    stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    cp "${build_log}" "${failure_root}/${runtime_id}-${stamp}.log"
    echo "Build log preserved under ${failure_root}" >&2
  fi
  if [[ ${activated} -eq 1 || ${status} -eq 0 ]]; then
    rm -rf -- "${stage_parent}"
  else
    echo "Failed staging tree preserved at ${stage_parent}" >&2
  fi
}
trap cleanup EXIT

readarray -t locked < <("${python_bin}" - "${lock_file}" <<'PY'
import json, sys
lock = json.load(open(sys.argv[1], encoding="utf-8"))
print(lock["upstream"]["repository"])
archive = lock["upstream"]["archive"]
print(archive["url"])
print(archive["sha256"])
print(archive["size_bytes"])
print(archive["root_directory"])
print(lock["upstream"]["commit"])
print(lock["build"]["patch_sha256"])
tool = lock["dependency_identity"]["build_tools"]["swig"]
print(tool["url"])
print(tool["sha256"])
PY
)
upstream_url="${locked[0]}"
archive_url="${locked[1]}"
archive_sha="${locked[2]}"
archive_size="${locked[3]}"
archive_root="${locked[4]}"
upstream_commit="${locked[5]}"
expected_patch_sha="${locked[6]}"
swig_url="${locked[7]}"
swig_sha="${locked[8]}"

actual_patch_sha="$(sha256sum "${patch_file}" | cut -d' ' -f1)"
[[ "${actual_patch_sha}" == "${expected_patch_sha}" ]] || \
  fail "production patch checksum mismatch: ${actual_patch_sha}"

archive_cache="${workspace_root}/.tooling/downloads/OpenVSP-${upstream_commit}.tar.gz"
mkdir -p "${workspace_root}/.tooling/downloads"
if [[ -f "${archive_cache}" ]]; then
  [[ "$(stat -c %s "${archive_cache}")" == "${archive_size}" ]] || \
    fail "cached source archive size mismatch: ${archive_cache}"
  [[ "$(sha256sum "${archive_cache}" | cut -d' ' -f1)" == "${archive_sha}" ]] || \
    fail "cached source archive checksum mismatch: ${archive_cache}"
else
  archive_partial="${archive_cache}.partial.$$"
  echo "Fetching immutable OpenVSP commit archive ${upstream_commit}..."
  timeout --signal=TERM --kill-after=30s 3600s curl --fail --location --retry 3 \
    --output "${archive_partial}" "${archive_url}" || \
    fail "locked source fetch failed or exceeded 3600 seconds"
  [[ "$(stat -c %s "${archive_partial}")" == "${archive_size}" ]] || \
    fail "downloaded source archive size mismatch"
  [[ "$(sha256sum "${archive_partial}" | cut -d' ' -f1)" == "${archive_sha}" ]] || \
    fail "downloaded source archive checksum mismatch"
  mv "${archive_partial}" "${archive_cache}"
fi
"${python_bin}" - "${archive_cache}" "${archive_root}" <<'PY'
import sys, tarfile
path, expected_root = sys.argv[1:]
with tarfile.open(path, "r:gz") as archive:
    names = archive.getnames()
roots = {name.split("/", 1)[0] for name in names}
assert roots == {expected_root}, (roots, expected_root)
assert all(name and not name.startswith("/") and ".." not in name.split("/") for name in names)
PY
mkdir -p "${source_dir}"
tar --extract --gzip --file "${archive_cache}" --directory "${source_dir}" \
  --strip-components=1 --no-same-owner --no-same-permissions
[[ -f "${source_dir}/src/geom_core/PropGeom.cpp" ]] || fail "source archive is incomplete"
git -C "${source_dir}" init --quiet
git -C "${source_dir}" apply --check "${patch_file}" \
  >>"${build_log}" 2>&1 || fail "production patch does not apply exactly"
git -C "${source_dir}" apply "${patch_file}" \
  >>"${build_log}" 2>&1 || fail "production patch application failed"

swig_cache="${workspace_root}/.tooling/downloads/swig_4.2.0-2ubuntu1_amd64.deb"
if [[ -f "${swig_cache}" ]]; then
  [[ "$(sha256sum "${swig_cache}" | cut -d' ' -f1)" == "${swig_sha}" ]] || fail "cached SWIG package checksum mismatch: ${swig_cache}"
else
  swig_partial="${swig_cache}.partial.$$"
  echo "Fetching pinned project-local SWIG build tool..."
  timeout --signal=TERM --kill-after=10s 300s curl --fail --location --retry 3 --output "${swig_partial}" "${swig_url}" || fail "pinned SWIG fetch failed"
  [[ "$(sha256sum "${swig_partial}" | cut -d' ' -f1)" == "${swig_sha}" ]] || fail "SWIG package checksum mismatch"
  mv "${swig_partial}" "${swig_cache}"
fi
swig_root="${stage_parent}/swig"
mkdir -p "${swig_root}"
dpkg-deb --extract "${swig_cache}" "${swig_root}"
swig_command="${swig_root}/usr/bin/swig"
[[ -x "${swig_command}" ]] || fail "pinned SWIG package did not contain usr/bin/swig"
export SWIG_LIB="${swig_root}/usr/share/swig4.0"
export PATH="${swig_root}/usr/bin:${PATH}"
"${swig_command}" -version >>"${build_log}" 2>&1

python_include="$("${python_bin}" -c 'import sysconfig; print(sysconfig.get_path("include"))')"
python_library="$("${python_bin}" -c 'import os,sysconfig; print(os.path.join(sysconfig.get_config_var("LIBDIR"), sysconfig.get_config_var("LDLIBRARY")))')"
[[ -f "${python_library}" ]] || fail "Python shared library not found: ${python_library}"
mkdir -p "${build_dir}" "${staged_root}"

echo "Configuring Release/headless OpenVSP with required Python wrappers..."
cmake -S "${source_dir}/SuperProject" -B "${build_dir}" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="${staged_root}" \
  -DBLADEGEN_FIXED_RADIAL_SECTIONS=ON \
  -DVSP_NO_GRAPHICS=ON \
  -DVSP_NO_VSPAERO=ON \
  -DVSP_NO_API_WRAPPERS=OFF \
  -DVSP_NO_HELP=ON \
  -DVSP_NO_DOC=ON \
  -DVSP_NO_PYDOC=ON \
  -DPYTHON_EXECUTABLE="${python_bin}" \
  -DPYTHON_INCLUDE_DIR="${python_include}" \
  -DPYTHON_INCLUDE_PATH="${python_include}" \
  -DPYTHON_LIBRARY="${python_library}" \
  -DSWIG_EXECUTABLE="${swig_command}" >>"${build_log}" 2>&1

echo "Building ${runtime_id} (limit ${build_timeout}s, ${build_jobs} jobs)..."
CMAKE_BUILD_PARALLEL_LEVEL="${build_jobs}" timeout --signal=TERM --kill-after=30s "${build_timeout}s" cmake --build "${build_dir}" --target OpenVSP --parallel 1 >>"${build_log}" 2>&1 || fail "native build failed or reached its finite time limit"

mkdir -p "${staged_root}/share/bladegen"
cp "${lock_file}" "${staged_root}/share/bladegen/upstream.lock.json"
cp "${patch_file}" \
  "${staged_root}/share/bladegen/0001-bladegen-fixed-radial-sections.patch"
cp "${build_log}" "${staged_root}/share/bladegen/build.log"
"${python_bin}" "${workspace_root}/scripts/write_openvsp_runtime_manifest.py" \
  --root "${staged_root}" \
  --lock "${lock_file}" \
  --patch "${patch_file}" \
  --build-log "${build_log}" \
  --compiler "$(command -v c++)" >>"${build_log}" 2>&1

echo "Verifying native import, compiled capability, and a real geometry build..."
OPENVSP_ROOT="${staged_root}" "${python_bin}" -m bladegen.cli runtime-info --json \
  >>"${build_log}" 2>&1
smoke_output="${stage_parent}/geometry-smoke"
OPENVSP_ROOT="${staged_root}" BLADEGEN_BYPASS_AUTO_RIB_ROTATION="inherited-but-ignored" \
  timeout --signal=TERM --kill-after=30s "${BLADEGEN_OPENVSP_SMOKE_TIMEOUT:-300}s" \
  "${python_bin}" -m bladegen.cli build \
  "${workspace_root}/examples/custom_multi_airfoil_finite_te.json" \
  --output "${smoke_output}" >>"${build_log}" 2>&1 || \
  fail "production Python geometry smoke failed"
"${python_bin}" - "${smoke_output}/validation.json" <<'PY' || fail "geometry smoke did not pass"
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
assert data["status"] == "PASS"
assert data["engine"]["construction_contract"] == "bladegen.fixed-radial-sections.v1"
assert data["solidification"]["solid_after_reimport"]["solids"] == 1
assert data["geometry_validation"]["passed"] is True
PY

backup_dir=""
if [[ -e "${install_dir}" ]]; then
  backup_dir="${install_dir}.replaced.$(date -u +%Y%m%dT%H%M%SZ)"
  mv "${install_dir}" "${backup_dir}"
fi
if ! mv "${payload_dir}" "${install_dir}"; then
  [[ -z "${backup_dir}" ]] || mv "${backup_dir}" "${install_dir}"
  fail "could not activate the staged runtime"
fi
activated=1
echo "${runtime_id} is ready at ${runtime_root}"
echo "Run: .venv/bin/bladegen doctor"
