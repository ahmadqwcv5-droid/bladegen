import type { BladeSpec, Distribution, Point } from '../types/bladespec'
import {
  CURVES,
  displayToStored,
  type CurveName,
  type CurveDefinition,
} from './curveEditing'

export const MAX_BULK_ROWS = 5000
const DOMAIN_EPSILON = 1e-10

export type DelimitedRow = { sourceRow: number; cells: Record<string, string> }
export type DelimitedTable = {
  sourceName: string
  delimiter: ',' | '\t'
  headers: string[]
  rows: DelimitedRow[]
}

export type ImportUnit = 'mm' | 'normalized' | 'deg' | 'percent' | 'ratio'
export type DistributionColumn = {
  column: string
  unit: ImportUnit
  interpolation: 'linear' | 'pchip'
}
export type DistributionImportPlan = {
  radialColumn: string
  selections: Partial<Record<CurveName, DistributionColumn>>
  excludedColumns: string[]
}

export type DistributionImportSummary = {
  curve: CurveName
  title: string
  column: string
  unit: ImportUnit
  interpolation: 'linear' | 'pchip'
  oldPointCount: number
  newPointCount: number
}

export type DistributionImportCandidate = {
  spec: BladeSpec
  summaries: DistributionImportSummary[]
  radialDomain: [number, number]
}

const parseCsvLine = (line: string): string[] => {
  const values: string[] = []
  let value = ''
  let quoted = false
  for (let index = 0; index < line.length; index += 1) {
    const character = line[index]
    if (quoted) {
      if (character === '"' && line[index + 1] === '"') {
        value += '"'
        index += 1
      } else if (character === '"') quoted = false
      else value += character
    } else if (character === '"') quoted = true
    else if (character === ',') { values.push(value); value = '' }
    else value += character
  }
  if (quoted) throw new Error('CSV contains an unterminated quoted field')
  values.push(value)
  return values
}

export function parseDelimitedTable(text: string, sourceName = 'Pasted spreadsheet data'): DelimitedTable {
  const normalized = text.replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n')
  const lines = normalized.split('\n').filter(line => line.trim() !== '')
  if (lines.length < 2) throw new Error('Bulk input requires a header and at least one data row')
  const delimiter: ',' | '\t' = lines[0].includes('\t') ? '\t' : ','
  const split = delimiter === '\t' ? (line: string) => line.split('\t') : parseCsvLine
  const headers = split(lines[0]).map(header => header.trim())
  if (headers.some(header => !header)) throw new Error('Every bulk-input column requires a header')
  if (new Set(headers).size !== headers.length) throw new Error('Bulk-input headers must be unique')
  const dataLines = lines.slice(1)
  if (dataLines.length > MAX_BULK_ROWS) {
    throw new Error(`Bulk input exceeds the ${MAX_BULK_ROWS}-row safety limit`)
  }
  const rows = dataLines.map((line, index) => {
    const values = split(line)
    if (values.length !== headers.length) {
      throw new Error(
        `Row ${index + 2} has ${values.length} cells; expected ${headers.length}`,
      )
    }
    return {
      sourceRow: index + 2,
      cells: Object.fromEntries(headers.map((header, cell) => [header, values[cell].trim()])),
    }
  })
  return { sourceName, delimiter, headers, rows }
}

const knownColumns: Record<string, { curve: CurveName; unit: ImportUnit }> = {
  chord_mm: { curve: 'chord', unit: 'mm' },
  chord_over_R: { curve: 'chord', unit: 'normalized' },
  twist_deg: { curve: 'twist', unit: 'deg' },
  rake_mm: { curve: 'rake', unit: 'mm' },
  rake_over_R: { curve: 'rake', unit: 'normalized' },
  skew_mm: { curve: 'skew', unit: 'mm' },
  skew_over_R: { curve: 'skew', unit: 'normalized' },
  thickness_percent: { curve: 'thickness', unit: 'percent' },
  thickness_ratio: { curve: 'thickness', unit: 'ratio' },
}

export function suggestedImportPlan(table: DelimitedTable, spec: BladeSpec): DistributionImportPlan {
  const selections: DistributionImportPlan['selections'] = {}
  for (const header of table.headers) {
    const known = knownColumns[header]
    if (!known || selections[known.curve]) continue
    const definition = CURVES.find(curve => curve.name === known.curve)!
    selections[known.curve] = {
      column: header,
      unit: known.unit,
      interpolation: spec[definition.key].interpolation,
    }
  }
  return {
    radialColumn: table.headers.includes('r_over_R') ? 'r_over_R' : '',
    selections,
    excludedColumns: [],
  }
}

export const unitsForCurve = (curve: CurveName): ImportUnit[] => {
  if (curve === 'twist') return ['deg']
  if (curve === 'thickness') return ['percent', 'ratio']
  return ['mm', 'normalized']
}

