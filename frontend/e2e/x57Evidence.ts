import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import type { BladeSpec, CoordinateAirfoil, Distribution } from '../src/types/bladespec'

export const X57_FIXTURE_DIR = fileURLToPath(
  new URL('../../fixtures/x57_manual_reference/', import.meta.url),
)

const DECIMAL_NUMBER = /^[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eE][+-]?\d+)?$/
const EXPECTED_PROJECT_NAME = 'X57_HLP_manual_test'

type NumericRow = Record<string, number>
type Coordinate = [number, number]

type X57Manifest = {
  diameter_mm: number
  radius_mm: number
  root_r_over_R: number
  reference_axis_x_over_c: number
  rotation_direction: 'normal'
  airfoil_station_count: number
  points_upper: number
  points_lower: number
  source_thickness_ratio: number
  source_physical_te_mm: number
  control_points_per_distribution: Record<'chord' | 'twist' | 'rake' | 'skew', number>
}

export type X57FixtureData = {
  root: string
  manifest: X57Manifest
  physicalControls: NumericRow[]
  normalizedControls: NumericRow[]
  airfoil: CoordinateAirfoil
  productThicknessRatio: number
  sha256: Record<string, string>
}

export type X57DistributionFidelity = {
  interpolation: 'pchip'
  point_count: number
  exact_radius_matches_physical_sheet: number
  exact_value_matches_physical_conversion: number
  max_radius_error_vs_physical_sheet: number
  max_radius_error_vs_normalized_sheet: number
  max_stored_value_error_vs_physical_conversion: number
  max_stored_value_error_vs_normalized_sheet: number
  max_physical_roundtrip_error_mm: number | null
  max_twist_roundtrip_error_deg: number | null
}

export type X57CandidateFidelity = {
  passed: true
  fixture_sha256: Record<string, string>
  globals: {
    schema_version: '0.2'
    name: string
    units: 'mm'
    diameter_mm: number
    radius_mm: number
    root_r_over_R: number
    reference_axis_x_over_c: number
    rotation_direction: 'normal'
  }
  airfoil: {
    station_count: number
    upper_points_per_station: number
    lower_points_per_station: number
    coordinate_pairs_compared: number
    exact_coordinate_pairs: number
    maximum_coordinate_abs_error: number
    trailing_edge_thickness_mm: number
  }
  distributions: Record<'chord' | 'twist' | 'rake' | 'skew', X57DistributionFidelity>
  thickness_representation: {
    interpolation: 'linear'
    point_count: 2
    product_geometric_ratio: number
    source_native_ratio: number
    product_minus_source_ratio: number
    product_minus_source_percentage_points: number
    maximum_export_error_vs_product_ratio: number
    source_and_product_are_numerically_identical: false
  }
}

function fail(message: string): never {
  throw new Error(`X-57 exported-candidate fidelity mismatch: ${message}`)
}

function requireCondition(condition: unknown, message: string): asserts condition {
  if (!condition) fail(message)
}

function requireExact(actual: unknown, expected: unknown, label: string): void {
  if (!Object.is(actual, expected)) {
    fail(`${label}: expected ${JSON.stringify(expected)}, received ${JSON.stringify(actual)}`)
  }
}

function parseCsvLine(line: string, lineNumber: number): string[] {
  const values: string[] = []
  let value = ''
  let quoted = false
  let quoteClosed = false
  for (let index = 0; index < line.length; index += 1) {
    const character = line[index]
    if (quoted) {
      if (character === '"' && line[index + 1] === '"') {
        value += '"'
        index += 1
      } else if (character === '"') {
        quoted = false
        quoteClosed = true
      } else {
        value += character
      }
    } else if (quoteClosed) {
      if (character !== ',') fail(`fixture CSV line ${lineNumber}: unexpected character after quote`)
      values.push(value)
      value = ''
      quoteClosed = false
    } else if (character === '"') {
      if (value.length) fail(`fixture CSV line ${lineNumber}: quote inside unquoted field`)
      quoted = true
    } else if (character === ',') {
      values.push(value)
      value = ''
    } else {
      value += character
    }
  }
  if (quoted) fail(`fixture CSV line ${lineNumber}: unterminated quoted field`)
  values.push(value)
  return values
}

