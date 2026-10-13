import type { AirfoilSection, BladeSpec, Distribution } from '../types/bladespec'
import {
  addControlPoint,
  canonicalJson,
  effectiveThickness,
  hasThicknessOverride,
  updateControlPoint,
} from './bladespecEditor'
import { evaluateDistribution } from './bladespecEditor'

const EPSILON = 1e-10
export const MAX_AIRFOIL_STATIONS = 64

export type StationSetupOptions = {
  mode: 'uniform' | 'explicit'
  count: number
  explicitRadii: string
  sourceStationIndex: number
  commonTrailingEdgeMm: number
  preserveMatchingStations: boolean
  constantThicknessDistribution: boolean
}

export type StationSetupCandidate = {
  spec: BladeSpec
  radii: number[]
  retainedCount: number
  assignedCount: number
  oldThicknessPointCount: number
  newThicknessPointCount: number
  changed: boolean
}

export function uniformStationRadii(root: number, count: number): number[] {
  if (!Number.isInteger(count) || count < 2 || count > MAX_AIRFOIL_STATIONS) {
    throw new Error(`Station count must be an integer from 2 through ${MAX_AIRFOIL_STATIONS}`)
  }
  const span = 1 - root
  return Array.from({ length: count }, (_, index) => (
    index === count - 1
      ? 1
      : Number((root + span * index / (count - 1)).toPrecision(15))
  ))
}

export function parseStationRadii(text: string): number[] {
  const tokens = text.trim().split(/[\s,;]+/).filter(Boolean)
  if (tokens.length < 2) throw new Error('Provide at least root and tip r/R values')
  if (tokens.length > MAX_AIRFOIL_STATIONS) {
    throw new Error(`Station setup exceeds the ${MAX_AIRFOIL_STATIONS}-station safety limit`)
  }
  return tokens.map((token, index) => {
    const value = Number(token)
    if (!Number.isFinite(value)) throw new Error(`Station value ${index + 1} is not finite`)
    return value
  })
}

function validateRadii(radii: number[], root: number): void {
  for (let index = 1; index < radii.length; index += 1) {
    if (radii[index] <= radii[index - 1]) {
      throw new Error('Airfoil station radii must be strictly increasing with no duplicates')
    }
  }
  if (Math.abs(radii[0] - root) > EPSILON) {
    throw new Error(`First airfoil station must match project root r/R ${root}`)
  }
  if (Math.abs(radii.at(-1)! - 1) > EPSILON) {
    throw new Error('Last airfoil station must match project tip r/R 1')
  }
}

function thicknessAtTemplate(spec: BladeSpec, section: AirfoilSection): number {
  if (section.airfoil.type === 'naca4' && !hasThicknessOverride(section)) {
    return Number(section.airfoil.code.slice(2)) / 100
  }
  return effectiveThickness(spec, section)
}

function coordinateThickness(
  distribution: Distribution,
  radius: number,
  ratio: number,
): Distribution {
  const current = evaluateDistribution(distribution, 'thickness_ratio', radius)
  if (Math.abs(current - ratio) <= 1e-12) return distribution
  let next = distribution
  let index = next.points.findIndex(point => Math.abs(point.r_over_R - radius) <= EPSILON)
  if (index < 0) {
    next = addControlPoint(next, 'thickness_ratio', radius)
    index = next.points.findIndex(point => Math.abs(point.r_over_R - radius) <= EPSILON)
  }
  return updateControlPoint(next, index, { thickness_ratio: ratio })
}

export function buildStationSetupCandidate(
  snapshot: BladeSpec,
  options: StationSetupOptions,
): StationSetupCandidate {
  if (!Number.isFinite(options.commonTrailingEdgeMm) || options.commonTrailingEdgeMm < 0) {
    throw new Error('Common physical trailing-edge thickness must be finite and non-negative')
  }
  const template = snapshot.airfoil_sections[options.sourceStationIndex]
  if (!template) throw new Error('Choose an existing profile assignment')
  const radii = options.mode === 'uniform'
    ? uniformStationRadii(snapshot.root_radius_ratio, options.count)
    : parseStationRadii(options.explicitRadii)
  validateRadii(radii, snapshot.root_radius_ratio)

  let thickness = structuredClone(snapshot.thickness_distribution)
  const expectedThickness = thicknessAtTemplate(snapshot, template)
  if (options.constantThicknessDistribution) {
    thickness = {
      interpolation: snapshot.thickness_distribution.interpolation,
      points: [
        { r_over_R: snapshot.root_radius_ratio, thickness_ratio: expectedThickness },
        { r_over_R: 1, thickness_ratio: expectedThickness },
      ],
    }
  }
  let retainedCount = 0
  let assignedCount = 0
  const sections = radii.map(radius => {
    const retained = snapshot.airfoil_sections.find(
      section => Math.abs(section.r_over_R - radius) <= EPSILON,
    )
    if (options.preserveMatchingStations && retained) {
      retainedCount += 1
      return structuredClone(retained)
    }
    assignedCount += 1
    thickness = coordinateThickness(thickness, radius, expectedThickness)
    const section: AirfoilSection = {
      r_over_R: radius,
      airfoil: structuredClone(template.airfoil),
      trailing_edge_thickness_mm: options.commonTrailingEdgeMm,
    }
    if (hasThicknessOverride(template)) {
      section.thickness_override_ratio = template.thickness_override_ratio
    }
    return section
  })
  const spec = { ...snapshot, airfoil_sections: sections, thickness_distribution: thickness }
  return {
    spec,
    radii,
    retainedCount,
    assignedCount,
    oldThicknessPointCount: snapshot.thickness_distribution.points.length,
    newThicknessPointCount: thickness.points.length,
    changed: canonicalJson(spec) !== canonicalJson(snapshot),
  }
}
