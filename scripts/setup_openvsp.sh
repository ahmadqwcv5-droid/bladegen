#!/usr/bin/env bash
set -euo pipefail

openvsp_version="3.54.0"
workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
install_dir="${workspace_root}/.tooling/openvsp-${openvsp_version}"
openvsp_root="${install_dir}/opt/OpenVSP"
cminpack_lib="${install_dir}/usr/lib/x86_64-linux-gnu/libcminpack.so.1"
package_name="OpenVSP-${openvsp_version}-Ubuntu-24.04_amd64.deb"
package_url="https://openvsp.org/download.php?file=zips/old/linux/${package_name}"

if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
  echo "Automatic OpenVSP setup supports Linux x86_64 only." >&2
  echo "Install OpenVSP ${openvsp_version} manually and set OPENVSP_ROOT." >&2
  exit 1
fi

if [[ -d "${openvsp_root}/python/openvsp_config" && -e "${cminpack_lib}" ]]; then
  echo "OpenVSP ${openvsp_version} is ready at ${openvsp_root}"
  exit 0
fi

for required_command in curl dpkg-deb apt-get; do
  if ! command -v "${required_command}" >/dev/null 2>&1; then
    echo "Required setup command not found: ${required_command}" >&2
    exit 1
  fi
done

temporary_dir="$(mktemp -d)"
staging_dir="${install_dir}.staging.$$"
cleanup() {
  rm -rf -- "${temporary_dir}" "${staging_dir}"
}
trap cleanup EXIT

openvsp_deb="${temporary_dir}/${package_name}"
if [[ -f "/tmp/${package_name}" ]]; then
  cp "/tmp/${package_name}" "${openvsp_deb}"
else
  echo "Downloading official OpenVSP ${openvsp_version}..."
  curl --fail --location --retry 3 --output "${openvsp_deb}" "${package_url}"
fi

if [[ "$(dpkg-deb -f "${openvsp_deb}" Package)" != "openvsp" || \
      "$(dpkg-deb -f "${openvsp_deb}" Version)" != "${openvsp_version}" || \
      "$(dpkg-deb -f "${openvsp_deb}" Architecture)" != "amd64" ]]; then
  echo "Downloaded package metadata does not match OpenVSP ${openvsp_version} amd64." >&2
  exit 1
fi

mkdir -p "${temporary_dir}/cminpack" "${staging_dir}"
(
  cd "${temporary_dir}/cminpack"
  apt-get download libcminpack1
)
cminpack_packages=("${temporary_dir}/cminpack"/libcminpack1_*.deb)
if [[ ! -f "${cminpack_packages[0]}" ]]; then
  echo "Could not download the libcminpack1 runtime package." >&2
  exit 1
fi

echo "Extracting OpenVSP and libcminpack into ${install_dir}..."
dpkg-deb --extract "${openvsp_deb}" "${staging_dir}"
dpkg-deb --extract "${cminpack_packages[0]}" "${staging_dir}"

if [[ ! -d "${staging_dir}/opt/OpenVSP/python/openvsp_config" || \
      ! -e "${staging_dir}/usr/lib/x86_64-linux-gnu/libcminpack.so.1" ]]; then
  echo "Extracted OpenVSP runtime is incomplete." >&2
  exit 1
fi

if [[ -e "${install_dir}" ]]; then
  backup_dir="${install_dir}.incomplete.$(date +%Y%m%d%H%M%S)"
  mv "${install_dir}" "${backup_dir}"
  echo "Moved the incomplete previous runtime to ${backup_dir}"
fi
mv "${staging_dir}" "${install_dir}"

echo "OpenVSP ${openvsp_version} is ready at ${openvsp_root}"
echo "Use ./scripts/start_backend.sh so the required environment is loaded."