function parseCsv(text: string, label: string): Record<string, string>[] {
  const lines = text.replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n')
    .split('\n')
    .filter(line => line.trim() !== '')
  requireCondition(lines.length >= 2, `${label}: expected a header and data rows`)
  const headers = parseCsvLine(lines[0], 1).map(value => value.trim())
  requireCondition(headers.every(Boolean), `${label}: blank header`)
  requireCondition(new Set(headers).size === headers.length, `${label}: duplicate header`)
  return lines.slice(1).map((line, index) => {
    const cells = parseCsvLine(line, index + 2)
    requireCondition(
      cells.length === headers.length,
      `${label} line ${index + 2}: expected ${headers.length} cells, received ${cells.length}`,
    )
    return Object.fromEntries(headers.map((header, cell) => [header, cells[cell].trim()]))
  })
}

function numeric(value: string | undefined, label: string): number {
  requireCondition(value !== undefined && DECIMAL_NUMBER.test(value), `${label}: invalid decimal value`)
  const result = Number(value)
  requireCondition(Number.isFinite(result), `${label}: non-finite value`)
  return result
}

function numericRows(
  text: string,
  label: string,
  expectedHeaders: string[],
): NumericRow[] {
  const rows = parseCsv(text, label)
  return rows.map((row, rowIndex) => {
    requireCondition(
      Object.keys(row).length === expectedHeaders.length
        && expectedHeaders.every(header => Object.hasOwn(row, header)),
      `${label}: unexpected columns`,
    )
    return Object.fromEntries(expectedHeaders.map(header => [
      header,
      numeric(row[header], `${label} row ${rowIndex + 1}, ${header}`),
    ]))
  })
}

function sha256(content: Buffer): string {
  return createHash('sha256').update(content).digest('hex')
}

function loadAndVerifyChecksums(root: string): Record<string, string> {
  const rows = readFileSync(`${root}/SHA256SUMS.txt`, 'utf8')
    .replace(/\r\n?/g, '\n')
    .split('\n')
    .filter(Boolean)
  const result: Record<string, string> = {}
  for (const row of rows) {
    const match = /^([0-9a-f]{64})  ([^/]+)$/.exec(row)
    requireCondition(match, `SHA256SUMS.txt contains an invalid entry: ${JSON.stringify(row)}`)
    const [, expected, filename] = match
    const actual = sha256(readFileSync(`${root}/${filename}`))
    requireExact(actual, expected, `SHA-256 ${filename}`)
    result[filename] = actual
  }
  return result
}

function surfaceEnvelope(points: Coordinate[], upper: boolean): Coordinate[] {
  const buckets = new Map<number, number[]>()
  for (const [x, y] of points) buckets.set(x, [...(buckets.get(x) ?? []), y])
  return [...buckets.entries()]
    .sort(([left], [right]) => left - right)
    .map(([x, values]) => [x, (upper ? Math.max : Math.min)(...values)])
}

function interpolate(points: Coordinate[], x: number): number {
  if (x <= points[0][0]) return points[0][1]
  if (x >= points.at(-1)![0]) return points.at(-1)![1]
  let right = 1
  while (points[right][0] < x) right += 1
  const [leftX, leftY] = points[right - 1]
  const [rightX, rightY] = points[right]
  return leftY + (x - leftX) * (rightY - leftY) / (rightX - leftX)
}

function measureProductThickness(airfoil: CoordinateAirfoil): number {
  const upper = surfaceEnvelope(airfoil.upper as Coordinate[], true)
  const lower = surfaceEnvelope(airfoil.lower as Coordinate[], false)
  const start = Math.max(upper[0][0], lower[0][0])
  const end = Math.min(upper.at(-1)![0], lower.at(-1)![0])
  requireCondition(end - start > 1e-9, 'airfoil surfaces do not share a usable domain')
  let maximum = Number.NEGATIVE_INFINITY
  for (let index = 0; index < 2001; index += 1) {
    const x = start + (end - start) * index / 2000
    maximum = Math.max(maximum, interpolate(upper, x) - interpolate(lower, x))
  }
  return maximum
}

