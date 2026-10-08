export type Point = { r_over_R: number; [key: string]: number }
export type Distribution = { interpolation: 'linear' | 'pchip'; points: Point[] }
export type AirfoilSection = {
  r_over_R: number
  airfoil: { type: 'naca4'; code: string } | { type: 'coordinates'; upper: number[][]; lower: number[][] }
  trailing_edge_thickness_mm: number
  thickness_override_ratio?: number
}
export type BladeSpec = {
  schema_version: '0.1' | '0.2'; name: string; units: 'mm'; diameter_mm: number
  root_radius_ratio: number; reference_axis_x_over_c: number
  rotation_direction: 'normal' | 'reverse'; airfoil_sections: AirfoilSection[]
  chord_distribution: Distribution; twist_distribution: Distribution
  rake_distribution: Distribution; skew_distribution: Distribution
  thickness_distribution: Distribution
}
export type Artifact = { name: string; size_bytes: number; download_url: string }
export type Job = { job_id: string; status: 'queued'|'running'|'succeeded'|'failed'; error?: string }
