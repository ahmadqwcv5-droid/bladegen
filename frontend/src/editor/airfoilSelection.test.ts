import { describe, expect, it } from 'vitest'
import example from '../../../examples/custom_multi_airfoil_finite_te.json'
import { applyAirfoilProfile } from './airfoilSelection'
import type { AirfoilProfile, BladeSpec } from '../types/bladespec'

const imported: AirfoilProfile = {
  profile_id: 'imported-test',
  display_name: 'Independent 11%',
  category: 'imported',
  source: 'fixture',
  license: 'unknown',
  point_counts: { upper: 3, lower: 3 },
  metrics: {
    max_thickness_ratio: .11,
    max_thickness_x_over_c: .5,
    max_camber_ratio: .02,
    max_camber_x_over_c: .5,
    trailing_edge_gap_ratio: .01,
  },
  airfoil: {
    type: 'coordinates',
    upper: [[0, 0], [.5, .075], [1, .005]],
    lower: [[0, 0], [.5, -.035], [1, -.005]],
  },
}

describe('airfoil library engineering application', () => {
  it('embeds imported coordinates and coordinates only the active thickness station', () => {
    const spec = structuredClone(example) as BladeSpec
    const before = structuredClone(spec.thickness_distribution.points)
    const next = applyAirfoilProfile(spec, 2, imported)
    expect(next.airfoil_sections[2].airfoil).toEqual(imported.airfoil)
    expect(next.airfoil_sections[2].thickness_override_ratio).toBeUndefined()
    expect(next.thickness_distribution.points[2].thickness_ratio).toBe(.11)
    expect(next.thickness_distribution.points[0]).toEqual(before[0])
    expect(next.thickness_distribution.points[1]).toEqual(before[1])
    expect(next.thickness_distribution.points[3]).toEqual(before[3])
    expect(next.airfoil_sections[1]).toEqual(spec.airfoil_sections[1])
  })

  it('keeps an explicit NACA override explicit when selecting another NACA', () => {
    const spec = structuredClone(example) as BladeSpec
    spec.airfoil_sections[1].thickness_override_ratio = .13
    const profile = { ...imported, category: 'naca4' as const, airfoil: { type: 'naca4' as const, code: '0012' } }
    const next = applyAirfoilProfile(spec, 1, profile)
    expect(next.airfoil_sections[1].airfoil).toEqual({ type: 'naca4', code: '0012' })
    expect(next.airfoil_sections[1].thickness_override_ratio).toBe(.13)
    expect(next.thickness_distribution.points[1].thickness_ratio).toBe(spec.thickness_distribution.points[1].thickness_ratio)
  })
})