export function loadX57FixtureData(root = X57_FIXTURE_DIR): X57FixtureData {
  const sha = loadAndVerifyChecksums(root)
  const manifest = JSON.parse(readFileSync(`${root}/manifest.json`, 'utf8')) as X57Manifest
  requireCondition(Number.isFinite(manifest.diameter_mm), 'manifest diameter is invalid')
  requireExact(manifest.radius_mm, manifest.diameter_mm / 2, 'manifest radius')

  const physicalHeaders = ['row', 'r_over_R', 'chord_mm', 'twist_deg', 'rake_mm', 'skew_mm']
  const normalizedHeaders = [
    'row', 'r_over_R', 'chord_over_R', 'twist_deg', 'rake_over_R', 'skew_over_R',
  ]
  const physicalControls = numericRows(
    readFileSync(`${root}/x57_hlp_control_points_mm.csv`, 'utf8'),
    'physical control fixture',
    physicalHeaders,
  )
  const normalizedControls = numericRows(
    readFileSync(`${root}/x57_hlp_control_points_normalized.csv`, 'utf8'),
    'normalized control fixture',
    normalizedHeaders,
  )
  requireExact(physicalControls.length, 40, 'physical fixture row count')
  requireExact(normalizedControls.length, 40, 'normalized fixture row count')
  for (let index = 0; index < physicalControls.length; index += 1) {
    requireExact(physicalControls[index].row, index + 1, `physical fixture row ${index + 1} identity`)
    requireExact(normalizedControls[index].row, index + 1, `normalized fixture row ${index + 1} identity`)
  }

  const airfoilRows = parseCsv(
    readFileSync(`${root}/x57_hlp_airfoil.csv`, 'utf8'),
    'airfoil fixture',
  )
  const coordinates = (surface: 'upper' | 'lower'): Coordinate[] => airfoilRows
    .filter(row => row.surface === surface)
    .map((row, index) => [
      numeric(row.x, `${surface} coordinate ${index + 1} x`),
      numeric(row.y, `${surface} coordinate ${index + 1} y`),
    ])
  requireCondition(
    airfoilRows.every(row => row.surface === 'upper' || row.surface === 'lower'),
    'airfoil fixture contains an unsupported surface label',
  )
  const airfoil: CoordinateAirfoil = {
    type: 'coordinates',
    upper: coordinates('upper'),
    lower: coordinates('lower'),
  }
  requireExact(airfoil.upper.length, manifest.points_upper, 'upper airfoil point count')
  requireExact(airfoil.lower.length, manifest.points_lower, 'lower airfoil point count')
  const productThicknessRatio = measureProductThickness(airfoil)
  requireCondition(
    Math.abs(productThicknessRatio - 0.1305533776828919) <= 1e-15,
    `product thickness measurement changed: ${productThicknessRatio}`,
  )

  return {
    root,
    manifest,
    physicalControls,
    normalizedControls,
    airfoil,
    productThicknessRatio,
    sha256: sha,
  }
}

function maximum(values: number[]): number {
  return values.length ? Math.max(...values) : 0
}

function compareAirfoil(
  actual: CoordinateAirfoil,
  expected: CoordinateAirfoil,
  station: number,
): { pairs: number; exact: number; errors: number[] } {
  const result = { pairs: 0, exact: 0, errors: [] as number[] }
  for (const surface of ['upper', 'lower'] as const) {
    requireExact(actual[surface].length, expected[surface].length, `station ${station} ${surface} count`)
    for (let index = 0; index < expected[surface].length; index += 1) {
      const candidate = actual[surface][index]
      const source = expected[surface][index]
      requireCondition(Array.isArray(candidate) && candidate.length === 2, `station ${station} ${surface} point ${index + 1}`)
      const errors = [Math.abs(candidate[0] - source[0]), Math.abs(candidate[1] - source[1])]
      result.pairs += 1
      if (errors[0] === 0 && errors[1] === 0) result.exact += 1
      result.errors.push(...errors)
      requireExact(candidate[0], source[0], `station ${station} ${surface} point ${index + 1} x`)
      requireExact(candidate[1], source[1], `station ${station} ${surface} point ${index + 1} y`)
    }
  }
  return result
}

type DistributionContract = {
  name: 'chord' | 'twist' | 'rake' | 'skew'
  distributionKey: 'chord_distribution' | 'twist_distribution' | 'rake_distribution' | 'skew_distribution'
  candidateValueKey: string
  physicalKey: string
  normalizedKey: string
  physical: boolean
}

