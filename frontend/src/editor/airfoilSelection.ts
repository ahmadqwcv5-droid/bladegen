import type { AirfoilProfile, BladeSpec, CoordinateAirfoil } from '../types/bladespec'
import { addControlPoint, coordinateNacaThickness, updateControlPoint } from './bladespecEditor'

const EPS = 1e-10

/** Apply a library choice while changing only the active station's thickness intent. */
export function applyAirfoilProfile(
  spec: BladeSpec,
  stationIndex: number,
  profile: AirfoilProfile,
): BladeSpec {
  if (profile.airfoil.type === 'naca4') {
    return coordinateNacaThickness(spec, stationIndex, profile.airfoil.code)
  }
  const ratio = profile.metrics.max_thickness_ratio
  if (!Number.isFinite(ratio) || ratio <= 0) throw new Error('Imported profile thickness is invalid')
  const radius = spec.airfoil_sections[stationIndex].r_over_R
  let thickness = spec.thickness_distribution
  let pointIndex = thickness.points.findIndex(point => Math.abs(point.r_over_R - radius) <= EPS)
  if (pointIndex < 0) {
    thickness = addControlPoint(thickness, 'thickness_ratio', radius)
    pointIndex = thickness.points.findIndex(point => Math.abs(point.r_over_R - radius) <= EPS)
  }
  thickness = updateControlPoint(thickness, pointIndex, { thickness_ratio: ratio })
  const airfoil: CoordinateAirfoil = structuredClone(profile.airfoil)
  return {
    ...spec,
    thickness_distribution: thickness,
    airfoil_sections: spec.airfoil_sections.map((section, index) => {
      if (index !== stationIndex) return section
      const { thickness_override_ratio: _, ...withoutOverride } = section
      return { ...withoutOverride, airfoil }
    }),
  }
}
