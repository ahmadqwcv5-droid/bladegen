# BladeGen fixed-plane OpenVSP flavor

This directory describes BladeGen's modified OpenVSP 3.54.0 distribution. It is
not an upstream OpenVSP feature and is not endorsed by upstream.

The single geometry change is compile-time guarded. With
`BLADEGEN_FIXED_RADIAL_SECTIONS=ON`, OpenVSP continues to calculate the native
derivative-driven `m_ZRotate` value but applies an identity rotation at the
propeller rib-positioning operation. All surrounding translations, pivots,
rotations, cylinder projection, lofting, caps, and export behavior remain
unchanged. With the option OFF, the patched source follows upstream behavior.

The compiled Python binding exports `GetBladeGenBuildID()`,
`GetBladeGenConstructionContract()`, and
`HasBladeGenFixedRadialSectionsV1()`. BladeGen accepts only the expected build
ID, contract, capability, module locations, and hashes.

Build the project-local runtime with:

```bash
./scripts/setup_openvsp_fixed_plane.sh
```

Generated source, build, and install trees live under `.tooling/` and are not
versioned. The stock `.tooling/openvsp-3.54.0` runtime is retained side by side.
OpenVSP's NOSA license and upstream notices are installed with the modified
runtime.
