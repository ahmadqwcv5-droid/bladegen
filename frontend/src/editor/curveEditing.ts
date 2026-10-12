import type { AirfoilSection, BladeSpec, Distribution } from '../types/bladespec'

export type CurveName = 'chord' | 'twist' | 'rake' | 'skew' | 'thickness'
export type DistributionKey = 'chord_distribution' | 'twist_distribution' | 'rake_distribution' | 'skew_distribution' | 'thickness_distribution'

export type CurveDefinition = {
  name: CurveName
  key: DistributionKey
  title: string
  valueKey: string
  unit: string
  step: number
  positive: boolean
}

export const CURVES: readonly CurveDefinition[] = [
  { name: 'chord', key: 'chord_distribution', title: 'Chord', valueKey: 'chord_over_R', unit: 'mm', step: .5, positive: true },
  { name: 'twist', key: 'twist_distribution', title: 'Twist', valueKey: 'twist_deg', unit: 'deg', step: .25, positive: false },
  { name: 'rake', key: 'rake_distribution', title: 'Rake', valueKey: 'rake_over_R', unit: 'mm', step: .5, positive: false },
  { name: 'skew', key: 'skew_distribution', title: 'Skew', valueKey: 'skew_over_R', unit: 'mm', step: .5, positive: false },
  { name: 'thickness', key: 'thickness_distribution', title: 'Thickness', valueKey: 'thickness_ratio', unit: '% t/c', step: .1, positive: true },
] as const

export function bladeRadiusMm(diameterMm: number): number {
  return diameterMm / 2
}

export function storedToDisplay(curve: CurveName, stored: number, diameterMm: number): number {
  if (curve === 'twist') return stored
  if (curve === 'thickness') return stored * 100
  return stored * bladeRadiusMm(diameterMm)
}

export function displayToStored(curve: CurveName, displayed: number, diameterMm: number): number {
  if (curve === 'twist') return displayed
  if (curve === 'thickness') return displayed / 100
  return displayed / bladeRadiusMm(diameterMm)
}

export function validateDisplayValue(definition: CurveDefinition, value: number): void {
  if (!Number.isFinite(value)) throw new Error(`${definition.title} must be a finite number`)
  if (definition.positive && value <= 0) throw new Error(`${definition.title} must be greater than zero ${definition.unit}`)
}

function coincidentSection(spec: BladeSpec, radius: number): AirfoilSection | undefined {
  return spec.airfoil_sections.find(section => Math.abs(section.r_over_R - radius) <= 1e-10)
}

export function thicknessControlLock(spec: BladeSpec, radius: number): string | undefined {
  const section = coincidentSection(spec, radius)
  if (!section) return undefined
  if (section.airfoil.type === 'coordinates') {
    return 'Locked: this airfoil station uses imported coordinates, so its natural t/c is protected.'
  }
  if (typeof section.thickness_override_ratio !== 'number' || !Number.isFinite(section.thickness_override_ratio)) {
    return `Locked: NACA ${section.airfoil.code} owns t/c here. Enable its explicit thickness override first.`
  }
  return undefined
}

export function replaceCurvePoint(
  spec: BladeSpec,
  definition: CurveDefinition,
  pointIndex: number,
  displayedValue: number,
): BladeSpec {
  validateDisplayValue(definition, displayedValue)
  const distribution = spec[definition.key]
  const point = distribution.points[pointIndex]
  if (!point) throw new Error(`${definition.title} control point no longer exists`)
  if (definition.name === 'thickness') {
    const locked = thicknessControlLock(spec, point.r_over_R)
    if (locked) throw new Error(locked)
  }
  const stored = displayToStored(definition.name, displayedValue, spec.diameter_mm)
  const nextDistribution: Distribution = {
    ...distribution,
    points: distribution.points.map((candidate, index) => index === pointIndex
      ? { ...candidate, [definition.valueKey]: stored }
      : candidate),
  }
  let sections = spec.airfoil_sections
  if (definition.name === 'thickness') {
    sections = sections.map(section => (
      Math.abs(section.r_over_R - point.r_over_R) <= 1e-10
      && section.airfoil.type === 'naca4'
      && typeof section.thickness_override_ratio === 'number'
        ? { ...section, thickness_override_ratio: stored }
        : section
    ))
  }
  return { ...spec, [definition.key]: nextDistribution, airfoil_sections: sections }
}

export type CurveHistoryEntry = { before: BladeSpec; after: BladeSpec; label: string }

export class CurveHistory {
  private undoEntries: CurveHistoryEntry[] = []
  private redoEntries: CurveHistoryEntry[] = []

  constructor(private readonly limit = 50) {}

  clear(): void { this.undoEntries = []; this.redoEntries = [] }
  push(entry: CurveHistoryEntry): void {
    this.undoEntries.push(structuredClone(entry))
    if (this.undoEntries.length > this.limit) this.undoEntries.shift()
    this.redoEntries = []
  }
  get canUndo(): boolean { return this.undoEntries.length > 0 }
  get canRedo(): boolean { return this.redoEntries.length > 0 }
  get undoLabel(): string | undefined { return this.undoEntries.at(-1)?.label }
  get redoLabel(): string | undefined { return this.redoEntries.at(-1)?.label }

  undo(current: BladeSpec): BladeSpec | undefined {
    const entry = this.undoEntries.at(-1)
    if (!entry || JSON.stringify(current) !== JSON.stringify(entry.after)) { this.clear(); return undefined }
    this.undoEntries.pop()
    this.redoEntries.push(entry)
    return structuredClone(entry.before)
  }

  redo(current: BladeSpec): BladeSpec | undefined {
    const entry = this.redoEntries.at(-1)
    if (!entry || JSON.stringify(current) !== JSON.stringify(entry.before)) { this.clear(); return undefined }
    this.redoEntries.pop()
    this.undoEntries.push(entry)
    return structuredClone(entry.after)
  }
}
