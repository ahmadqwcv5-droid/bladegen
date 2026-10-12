import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import exampleJson from '../../examples/custom_multi_airfoil_finite_te.json'
import App from './App'
import type { BladeSpec, DesignPreview, Job } from './types/bladespec'

const api = vi.hoisted(() => ({
  getExample: vi.fn(), validate: vi.fn(), build: vi.fn(), validatePropeller: vi.fn(), buildPropeller: vi.fn(),
  getJob: vi.fn(), getArtifacts: vi.fn(), getDesignPreview: vi.fn(), getPropellerCapabilities: vi.fn(), getAirfoilCatalog: vi.fn(),
  getAirfoilProfile: vi.fn(), importAirfoil: vi.fn(),
}))
vi.mock('./api/client', () => api)
vi.mock('./components/BladeViewer', () => ({
  BladeViewer: ({ url, modelType, guidesEnabled, guideStatus }: { url?: string; modelType?: string; guidesEnabled?: boolean; guideStatus?: string }) => <div data-testid="viewer" data-url={url} data-model-type={modelType} data-guides-enabled={String(guidesEnabled)}>{guideStatus}</div>,
}))

const example = exampleJson as unknown as BladeSpec
const profile = { upper: [[0, 0], [1, 0]], lower: [[0, 0], [1, 0]], metrics: { max_thickness_ratio: .12, max_thickness_x_over_c: .3, max_camber_ratio: 0, max_camber_x_over_c: 0, trailing_edge_gap_ratio: 0 } }

function preview(spec: BladeSpec): DesignPreview {
  const distribution = (key: keyof BladeSpec, valueKey: string, unit: string) => {
    const source = spec[key] as BladeSpec['chord_distribution']
    const controls = source.points.map(point => [point.r_over_R, point[valueKey]])
    return { interpolation: source.interpolation, unit, controls, samples: controls }
  }
  return {
    schema_version: '1',
    stations: spec.airfoil_sections.map(section => ({
      r_over_R: section.r_over_R, name: 'station', kind: section.airfoil.type,
      local_chord_mm: 60, nominal_thickness_ratio: .12, effective_thickness_ratio: .12,
      requested_trailing_edge_thickness_mm: section.trailing_edge_thickness_mm,
      source: profile, resolved: profile, preview_status: 'canonical',
    })),
    distributions: {
      chord: distribution('chord_distribution', 'chord_over_R', 'mm'),
      twist: distribution('twist_distribution', 'twist_deg', 'deg'),
      rake: distribution('rake_distribution', 'rake_over_R', 'mm'),
      skew: distribution('skew_distribution', 'skew_over_R', 'mm'),
      thickness: distribution('thickness_distribution', 'thickness_ratio', '% t/c'),
    },
  }
}

const queued: Job = {
  job_id: '4'.repeat(32), build_type: 'propeller', status: 'queued', stage: 'queued',
  stage_label: 'Queued', progress_percent: 0, message: 'Waiting', elapsed_seconds: 0,
}
const succeeded: Job = {
  ...queued, status: 'succeeded', stage: 'complete', stage_label: 'Build complete',
  progress_percent: 100, message: 'Assembly ready', elapsed_seconds: 42,
}
const validation = {
  assembly_validation: {
    passed: true, requested_blade_count: 3, actual_blade_placement_count: 3,
    azimuth_angles_deg: [0, 120, 240], rotation_axis: [1, 0, 0],
    hub_diameter_mm: 90, hub_length_mm: 45, shaft_bore_diameter_mm: 12,
    hub_blade_overlap_mm3: [1397, 1397, 1397], maximum_copy_volume_delta_mm3: 1e-11,
    bore: { requested_radius_mm: 6, measured_radii_mm: [6, 6], maximum_radius_error_mm: 0, continuous_through_hole: true, residual_material_volume_mm3: 0 },
    final_after_reimport: { solids: 1, shells: 1, closed_shell: true, brepcheck_valid: true, free_edges: 0, volume_mm3: 392673, volume_method: 'adaptive' },
    roundtrip: { passed: true, volume_delta_mm3: 2e-8, bbox_max_abs_delta_mm: 8e-11 },
  },
}

