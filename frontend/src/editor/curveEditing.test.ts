import { describe, expect, it } from 'vitest'
import example from '../../../examples/custom_multi_airfoil_finite_te.json'
import type { BladeSpec } from '../types/bladespec'
import {
  CURVES,
  CurveHistory,
  displayToStored,
  formatEngineeringValue,
  replaceCurvePoint,
  storedToDisplay,
  thicknessControlLock,
} from './curveEditing'

const spec = () => structuredClone(example) as BladeSpec

describe('Sprint 03C engineering units', () => {
  it('round-trips physical values without rounding at D=400 and D=720', () => {
    expect(displayToStored('chord', 64, 400)).toBe(.32)
    expect(storedToDisplay('chord', .32, 400)).toBe(64)
    expect(displayToStored('rake', -36, 720)).toBe(-.1)
    expect(storedToDisplay('skew', -.05, 720)).toBe(-18)
    expect(displayToStored('twist', 23.125, 720)).toBe(23.125)
    expect(displayToStored('thickness', 12.5, 720)).toBe(.125)
  })

  it('keeps normalized storage constant while diameter changes physical display semantics', () => {
    expect(storedToDisplay('chord', .32, 400)).toBe(64)
    expect(storedToDisplay('chord', .32, 720)).toBe(115.2)
  })

  it('formats readable engineering text without altering precise values', () => {
    const precise = 64.00000198364258
    expect(formatEngineeringValue('chord', precise)).toBe('64')
    expect(formatEngineeringValue('twist', 23.1254)).toBe('23.125')
    expect(formatEngineeringValue('thickness', 12.34567)).toBe('12.3457')
    expect(precise).toBe(64.00000198364258)
  })
})

describe('Sprint 03C curve candidates and history', () => {
  it('changes only the selected ordinate and stores chord 64 mm as 0.32', () => {
    const before = spec()
    const definition = CURVES.find(curve => curve.name === 'chord')!
    const index = before.chord_distribution.points.findIndex(point => point.r_over_R === .5)
    const after = replaceCurvePoint(before, definition, index, 64)
    expect(after.chord_distribution.points[index].chord_over_R).toBe(.32)
    expect(after.chord_distribution.points[index].r_over_R).toBe(.5)
    expect(after.twist_distribution).toEqual(before.twist_distribution)
    expect(before.chord_distribution.points[index].chord_over_R).toBe(.3)
  })

  it('allows negative rake/skew but rejects non-positive chord and thickness', () => {
    const before = spec()
    const rake = CURVES.find(curve => curve.name === 'rake')!
    const skew = CURVES.find(curve => curve.name === 'skew')!
    expect(replaceCurvePoint(before, rake, 1, -4).rake_distribution.points[1].rake_over_R).toBe(-.02)
    expect(replaceCurvePoint(before, skew, 1, -6).skew_distribution.points[1].skew_over_R).toBe(-.03)
    expect(() => replaceCurvePoint(before, CURVES[0], 1, 0)).toThrow(/greater than zero/)
    expect(() => replaceCurvePoint(before, CURVES[4], 1, -1)).toThrow(/greater than zero/)
  })

  it('protects natural NACA/imported t/c and updates an explicit NACA override atomically', () => {
    const natural = spec()
    expect(thicknessControlLock(natural, .4)).toMatch(/NACA 4412/)
    const imported = spec()
    imported.airfoil_sections[1].airfoil = { type: 'coordinates', upper: [[0, 0], [1, 0]], lower: [[0, 0], [1, 0]] }
    expect(thicknessControlLock(imported, .4)).toMatch(/imported coordinates/)
    const overridden = spec()
    overridden.airfoil_sections[1].thickness_override_ratio = .12
    const after = replaceCurvePoint(overridden, CURVES[4], 1, 13.5)
    expect(after.thickness_distribution.points[1].thickness_ratio).toBe(.135)
    expect(after.airfoil_sections[1].thickness_override_ratio).toBe(.135)
  })

  it('records one full-spec transaction, undoes/redoes, clears redo, and detects conflicts', () => {
    const before = spec()
    const after = replaceCurvePoint(before, CURVES[0], 2, 64)
    const history = new CurveHistory(50)
    history.push({ before, after, label: 'Chord control edit' })
    expect(history.undo(after)).toEqual(before)
    expect(history.redo(before)).toEqual(after)
    expect(history.undo({ ...after, name: 'unrelated' })).toBeUndefined()
    expect(history.canUndo).toBe(false)
    history.push({ before, after, label: 'first' })
    expect(history.undo(after)).toEqual(before)
    history.push({ before, after, label: 'new branch' })
    expect(history.canRedo).toBe(false)
  })
})