const DISTRIBUTIONS: DistributionContract[] = [
  { name: 'chord', distributionKey: 'chord_distribution', candidateValueKey: 'chord_over_R', physicalKey: 'chord_mm', normalizedKey: 'chord_over_R', physical: true },
  { name: 'twist', distributionKey: 'twist_distribution', candidateValueKey: 'twist_deg', physicalKey: 'twist_deg', normalizedKey: 'twist_deg', physical: false },
  { name: 'rake', distributionKey: 'rake_distribution', candidateValueKey: 'rake_over_R', physicalKey: 'rake_mm', normalizedKey: 'rake_over_R', physical: true },
  { name: 'skew', distributionKey: 'skew_distribution', candidateValueKey: 'skew_over_R', physicalKey: 'skew_mm', normalizedKey: 'skew_over_R', physical: true },
]

function compareDistribution(
  distribution: Distribution,
  contract: DistributionContract,
  fixture: X57FixtureData,
): X57DistributionFidelity {
  requireExact(distribution.interpolation, 'pchip', `${contract.name} interpolation`)
  requireExact(distribution.points.length, 40, `${contract.name} point count`)
  const radiusPhysicalErrors: number[] = []
  const radiusNormalizedErrors: number[] = []
  const storedPhysicalErrors: number[] = []
  const storedNormalizedErrors: number[] = []
  const roundtripErrors: number[] = []
  let exactRadii = 0
  let exactValues = 0
  for (let index = 0; index < distribution.points.length; index += 1) {
    const point = distribution.points[index]
    const physical = fixture.physicalControls[index]
    const normalized = fixture.normalizedControls[index]
    const expectedRadius = physical.r_over_R
    const expectedStored = contract.physical
      ? physical[contract.physicalKey] / fixture.manifest.radius_mm
      : physical[contract.physicalKey]
    const actual = point[contract.candidateValueKey]
    requireCondition(Number.isFinite(actual), `${contract.name} point ${index + 1} is non-finite`)
    radiusPhysicalErrors.push(Math.abs(point.r_over_R - expectedRadius))
    radiusNormalizedErrors.push(Math.abs(point.r_over_R - normalized.r_over_R))
    storedPhysicalErrors.push(Math.abs(actual - expectedStored))
    storedNormalizedErrors.push(Math.abs(actual - normalized[contract.normalizedKey]))
    roundtripErrors.push(Math.abs(
      (contract.physical ? actual * fixture.manifest.radius_mm : actual)
      - physical[contract.physicalKey],
    ))
    if (Object.is(point.r_over_R, expectedRadius)) exactRadii += 1
    if (Object.is(actual, expectedStored)) exactValues += 1
    requireExact(point.r_over_R, expectedRadius, `${contract.name} point ${index + 1} radius`)
    requireExact(actual, expectedStored, `${contract.name} point ${index + 1} value`)
  }
  return {
    interpolation: 'pchip',
    point_count: distribution.points.length,
    exact_radius_matches_physical_sheet: exactRadii,
    exact_value_matches_physical_conversion: exactValues,
    max_radius_error_vs_physical_sheet: maximum(radiusPhysicalErrors),
    max_radius_error_vs_normalized_sheet: maximum(radiusNormalizedErrors),
    max_stored_value_error_vs_physical_conversion: maximum(storedPhysicalErrors),
    max_stored_value_error_vs_normalized_sheet: maximum(storedNormalizedErrors),
    max_physical_roundtrip_error_mm: contract.physical ? maximum(roundtripErrors) : null,
    max_twist_roundtrip_error_deg: contract.physical ? null : maximum(roundtripErrors),
  }
}