const parseFiniteCell = (row: DelimitedRow, column: string): number => {
  const raw = row.cells[column]
  if (raw === undefined || raw === '') {
    throw new Error(`Row ${row.sourceRow}, column ${column}: a value is required`)
  }
  const value = Number(raw)
  if (!Number.isFinite(value)) {
    throw new Error(`Row ${row.sourceRow}, column ${column}: ${JSON.stringify(raw)} is not finite`)
  }
  return value
}

const usedColumns = (plan: DistributionImportPlan) => new Set([
  plan.radialColumn,
  ...Object.values(plan.selections).filter(Boolean).map(selection => selection!.column),
  ...plan.excludedColumns,
  'row',
])

export function unmappedColumns(table: DelimitedTable, plan: DistributionImportPlan): string[] {
  const used = usedColumns(plan)
  return table.headers.filter(header => !used.has(header))
}

function convertValue(
  definition: CurveDefinition,
  unit: ImportUnit,
  value: number,
  diameterMm: number,
): number {
  if (definition.name === 'twist') {
    if (unit !== 'deg') throw new Error('Twist input must explicitly use degrees')
    return value
  }
  if (definition.name === 'thickness') {
    if (unit === 'percent') return value / 100
    if (unit === 'ratio') return value
    throw new Error('Thickness input must explicitly use percent or ratio')
  }
  if (unit === 'normalized') return value
  if (unit === 'mm') return displayToStored(definition.name, value, diameterMm)
  throw new Error(`${definition.title} input must explicitly use mm or normalized units`)
}

export function buildDistributionCandidate(
  snapshot: BladeSpec,
  table: DelimitedTable,
  plan: DistributionImportPlan,
): DistributionImportCandidate {
  if (!plan.radialColumn || !table.headers.includes(plan.radialColumn)) {
    throw new Error('Select the normalized r_over_R column')
  }
  const selected = CURVES.flatMap(definition => {
    const selection = plan.selections[definition.name]
    return selection ? [{ definition, selection }] : []
  })
  if (!selected.length) throw new Error('Select at least one distribution to replace')
  const unknown = unmappedColumns(table, plan)
  if (unknown.length) {
    throw new Error(`Map or explicitly exclude column(s): ${unknown.join(', ')}`)
  }

  const radii = table.rows.map(row => parseFiniteCell(row, plan.radialColumn))
  for (let index = 1; index < radii.length; index += 1) {
    if (radii[index] === radii[index - 1]) {
      throw new Error(`Rows ${table.rows[index - 1].sourceRow} and ${table.rows[index].sourceRow}: duplicate r/R ${radii[index]}`)
    }
    if (radii[index] < radii[index - 1]) {
      throw new Error('r/R values are not increasing; use the explicit Sort rows action before Apply')
    }
  }
  const root = radii[0]
  const tip = radii.at(-1)!
  if (root < 0 || tip > 1 || root >= tip) throw new Error('The normalized radial domain must increase within [0, 1]')
  if (Math.abs(root - snapshot.root_radius_ratio) > DOMAIN_EPSILON) {
    throw new Error(`Imported root r/R ${root} does not match project root ${snapshot.root_radius_ratio}`)
  }
  if (Math.abs(tip - 1) > DOMAIN_EPSILON) {
    throw new Error(`Imported tip r/R ${tip} does not match required project tip 1`)
  }

  const next = structuredClone(snapshot)
  const summaries: DistributionImportSummary[] = []
  for (const { definition, selection } of selected) {
    if (!table.headers.includes(selection.column)) {
      throw new Error(`${definition.title}: selected column ${selection.column} does not exist`)
    }
    const points: Point[] = table.rows.map((row, index) => {
      const raw = parseFiniteCell(row, selection.column)
      const stored = convertValue(definition, selection.unit, raw, snapshot.diameter_mm)
      if (!Number.isFinite(stored)) {
        throw new Error(`Row ${row.sourceRow}, column ${selection.column}: conversion is not finite`)
      }
      if (definition.positive && stored <= 0) {
        throw new Error(`Row ${row.sourceRow}, column ${selection.column}: ${definition.title} must be positive`)
      }
      return { r_over_R: radii[index], [definition.valueKey]: stored }
    })
    const old = snapshot[definition.key]
    const distribution: Distribution = { interpolation: selection.interpolation, points }
    next[definition.key] = distribution
    summaries.push({
      curve: definition.name,
      title: definition.title,
      column: selection.column,
      unit: selection.unit,
      interpolation: selection.interpolation,
      oldPointCount: old.points.length,
      newPointCount: points.length,
    })
  }
  return { spec: next, summaries, radialDomain: [root, tip] }
}

export function sortTableByRadius(table: DelimitedTable, radialColumn: string): DelimitedTable {
  if (!radialColumn) throw new Error('Select r_over_R before sorting')
  const rows = [...table.rows].sort((left, right) => (
    parseFiniteCell(left, radialColumn) - parseFiniteCell(right, radialColumn)
  ))
  return { ...table, rows }
}
