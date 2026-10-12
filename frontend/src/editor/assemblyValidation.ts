import type { AssemblySpec, BladeSpec, NominalHubGuidance } from '../types/bladespec'

export function nominalHubGuidance(spec: BladeSpec, assembly: AssemblySpec): NominalHubGuidance {
  const rootRadius = spec.diameter_mm / 2 * spec.root_radius_ratio
  const hubRadius = assembly.hub_diameter_mm / 2
  const difference = hubRadius - rootRadius
  return {
    root_radius_mm: rootRadius,
    hub_radius_mm: hubRadius,
    nominal_radial_overlap_mm: Math.max(difference, 0),
    nominal_radial_gap_mm: Math.max(-difference, 0),
    required_hub_diameter_bound_mm: spec.diameter_mm * spec.root_radius_ratio,
    bound_is_exclusive: true,
    passes_nominal_policy: difference > 0,
  }
}