beforeEach(() => {
  vi.clearAllMocks()
  api.getExample.mockResolvedValue(structuredClone(example))
  api.getDesignPreview.mockImplementation(async (spec: BladeSpec) => preview(spec))
  api.getPropellerCapabilities.mockResolvedValue({
    contract_blade_count_min: 2,
    contract_blade_count_max: 8,
    supported_blade_counts: [2, 3, 4],
    release_policy: 'Blade counts 2, 3, and 4 are qualified in this release.',
  })
  api.validatePropeller.mockResolvedValue({ valid: true })
  api.buildPropeller.mockResolvedValue(queued)
  api.getJob.mockResolvedValue(succeeded)
  api.getArtifacts.mockResolvedValue([
    { name: 'propeller_solid.step', size_bytes: 10, download_url: '/assembly.step' },
    { name: 'propeller_preview.stl', size_bytes: 10, download_url: '/assembly.stl' },
    { name: 'propeller_spec.json', size_bytes: 10, download_url: '/assembly.json' },
    { name: 'validation.json', size_bytes: 10, download_url: '/validation.json' },
  ])
  vi.stubGlobal('fetch', vi.fn(async () => ({ json: async () => validation })))
  vi.stubGlobal('crypto', { randomUUID: vi.fn(() => Math.random().toString(36)) })
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

async function load() {
  render(<App />)
  await screen.findByText('Airfoil Stations (5)')
  await screen.findByRole('img', { name: /Chord Distribution canonical/ })
}

describe('Sprint 04A full-propeller product integration', () => {
  it('keeps the blade editor while editing and validating a complete PropellerSpec explicitly', async () => {
    const user = userEvent.setup()
    await load()
    await user.click(screen.getByRole('button', { name: 'Full Propeller' }))
    expect(screen.getByText('Propeller Assembly')).toBeVisible()
    expect(screen.getByText('Airfoil Stations (5)')).toBeVisible()
    fireEvent.change(screen.getByLabelText('Number of Blades'), { target: { value: '4' } })
    fireEvent.blur(screen.getByLabelText('Number of Blades'))
    expect(api.validatePropeller).not.toHaveBeenCalled()
    expect(api.buildPropeller).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Validate Assembly' }))
    await waitFor(() => expect(api.validatePropeller).toHaveBeenCalledOnce())
    const submitted = api.validatePropeller.mock.calls[0][0]
    expect(submitted.schema_version).toBe('0.1')
    expect(submitted.assembly.blade_count).toBe(4)
    expect(submitted.blade_spec.airfoil_sections).toHaveLength(5)
    expect(api.buildPropeller).not.toHaveBeenCalled()
  })

  it('binds propeller artifacts to their submitted assembly and marks parameter changes stale', async () => {
    const user = userEvent.setup()
    await load()
    await user.click(screen.getByRole('button', { name: 'Full Propeller' }))
    await user.click(screen.getByRole('button', { name: 'Generate Propeller' }))
    await waitFor(() => expect(api.buildPropeller).toHaveBeenCalledOnce())
    const submitted = api.buildPropeller.mock.calls[0][0]
    expect(submitted.assembly.blade_count).toBe(3)
    await screen.findByText(/Preview from completed job 44444444/)
    expect(screen.getByTestId('viewer')).toHaveAttribute('data-model-type', 'propeller')
    expect(screen.getByTestId('viewer')).toHaveAttribute('data-url', '/assembly.stl')
    expect(screen.getByText('Assembly validation')).toBeVisible()
    expect(screen.getByRole('link', { name: 'propeller_solid.step' })).toBeVisible()
    fireEvent.change(screen.getByLabelText('Number of Blades'), { target: { value: '4' } })
    fireEvent.blur(screen.getByLabelText('Number of Blades'))
    await waitFor(() => expect(screen.getByText(/Inputs changed — regenerate/)).toBeVisible())
    expect(api.buildPropeller).toHaveBeenCalledTimes(1)
    await user.click(screen.getByRole('button', { name: 'Single Blade' }))
    expect(screen.getByText(/previous inputs or mode/)).toBeVisible()
    expect(screen.getByText('Airfoil Stations (5)')).toBeVisible()
  })
})