export function verifyX57ExportedCandidate(
  candidate: BladeSpec,
  fixture = loadX57FixtureData(),
): X57CandidateFidelity {
  const manifest = fixture.manifest
  requireExact(candidate.schema_version, '0.2', 'schema_version')
  requireExact(candidate.name, EXPECTED_PROJECT_NAME, 'project name')
  requireExact(candidate.units, 'mm', 'units')
  requireExact(candidate.diameter_mm, manifest.diameter_mm, 'diameter_mm')
  requireExact(candidate.root_radius_ratio, manifest.root_r_over_R, 'root_radius_ratio')
  requireExact(candidate.reference_axis_x_over_c, manifest.reference_axis_x_over_c, 'reference_axis_x_over_c')
  requireExact(candidate.rotation_direction, manifest.rotation_direction, 'rotation_direction')

  requireExact(candidate.airfoil_sections.length, manifest.airfoil_station_count, 'airfoil station count')
  const coordinateErrors: number[] = []
  let coordinatePairs = 0
  let exactCoordinatePairs = 0
  candidate.airfoil_sections.forEach((section, index) => {
    requireExact(section.r_over_R, index === 0 ? manifest.root_r_over_R : 1, `station ${index + 1} radius`)
    requireExact(section.trailing_edge_thickness_mm, manifest.source_physical_te_mm, `station ${index + 1} TE`)
    requireCondition(!Object.hasOwn(section, 'thickness_override_ratio'), `station ${index + 1} contains a thickness override`)
    requireExact(section.airfoil.type, 'coordinates', `station ${index + 1} profile type`)
    const result = compareAirfoil(section.airfoil as CoordinateAirfoil, fixture.airfoil, index + 1)
    coordinatePairs += result.pairs
    exactCoordinatePairs += result.exact
    coordinateErrors.push(...result.errors)
  })

  const distributions = Object.fromEntries(DISTRIBUTIONS.map(contract => [
    contract.name,
    compareDistribution(candidate[contract.distributionKey], contract, fixture),
  ])) as X57CandidateFidelity['distributions']

  requireExact(candidate.thickness_distribution.interpolation, 'linear', 'thickness interpolation')
  requireExact(candidate.thickness_distribution.points.length, 2, 'thickness point count')
  const thicknessErrors = candidate.thickness_distribution.points.map((point, index) => {
    requireExact(point.r_over_R, index === 0 ? manifest.root_r_over_R : 1, `thickness point ${index + 1} radius`)
    requireExact(point.thickness_ratio, fixture.productThicknessRatio, `thickness point ${index + 1} product ratio`)
    return Math.abs(point.thickness_ratio - fixture.productThicknessRatio)
  })
  const thicknessDelta = fixture.productThicknessRatio - manifest.source_thickness_ratio
  requireCondition(thicknessDelta !== 0, 'source and product thickness representations unexpectedly became identical')

  return {
    passed: true,
    fixture_sha256: fixture.sha256,
    globals: {
      schema_version: '0.2',
      name: candidate.name,
      units: 'mm',
      diameter_mm: candidate.diameter_mm,
      radius_mm: manifest.radius_mm,
      root_r_over_R: candidate.root_radius_ratio,
      reference_axis_x_over_c: candidate.reference_axis_x_over_c,
      rotation_direction: 'normal',
    },
    airfoil: {
      station_count: candidate.airfoil_sections.length,
      upper_points_per_station: fixture.airfoil.upper.length,
      lower_points_per_station: fixture.airfoil.lower.length,
      coordinate_pairs_compared: coordinatePairs,
      exact_coordinate_pairs: exactCoordinatePairs,
      maximum_coordinate_abs_error: maximum(coordinateErrors),
      trailing_edge_thickness_mm: manifest.source_physical_te_mm,
    },
    distributions,
    thickness_representation: {
      interpolation: 'linear',
      point_count: 2,
      product_geometric_ratio: fixture.productThicknessRatio,
      source_native_ratio: manifest.source_thickness_ratio,
      product_minus_source_ratio: thicknessDelta,
      product_minus_source_percentage_points: thicknessDelta * 100,
      maximum_export_error_vs_product_ratio: maximum(thicknessErrors),
      source_and_product_are_numerically_identical: false,
    },
  }
}

export function percentile(values: number[], fraction: number): number {
  requireCondition(values.length > 0, 'percentile requires at least one value')
  requireCondition(values.every(Number.isFinite), 'percentile values must be finite')
  requireCondition(Number.isFinite(fraction) && fraction >= 0 && fraction <= 1, 'percentile fraction must be in [0, 1]')
  const sorted = [...values].sort((left, right) => left - right)
  const position = (sorted.length - 1) * fraction
  const lower = Math.floor(position)
  const upper = Math.ceil(position)
  return sorted[lower] + (sorted[upper] - sorted[lower]) * (position - lower)
}
