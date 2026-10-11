import { describe, expect, it } from 'vitest'
import example from '../../../examples/custom_multi_airfoil_finite_te.json'
import {
  addAirfoilStation,
  addControlPoint,
  canonicalJson,
  changeRootRadius,
  clearThicknessOverride,
  coordinateNacaThickness,
  effectiveThickness,
  hasThicknessOverride,
  parseBladeSpec,
  removeAirfoilStation,
  removeControlPoint,
  setThicknessOverride,
  validateEditorSpec,
} from './bladespecEditor'
import type { BladeSpec } from '../types/bladespec'

const source = () => structuredClone(example) as BladeSpec

describe('BladeSpec engineering editor', () => {
  it('adds and removes an airfoil station without leaking row metadata', () => {
    const added = addAirfoilStation(source(), .7, '0012')
    expect(added.airfoil_sections).toHaveLength(6)
    expect(added.airfoil_sections[3].r_over_R).toBe(.7)
    expect(removeAirfoilStation(added, 3).airfoil_sections).toHaveLength(5)
    expect(canonicalJson(added)).not.toContain('rowId')
  })

  it('rejects a duplicate airfoil radius', () => {
    expect(() => addAirfoilStation(source(), .6)).toThrow(/already exists/)
  })

  it('synchronizes root and all independent distribution roots', () => {
    const next = changeRootRadius(source(), .18)
    expect(next.airfoil_sections[0].r_over_R).toBe(.18)
    for (const key of ['chord_distribution', 'twist_distribution', 'rake_distribution', 'skew_distribution', 'thickness_distribution'] as const) {
      expect(next[key].points[0].r_over_R).toBe(.18)
    }
  })

  it('edits independent curve point counts and preserves interpolation', () => {
    const spec = source()
    const chord = addControlPoint(spec.chord_distribution, 'chord_over_R', .425)
    expect(chord.points).toHaveLength(7)
    expect(chord.interpolation).toBe('pchip')
    expect(removeControlPoint(chord, 2).points).toHaveLength(6)
    expect(spec.twist_distribution.points).toHaveLength(6)
  })

  it('treats null and omitted overrides as absent and numbers as explicit', () => {
    const spec = source()
    spec.airfoil_sections[0].thickness_override_ratio = null
    delete spec.airfoil_sections[1].thickness_override_ratio
    spec.airfoil_sections[2].thickness_override_ratio = .12
    expect(hasThicknessOverride(spec.airfoil_sections[0])).toBe(false)
    expect(hasThicknessOverride(spec.airfoil_sections[1])).toBe(false)
    expect(hasThicknessOverride(spec.airfoil_sections[2])).toBe(true)
  })

  it('coordinates null-override NACA 0010 to 0008 without changing physical TE', () => {
    const spec = source()
    const index = spec.airfoil_sections.length - 1
    spec.airfoil_sections[index].thickness_override_ratio = null
    const trailingEdge = spec.airfoil_sections[index].trailing_edge_thickness_mm
    expect(effectiveThickness(spec, spec.airfoil_sections[index])).toBeCloseTo(.10)
    const coordinated = coordinateNacaThickness(spec, index, '0008')
    expect(effectiveThickness(coordinated, coordinated.airfoil_sections[index])).toBeCloseTo(.08)
    expect(coordinated.thickness_distribution.points.at(-1)?.thickness_ratio).toBeCloseTo(.08)
    expect(coordinated.airfoil_sections[index].trailing_edge_thickness_mm).toBe(trailingEdge)
    expect(validateEditorSpec(coordinated)).toEqual([])
  })

  it('enables and disables an override while restoring nominal NACA semantics', () => {
    const spec = coordinateNacaThickness(source(), source().airfoil_sections.length - 1, '0008')
    const index = spec.airfoil_sections.length - 1
    const overridden = setThicknessOverride(spec, index, .10)
    expect(hasThicknessOverride(overridden.airfoil_sections[index])).toBe(true)
    expect(effectiveThickness(overridden, overridden.airfoil_sections[index])).toBeCloseTo(.10)
    expect(overridden.thickness_distribution.points.at(-1)?.thickness_ratio).toBeCloseTo(.10)
    const restored = clearThicknessOverride(overridden, index)
    expect(hasThicknessOverride(restored.airfoil_sections[index])).toBe(false)
    expect(effectiveThickness(restored, restored.airfoil_sections[index])).toBeCloseTo(.08)
    expect(restored.thickness_distribution.points.at(-1)?.thickness_ratio).toBeCloseTo(.08)
    expect(validateEditorSpec(restored)).toEqual([])
  })

  it('coordinates an explicit thickness override with its radial curve value', () => {
    const spec = source()
    const index = 1
    const radius = spec.airfoil_sections[index].r_over_R
    spec.thickness_distribution.points = spec.thickness_distribution.points.filter(point => point.r_over_R !== radius)
    const next = setThicknessOverride(spec, index, .105)
    expect(next.airfoil_sections[index].thickness_override_ratio).toBe(.105)
    expect(next.thickness_distribution.points.find(point => point.r_over_R === radius)?.thickness_ratio).toBe(.105)
    expect(validateEditorSpec(next)).toEqual([])
  })

  it('round-trips null, omitted, and numeric override semantics through neutral JSON', () => {
    const spec = source()
    spec.airfoil_sections[0].thickness_override_ratio = null
    delete spec.airfoil_sections[1].thickness_override_ratio
    spec.airfoil_sections[2].thickness_override_ratio = .12
    const parsed = parseBladeSpec(canonicalJson(spec))
    expect(parsed.airfoil_sections[0].thickness_override_ratio).toBeNull()
    expect(Object.hasOwn(parsed.airfoil_sections[1], 'thickness_override_ratio')).toBe(false)
    expect(parsed.airfoil_sections[2].thickness_override_ratio).toBe(.12)
  })

  it('detects changed input snapshots', () => {
    const before = source()
    const snapshot = canonicalJson(before)
    expect(canonicalJson({ ...before, name: 'changed' })).not.toBe(snapshot)
  })
})
