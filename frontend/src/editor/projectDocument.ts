import { parseBladeSpec } from './bladespecEditor'
import type { AssemblySpec, BladeSpec, PropellerSpec } from '../types/bladespec'

export const DEFAULT_ASSEMBLY: AssemblySpec = {
  blade_count: 3,
  hub_diameter_mm: 90,
  hub_length_mm: 45,
  shaft_bore_diameter_mm: 12,
  initial_azimuth_deg: 0,
}

export type ProjectDocument = {
  kind: 'blade' | 'propeller'
  bladeSpec: BladeSpec
  assembly: AssemblySpec
  propellerName: string
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function finite(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function rejectUnknownKeys(value: Record<string, unknown>, allowed: string[], label: string) {
  const unknown = Object.keys(value).filter(key => !allowed.includes(key))
  if (unknown.length) throw new Error(`${label} contains unsupported fields: ${unknown.join(', ')}`)
}

function parseAssembly(value: unknown): AssemblySpec {
  if (!isRecord(value)) throw new Error('PropellerSpec requires a complete assembly object')
  rejectUnknownKeys(value, [
    'blade_count', 'hub_diameter_mm', 'hub_length_mm',
    'shaft_bore_diameter_mm', 'initial_azimuth_deg',
  ], 'assembly')
  if (!Number.isInteger(value.blade_count)) throw new Error('assembly.blade_count must be an integer')
  for (const field of ['hub_diameter_mm', 'hub_length_mm', 'shaft_bore_diameter_mm']) {
    if (!finite(value[field])) throw new Error(`assembly.${field} must be a finite number`)
  }
  const initialAzimuth = 'initial_azimuth_deg' in value ? value.initial_azimuth_deg : 0
  if (!finite(initialAzimuth)) throw new Error('assembly.initial_azimuth_deg must be a finite number')
  return {
    blade_count: value.blade_count as number,
    hub_diameter_mm: value.hub_diameter_mm as number,
    hub_length_mm: value.hub_length_mm as number,
    shaft_bore_diameter_mm: value.shaft_bore_diameter_mm as number,
    initial_azimuth_deg: initialAzimuth,
  }
}

export function bladeProject(bladeSpec: BladeSpec): ProjectDocument {
  return {
    kind: 'blade',
    bladeSpec: structuredClone(bladeSpec),
    assembly: structuredClone(DEFAULT_ASSEMBLY),
    propellerName: `${bladeSpec.name}_propeller`,
  }
}

export function parseProjectDocument(text: string): ProjectDocument {
  let value: unknown
  try {
    value = JSON.parse(text)
  } catch {
    throw new Error('File is not valid JSON')
  }
  if (!isRecord(value)) throw new Error('Project file must contain a JSON object')
  const hasPropellerStructure = 'blade_spec' in value || 'assembly' in value
  const hasBladeStructure = 'diameter_mm' in value || 'airfoil_sections' in value
  if (hasPropellerStructure && hasBladeStructure) {
    throw new Error('Ambiguous project structure mixes BladeSpec and PropellerSpec fields')
  }
  if (hasPropellerStructure) {
    if (!('blade_spec' in value) || !('assembly' in value)) {
      throw new Error('Incomplete PropellerSpec requires both blade_spec and assembly')
    }
    if (value.schema_version !== '0.1') throw new Error('Unsupported PropellerSpec schema_version')
    if (typeof value.name !== 'string' || !value.name.trim()) throw new Error('PropellerSpec name is required')
    if (value.units !== 'mm') throw new Error('PropellerSpec units must be mm')
    rejectUnknownKeys(value, ['schema_version', 'name', 'units', 'blade_spec', 'assembly'], 'PropellerSpec')
    const bladeSpec = parseBladeSpec(JSON.stringify(value.blade_spec))
    return {
      kind: 'propeller',
      bladeSpec,
      assembly: parseAssembly(value.assembly),
      propellerName: value.name,
    }
  }
  if (hasBladeStructure) return bladeProject(parseBladeSpec(text))
  throw new Error('Unsupported project structure; expected BladeSpec or PropellerSpec')
}

export function propellerFromProject(project: ProjectDocument): PropellerSpec {
  return {
    schema_version: '0.1',
    name: project.propellerName,
    units: 'mm',
    blade_spec: project.bladeSpec,
    assembly: project.assembly,
  }
}
