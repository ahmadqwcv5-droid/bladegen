import { describe, expect, it } from 'vitest'
import example from '../../../examples/custom_multi_airfoil_finite_te.json'
import type { BladeSpec } from '../types/bladespec'
import { CurveHistory } from './curveEditing'
import {
  buildDistributionCandidate,
  parseDelimitedTable,
  sortTableByRadius,
  suggestedImportPlan,
  unmappedColumns,
} from './distributionImport'

const source = () => structuredClone(example) as BladeSpec

const x57Style = (delimiter = ',') => [
  ['row', 'r_over_R', 'chord_mm', 'twist_deg', 'rake_mm', 'skew_mm'].join(delimiter),
  ['1', '.2', '80.000000123', '30', '-2.5', '-1.25'].join(delimiter),
  ['2', '.6', '62.5', '18.25', '-1e-3', '0'].join(delimiter),
  ['3', '1', '30', '5', '1.75', '2.5'].join(delimiter),
].join('\n')

describe('Sprint 04B distribution import', () => {
  it('parses CSV and ordinary spreadsheet TSV equivalently', () => {
    const csv = parseDelimitedTable(x57Style(), 'fixture.csv')
    const tsv = parseDelimitedTable(x57Style('\t'), 'paste')
    expect(tsv.headers).toEqual(csv.headers)
    expect(tsv.rows.map(row => row.cells)).toEqual(csv.rows.map(row => row.cells))
    expect(csv.delimiter).toBe(',')
    expect(tsv.delimiter).toBe('\t')
  })

  it('replaces four selected distributions once while preserving stations and thickness', () => {
    const spec = source()
    const table = parseDelimitedTable(x57Style(), 'fixture.csv')
    const plan = suggestedImportPlan(table, spec)
    for (const selection of Object.values(plan.selections)) selection!.interpolation = 'pchip'
    const result = buildDistributionCandidate(spec, table, plan)
    expect(result.summaries.map(summary => summary.curve)).toEqual(['chord', 'twist', 'rake', 'skew'])
    expect(result.spec.chord_distribution.points).toHaveLength(3)
    expect(result.spec.chord_distribution.points[0].chord_over_R).toBe(80.000000123 / 200)
    expect(result.spec.rake_distribution.points[0].rake_over_R).toBe(-2.5 / 200)
    expect(result.spec.skew_distribution.points[0].skew_over_R).toBe(-1.25 / 200)
    expect(result.spec.twist_distribution.points[1].twist_deg).toBe(18.25)
    expect(result.spec.thickness_distribution).toEqual(spec.thickness_distribution)
    expect(result.spec.airfoil_sections).toEqual(spec.airfoil_sections)
    expect(table.headers).toContain('row')
    expect(unmappedColumns(table, plan)).toEqual([])
  })

  it('uses the reviewed diameter snapshot for physical conversion', () => {
    const table = parseDelimitedTable(x57Style())
    const small = source()
    small.diameter_mm = 400
    const large = source()
    large.diameter_mm = 720
    const smallValue = buildDistributionCandidate(small, table, suggestedImportPlan(table, small)).spec.chord_distribution.points[0].chord_over_R
    const largeValue = buildDistributionCandidate(large, table, suggestedImportPlan(table, large)).spec.chord_distribution.points[0].chord_over_R
    expect(smallValue).toBe(80.000000123 / 200)
    expect(largeValue).toBe(80.000000123 / 360)
  })

  it('supports partial replacement and independent grids in separate transactions', () => {
    const spec = source()
    const chordTable = parseDelimitedTable('r_over_R,chord_over_R\n.2,.4\n.5,.32\n1,.12')
    const chordPlan = suggestedImportPlan(chordTable, spec)
    const chord = buildDistributionCandidate(spec, chordTable, chordPlan).spec
    const twistTable = parseDelimitedTable('r_over_R\ttwist_deg\n.2\t30\n.4\t22\n.8\t10\n1\t5')
    const twist = buildDistributionCandidate(chord, twistTable, suggestedImportPlan(twistTable, chord)).spec
    expect(twist.chord_distribution.points.map(point => point.r_over_R)).toEqual([.2, .5, 1])
    expect(twist.twist_distribution.points.map(point => point.r_over_R)).toEqual([.2, .4, .8, 1])
    expect(twist.rake_distribution).toEqual(spec.rake_distribution)
  })

  it('converts explicit thickness percent and ratio without guessing', () => {
    const spec = source()
    const percent = parseDelimitedTable('r_over_R,thickness_percent\n.2,12\n1,10')
    const percentResult = buildDistributionCandidate(spec, percent, suggestedImportPlan(percent, spec)).spec
    expect(percentResult.thickness_distribution.points.map(point => point.thickness_ratio)).toEqual([.12, .1])
    const ratio = parseDelimitedTable('r_over_R,thickness_ratio\n.2,.12\n1,.1')
    const ratioResult = buildDistributionCandidate(spec, ratio, suggestedImportPlan(ratio, spec)).spec
    expect(ratioResult.thickness_distribution.points.map(point => point.thickness_ratio)).toEqual([.12, .1])
  })

  it('requires explicit exclusion for unknown columns and supports visible sorting', () => {
    const spec = source()
    const table = parseDelimitedTable('r_over_R,chord_mm,mystery\n1,30,a\n.2,80,b')
    let plan = suggestedImportPlan(table, spec)
    expect(() => buildDistributionCandidate(spec, table, plan)).toThrow(/exclude.*mystery/i)
    plan = { ...plan, excludedColumns: ['mystery'] }
    expect(() => buildDistributionCandidate(spec, table, plan)).toThrow(/Sort rows/)
    const sorted = sortTableByRadius(table, 'r_over_R')
    expect(buildDistributionCandidate(spec, sorted, plan).spec.chord_distribution.points[0].r_over_R).toBe(.2)
  })

  it.each([
    ['duplicate', 'r_over_R,chord_mm\n.2,80\n.2,70\n1,30', /duplicate/],
    ['missing', 'r_over_R,chord_mm\n.2,80\n1,', /value is required/],
    ['nonfinite', 'r_over_R,chord_mm\n.2,80\n1,NaN', /not finite/],
    ['root mismatch', 'r_over_R,chord_mm\n.21,80\n1,30', /does not match project root/],
    ['tip mismatch', 'r_over_R,chord_mm\n.2,80\n.99,30', /does not match required project tip/],
  ])('rejects %s input atomically', (_name, text, pattern) => {
    const spec = source()
    const table = parseDelimitedTable(text)
    expect(() => buildDistributionCandidate(spec, table, suggestedImportPlan(table, spec))).toThrow(pattern)
    expect(spec).toEqual(source())
  })

  it('accepts a 200-row synthetic distribution without resampling', () => {
    const spec = source()
    const rows = Array.from({ length: 200 }, (_, index) => {
      const radius = .2 + .8 * index / 199
      return `${radius},${80 - 50 * index / 199}`
    })
    const table = parseDelimitedTable(`r_over_R,chord_mm\n${rows.join('\n')}`)
    const result = buildDistributionCandidate(spec, table, suggestedImportPlan(table, spec))
    expect(result.spec.chord_distribution.points).toHaveLength(200)
    expect(result.spec.chord_distribution.points[73].r_over_R).toBe(.2 + .8 * 73 / 199)
  })

  it('is one undo/redo transaction and a no-op does not clear redo', () => {
    const spec = source()
    const table = parseDelimitedTable(x57Style())
    const after = buildDistributionCandidate(spec, table, suggestedImportPlan(table, spec)).spec
    const history = new CurveHistory()
    history.push({ before: spec, after, label: 'Bulk distribution import' })
    expect(history.undo(after)).toEqual(spec)
    expect(history.redo(spec)).toEqual(after)
  })
})
