import { describe, expect, it } from 'vitest'
import example from '../../../examples/custom_multi_airfoil_finite_te.json'
import type { BladeSpec } from '../types/bladespec'
import {
  buildStationSetupCandidate,
  parseStationRadii,
  uniformStationRadii,
} from './airfoilStationSetup'
import { evaluateDistribution } from './bladespecEditor'

const source = () => structuredClone(example) as BladeSpec

const options = (count: number) => ({
  mode: 'uniform' as const,
  count,
  explicitRadii: '',
  sourceStationIndex: 0,
  commonTrailingEdgeMm: 0,
  preserveMatchingStations: false,
  constantThicknessDistribution: false,
})

describe('Sprint 04B airfoil station setup', () => {
  it.each([
    [2, [.2, 1]],
    [3, [.2, .6, 1]],
    [5, [.2, .4, .6, .8, 1]],
    [8, [.2, .314285714285714, .428571428571429, .542857142857143, .657142857142857, .771428571428571, .885714285714286, 1]],
  ])('creates %i uniform stations including exact root and tip', (count, expected) => {
    expect(uniformStationRadii(.2, count)).toEqual(expected)
    const result = buildStationSetupCandidate(source(), options(count))
    expect(result.radii).toEqual(expected)
    expect(result.spec.airfoil_sections).toHaveLength(count)
    expect(result.spec.chord_distribution).toEqual(source().chord_distribution)
  })

  it('accepts explicit nonuniform radii and common physical TE', () => {
    const spec = source()
    const result = buildStationSetupCandidate(spec, {
      ...options(2),
      mode: 'explicit',
      explicitRadii: '.2, .31\n.73 1',
      commonTrailingEdgeMm: .125,
    })
    expect(result.radii).toEqual([.2, .31, .73, 1])
    expect(result.spec.airfoil_sections.every(section => section.trailing_edge_thickness_mm === .125)).toBe(true)
  })

  it('preserves matching complete assignments when explicitly requested', () => {
    const spec = source()
    const result = buildStationSetupCandidate(spec, {
      ...options(5),
      preserveMatchingStations: true,
      commonTrailingEdgeMm: 99,
    })
    expect(result.retainedCount).toBe(5)
    expect(result.spec.airfoil_sections).toEqual(spec.airfoil_sections)
  })

  it('coordinates a selected coordinate profile natural thickness at all assigned stations', () => {
    const spec = source()
    const coordinateIndex = 1
    spec.airfoil_sections[coordinateIndex].airfoil = {
      type: 'coordinates',
      upper: [[0, 0], [.5, .06], [1, 0]],
      lower: [[0, 0], [.5, -.06], [1, 0]],
    }
    delete spec.airfoil_sections[coordinateIndex].thickness_override_ratio
    const sourceRatio = evaluateDistribution(spec.thickness_distribution, 'thickness_ratio', spec.airfoil_sections[coordinateIndex].r_over_R)
    const result = buildStationSetupCandidate(spec, {
      ...options(3),
      sourceStationIndex: coordinateIndex,
    })
    for (const section of result.spec.airfoil_sections) {
      expect(section.airfoil.type).toBe('coordinates')
      expect(evaluateDistribution(result.spec.thickness_distribution, 'thickness_ratio', section.r_over_R)).toBeCloseTo(sourceRatio, 12)
    }
  })

  it('retains a valid explicit NACA override and coordinates its curve', () => {
    const spec = source()
    spec.airfoil_sections[0].thickness_override_ratio = .15
    spec.thickness_distribution.points[0].thickness_ratio = .15
    const result = buildStationSetupCandidate(spec, options(3))
    expect(result.spec.airfoil_sections.every(section => section.thickness_override_ratio === .15)).toBe(true)
    for (const section of result.spec.airfoil_sections) {
      expect(evaluateDistribution(result.spec.thickness_distribution, 'thickness_ratio', section.r_over_R)).toBeCloseTo(.15, 12)
    }
  })

  it('replaces thickness with an explicitly reviewed two-point constant only when selected', () => {
    const spec = source()
    const preserved = buildStationSetupCandidate(spec, options(2))
    expect(preserved.spec.thickness_distribution.points).toHaveLength(5)
    const constant = buildStationSetupCandidate(spec, {
      ...options(2), constantThicknessDistribution: true,
    })
    expect(constant.spec.thickness_distribution.points).toEqual([
      { r_over_R: .2, thickness_ratio: .15 },
      { r_over_R: 1, thickness_ratio: .15 },
    ])
  })

  it.each([
    ['', /at least root and tip/],
    ['.2,.5,.5,1', /strictly increasing/],
    ['.21,.5,1', /match project root/],
    ['.2,.5,.99', /match project tip/],
  ])('rejects invalid explicit list %s', (text, pattern) => {
    const spec = source()
    expect(() => buildStationSetupCandidate(spec, {
      ...options(2), mode: 'explicit', explicitRadii: text,
    })).toThrow(pattern)
  })

  it('parses scientific notation without changing values', () => {
    expect(parseStationRadii('2e-1\n5e-1\n1e0')).toEqual([.2, .5, 1])
  })
})
