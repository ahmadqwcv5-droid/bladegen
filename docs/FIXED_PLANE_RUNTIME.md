# Managed fixed-plane runtime

BladeGen production generation requires the project-defined construction
contract `bladegen.fixed-radial-sections.v1` and runtime build
`openvsp-3.54.0-bladegen-fixed-plane.1`.

## Construction contract

In the blade's local engineering frame, radial location is
`Y = (diameter_mm / 2) * r_over_R`, and the requested section lies in that
fixed-Y plane. Chord, twist, rake, skew, thickness, trailing-edge, and reference
axis meanings remain those of BladeSpec v0.2. Rake changes axial placement; its
derivative does not add an unrequested rib-plane tilt. Whole-blade and
propeller-assembly transforms remain unchanged.

This is a BladeGen backend semantic correction, not a claim that upstream
OpenVSP's default propeller positioning is wrong for other applications. There
is no X-57-specific branch and no user-facing native-mode switch.

## Install and inspect

The setup is project-local, source pinned, staged, and fail-closed:

```bash
./scripts/setup_openvsp_fixed_plane.sh
source scripts/openvsp_env.sh
.venv/bin/bladegen doctor
.venv/bin/bladegen runtime-info --json
```

The generated runtime lives under
`.tooling/openvsp-3.54.0-bladegen-fixed-plane.1/`; the official stock runtime
at `.tooling/openvsp-3.54.0/` is retained side by side. The setup does not use
sudo or replace `/opt/OpenVSP`. An unchanged verified installation is reused.
A partial, changed, wrong-ABI, or stale installation is rebuilt through a
staging path and is never activated before native import, compiled capability,
and real geometry checks pass.

`OPENVSP_ROOT` is the only override. If it is set, that exact absolute root is
validated; an invalid explicit value never falls back to the managed default,
stock `/opt`, a pip package, or `/tmp`. Restart a worker after changing the
runtime because an already imported native module is not replaced in-process.

The setup lock and patch are in `vendor/openvsp_fixed_plane/`. Generated source,
build, install, and downloaded tool files are ignored. The installed
`bladegen-runtime-manifest.json` records the upstream commit, patch hash,
toolchain, Python ABI/SOABI, build options, and runtime artifact hashes.

## Native change and identity

The maintained patch is based on OpenVSP 3.54.0 commit
`db6c6fe8f4eca27d7517f4ae0b2078abdd3fd927`. With the compile feature ON,
OpenVSP still calculates `m_ZRotate`, but applies identity at the single
automatic propeller rib-rotation operation. With the feature OFF, the patched
source retains upstream behavior. No profile fitting, derivatives, rib
selection, loft, cap, tolerance, or export setting is changed.

The real SWIG/native binding exports:

- `GetBladeGenBuildID()`
- `GetBladeGenConstructionContract()`
- `HasBladeGenFixedRadialSectionsV1()`

BladeGen checks these compiled values in a bounded fresh process and also binds
the imported Python and native module paths/hashes to the selected root.
`BLADEGEN_BYPASS_AUTO_RIB_ROTATION` and other diagnostic flags have no geometry
effect in this build.

## Runtime behavior and provenance

Input editing, save/open, examples, and `POST /api/validate` remain available
without a CAD runtime. `GET /api/runtime` reports generation readiness. A build
request is rejected with HTTP 503 before a job directory is queued when the
runtime is incompatible. The serialized child worker independently verifies
the queued fingerprint and fails if the runtime changes while waiting.

Each attempt writes `engine_manifest.json` with distinct `REQUESTED`,
`ACTUALLY_LOADED`, and `COMPLETED` states. It contains canonical submitted and
resolved-definition hashes, implementation identities, selected/loaded engine
identity, local module hashes/paths, dependency versions, run/job identity, and
the effective timeout. Legacy outputs without this file have unknown/legacy
engine identity; they are never relabeled.

A VSP3 file is not frozen proof of fixed-plane behavior: opening/updating it in
a stock runtime can recompute different geometry. Replay requires the same
BladeSpec, fixed-plane contract, runtime build/fingerprint, adapter/resolver,
and validation implementation. The final STEP is the frozen generated shape.

## Rollback and limits

Rollback is explicit: check out the preceding application commit/branch and use
its documented official-runtime setup. Do not point this fixed-plane application
at the stock runtime; it will reject it. Historical job artifacts and the
original failed X-57 job must remain unchanged.

Qualification is currently Linux x86_64/Python 3.12 only. Broader CAD designs,
Windows/macOS, desktop packaging, default-300-second full X-57 UI usability,
external NASA surface fidelity, and the earlier profile-preparation refinement
remain separate or pending qualifications.
