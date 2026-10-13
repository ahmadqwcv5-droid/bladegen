import { describe, expect, it } from 'vitest'
import bladeJson from '../../../examples/custom_multi_airfoil_finite_te.json'
import propellerJson from '../../../examples/propeller_three_blade.json'
import { parseProjectDocument, propellerFromProject } from './projectDocument'
import type { BladeSpec, PropellerSpec } from '../types/bladespec'

const blade = bladeJson as unknown as BladeSpec
const propeller = propellerJson as unknown as PropellerSpec

describe('project document parsing', () => {
  it('identifies BladeSpec by structure and supplies a complete neutral assembly baseline', () => {
    const project = parseProjectDocument(JSON.stringify(blade))
    expect(project.kind).toBe('blade')
    expect(project.bladeSpec).toEqual(blade)
    expect(project.assembly.hub_diameter_mm).toBe(90)
  })

  it('round-trips complete PropellerSpec data without deriving its name', () => {
    const custom = {
      ...propeller,
      name: 'customer_project_alpha',
      blade_spec: {
        ...propeller.blade_spec,
        airfoil_sections: propeller.blade_spec.airfoil_sections.map((section, index) => index === 1 ? {
          ...section,
          airfoil: {
            type: 'coordinates' as const,
            upper: [[0, 0], [0.333333333333, 0.071234567891], [1, 0.004]],
            lower: [[0, 0], [0.25, -0.052345678912], [1, -0.004]],
          },
          thickness_override_ratio: null,
        } : section),
        chord_distribution: {
          interpolation: 'linear' as const,
          points: [
            ...propeller.blade_spec.chord_distribution.points,
            { r_over_R: .925, chord_over_R: .123456789012 },
          ].sort((left, right) => left.r_over_R - right.r_over_R),
        },
      },
      assembly: { ...propeller.assembly, hub_length_mm: 30, initial_azimuth_deg: 17.125 },
    }
    const project = parseProjectDocument(JSON.stringify(custom))
    expect(project.kind).toBe('propeller')
    expect(project.propellerName).toBe('customer_project_alpha')
    expect(propellerFromProject(project)).toEqual(custom)
    expect(project.bladeSpec.airfoil_sections[1].airfoil.type).toBe('coordinates')
    expect(project.bladeSpec.chord_distribution.points).toHaveLength(7)
    expect(project.bladeSpec.thickness_distribution.points).toHaveLength(5)
  })

  it('normalizes omitted azimuth to zero and preserves explicit finite values', () => {
    const omitted = structuredClone(propeller) as PropellerSpec
    delete (omitted.assembly as Partial<PropellerSpec['assembly']>).initial_azimuth_deg
    const project = parseProjectDocument(JSON.stringify(omitted))
    expect(project.assembly.initial_azimuth_deg).toBe(0)
    expect(propellerFromProject(project).assembly.initial_azimuth_deg).toBe(0)

    const explicit = structuredClone(propeller)
    explicit.assembly.initial_azimuth_deg = 17.5
    expect(parseProjectDocument(JSON.stringify(explicit)).assembly.initial_azimuth_deg).toBe(17.5)
  })

  it.each([null, 'zero'])('rejects explicit invalid azimuth %s', invalid => {
    const document = structuredClone(propeller) as unknown as Record<string, unknown>
    const assembly = document.assembly as Record<string, unknown>
    assembly.initial_azimuth_deg = invalid
    expect(() => parseProjectDocument(JSON.stringify(document))).toThrow(
      'assembly.initial_azimuth_deg must be a finite number',
    )
  })

  it.each([
    ['not json', 'valid JSON'],
    [JSON.stringify({ schema_version: '0.1' }), 'Unsupported project structure'],
    [JSON.stringify({ ...blade, blade_spec: blade, assembly: propeller.assembly }), 'Ambiguous'],
    [JSON.stringify({ blade_spec: blade }), 'both blade_spec and assembly'],
    [JSON.stringify({ ...propeller, transient_row_ids: ['not-allowed'] }), 'unsupported fields'],
  ])('rejects invalid documents atomically', (text, message) => {
    expect(() => parseProjectDocument(text)).toThrow(message)
  })
})
