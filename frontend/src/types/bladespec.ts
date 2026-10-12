export type Point = { r_over_R: number; [key: string]: number }
export type Distribution = { interpolation: 'linear' | 'pchip'; points: Point[] }
export type CoordinateAirfoil = { type: 'coordinates'; upper: number[][]; lower: number[][] }
export type NacaAirfoil = { type: 'naca4'; code: string }
export type AirfoilSection = {
  r_over_R: number
  airfoil: NacaAirfoil | CoordinateAirfoil
  trailing_edge_thickness_mm: number
  thickness_override_ratio?: number | null
}
export type BladeSpec = {
  schema_version: '0.1' | '0.2'; name: string; units: 'mm'; diameter_mm: number
  root_radius_ratio: number; reference_axis_x_over_c: number
  rotation_direction: 'normal' | 'reverse'; airfoil_sections: AirfoilSection[]
  chord_distribution: Distribution; twist_distribution: Distribution
  rake_distribution: Distribution; skew_distribution: Distribution
  thickness_distribution: Distribution
}
export type AssemblySpec = {
  blade_count: number
  hub_diameter_mm: number
  hub_length_mm: number
  shaft_bore_diameter_mm: number
  initial_azimuth_deg: number
}
export type PropellerSpec = {
  schema_version: '0.1'
  name: string
  units: 'mm'
  blade_spec: BladeSpec
  assembly: AssemblySpec
}
export type ValidationIssue = {
  code: string
  field: string
  message: string
  context?: Record<string, unknown>
  operator?: string
  bound?: number
}
export type PropellerCapabilities = {
  contract_blade_count_min: number
  contract_blade_count_max: number
  supported_blade_counts: number[]
  release_policy: string
}
export type NominalHubGuidance = {
  root_radius_mm: number
  hub_radius_mm: number
  nominal_radial_overlap_mm: number
  nominal_radial_gap_mm: number
  required_hub_diameter_bound_mm: number
  bound_is_exclusive: boolean
  passes_nominal_policy: boolean
}
export type PropellerValidationResponse = {
  valid: true
  schema_version: '0.1'
  blade_count: number
  airfoil_sections_per_blade: number
  rotation_axis: 'X'
  nominal_radial_overlap_mm: number
  nominal_hub_guidance: NominalHubGuidance
  capabilities: PropellerCapabilities
  geometric_qualification: string
}
export type Artifact = { name: string; size_bytes: number; download_url: string }
export type Job = {
  job_id: string
  build_type: 'blade'|'propeller'
  status: 'queued'|'running'|'succeeded'|'failed'
  stage: string
  stage_label: string
  progress_percent: number
  message: string
  elapsed_seconds: number
  error?: string | null
}

export type AirfoilMetrics = {
  max_thickness_ratio: number
  max_thickness_x_over_c: number
  max_camber_ratio: number
  max_camber_x_over_c: number
  trailing_edge_gap_ratio: number
}

export type ProfileDiagnostics = {
  upper_point_count: number
  lower_point_count: number
  maximum_chordwise_spacing: number
  upper_leading_edge_point_count: number
  lower_leading_edge_point_count: number
  warning_codes: string[]
  warnings: string[]
  has_warning: boolean
  advisory: string
}

export type AirfoilCatalogItem = {
  profile_id: string
  display_name: string
  category: 'naca4' | 'imported'
  source: string
  license: string
  point_counts: { upper: number; lower: number }
  metrics: AirfoilMetrics
  diagnostics?: ProfileDiagnostics
  original_filename?: string
  import_format?: string
  canonical_coordinate_sha256?: string
  notes?: string | null
  normalization?: string
  airfoil?: NacaAirfoil | CoordinateAirfoil
}

export type AirfoilProfile = AirfoilCatalogItem & {
  airfoil: NacaAirfoil | CoordinateAirfoil
  source_coordinates?: CoordinateAirfoil
}

export type PreviewProfile = {
  upper: number[][]
  lower: number[][]
  metrics: AirfoilMetrics
}

export type PreviewStation = {
  r_over_R: number
  name: string
  kind: 'naca4' | 'coordinates'
  local_chord_mm: number
  nominal_thickness_ratio: number
  effective_thickness_ratio: number
  requested_trailing_edge_thickness_mm: number
  source: PreviewProfile
  resolved: PreviewProfile
  diagnostics?: ProfileDiagnostics | null
  preview_status: string
}

export type DistributionPreview = {
  interpolation: 'linear' | 'pchip'
  unit: string
  samples: number[][]
  controls: number[][]
}

export type DesignPreview = {
  schema_version: '1'
  stations: PreviewStation[]
  distributions: Record<'chord' | 'twist' | 'rake' | 'skew' | 'thickness', DistributionPreview>
}
