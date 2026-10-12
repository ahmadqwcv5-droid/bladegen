import { describe, expect, it } from 'vitest'
import exampleJson from '../../../examples/custom_multi_airfoil_finite_te.json'
import { nominalHubGuidance } from './assemblyValidation'
import type { AssemblySpec, BladeSpec } from '../types/bladespec'

const blade = exampleJson as unknown as BladeSpec
const assembly: AssemblySpec = {
  blade_count: 2,
  hub_diameter_mm: 60,
  hub_length_mm: 30,
  shaft_bore_diameter_mm: 12,
  initial_azimuth_deg: 0,
}

describe('nominal assembly guidance', () => {
  it('reports the strict 80 mm bound and 10 mm radial gap dynamically', () => {
    expect(nominalHubGuidance(blade, assembly)).toEqual({
      root_radius_mm: 40,
      hub_radius_mm: 30,
      nominal_radial_overlap_mm: 0,
      nominal_radial_gap_mm: 10,
      required_hub_diameter_bound_mm: 80,
      bound_is_exclusive: true,
      passes_nominal_policy: false,
    })
  })

  it('updates the bound when propeller diameter changes', () => {
    const guidance = nominalHubGuidance({ ...blade, diameter_mm: 600 }, { ...assembly, hub_diameter_mm: 90 })
    expect(guidance.root_radius_mm).toBe(60)
    expect(guidance.required_hub_diameter_bound_mm).toBe(120)
    expect(guidance.nominal_radial_gap_mm).toBe(15)
  })
})
