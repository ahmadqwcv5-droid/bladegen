import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import bladeJson from '../../examples/custom_multi_airfoil_finite_te.json'
import propellerJson from '../../examples/propeller_two_blade.json'
import App from './App'
import type { BladeSpec, DesignPreview, Job, PropellerSpec } from './types/bladespec'

const api = vi.hoisted(() => ({
  getExample: vi.fn(), validate: vi.fn(), build: vi.fn(), validatePropeller: vi.fn(),
  buildPropeller: vi.fn(), getJob: vi.fn(), getArtifacts: vi.fn(),
  getDesignPreview: vi.fn(), getPropellerCapabilities: vi.fn(),
}))
vi.mock('./api/client', () => api)
vi.mock('./components/BladeViewer', () => ({
  BladeViewer: ({ url }: { url?: string }) => <div data-testid="viewer">{url ?? 'empty'}</div>,
}))

const blade = bladeJson as unknown as BladeSpec
const propeller = propellerJson as unknown as PropellerSpec
const job = (id: string, status: Job['status']): Job => ({
  job_id: id,
  build_type: 'propeller',
  status,
  stage: status === 'succeeded' ? 'complete' : 'queued',
  stage_label: status === 'succeeded' ? 'Build complete' : 'Queued',
  progress_percent: status === 'succeeded' ? 100 : 0,
  message: status === 'succeeded' ? 'Assembly ready' : 'Waiting',
  elapsed_seconds: 1,
})

function preview(spec: BladeSpec): DesignPreview {
  const distribution = (key: keyof BladeSpec, valueKey: string, unit: string) => {
    const source = spec[key] as BladeSpec['chord_distribution']
    const controls = source.points.map(point => [point.r_over_R, point[valueKey]])
    return { interpolation: source.interpolation, unit, controls, samples: controls }
  }
  const profile = {
    upper: [[0, 0], [1, 0]], lower: [[0, 0], [1, 0]],
    metrics: {
      max_thickness_ratio: .12, max_thickness_x_over_c: .3,
      max_camber_ratio: 0, max_camber_x_over_c: 0, trailing_edge_gap_ratio: 0,
    },
  }
  return {
    schema_version: '1',
    stations: spec.airfoil_sections.map(section => ({
      r_over_R: section.r_over_R,
      name: 'station',
      kind: section.airfoil.type,
      local_chord_mm: 60,
      nominal_thickness_ratio: .12,
      effective_thickness_ratio: .12,
      requested_trailing_edge_thickness_mm: section.trailing_edge_thickness_mm,
      source: profile,
      resolved: profile,
      preview_status: 'canonical',
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

const validation = {
  assembly_validation: {
    passed: true,
    actual_blade_placement_count: 2,
    azimuth_angles_deg: [0, 180],
    rotation_axis: [1, 0, 0],
    hub_diameter_mm: 90,
    hub_length_mm: 30,
    shaft_bore_diameter_mm: 12,
    hub_blade_overlap_mm3: [1, 1],
    maximum_copy_volume_delta_mm3: 0,
    bore: {
      measured_radii_mm: [6, 6],
      continuous_through_hole: true,
      residual_material_volume_mm3: 0,
    },
    final_after_reimport: {
      solids: 1, shells: 1, closed_shell: true, brepcheck_valid: true,
      free_edges: 0, volume_mm3: 1, volume_method: 'adaptive',
    },
    roundtrip: { passed: true, volume_delta_mm3: 0, bbox_max_abs_delta_mm: 0 },
  },
}

beforeEach(() => {
  vi.clearAllMocks()
  api.getExample.mockResolvedValue(structuredClone(blade))
  api.getDesignPreview.mockImplementation(async (spec: BladeSpec) => preview(spec))
  api.getPropellerCapabilities.mockResolvedValue({
    contract_blade_count_min: 2,
    contract_blade_count_max: 8,
    supported_blade_counts: [2, 3, 4],
    release_policy: 'Blade counts 2, 3, and 4 are qualified in this release.',
  })
  api.validatePropeller.mockResolvedValue({ valid: true })
  api.getJob.mockImplementation(async (id: string) => job(id, 'succeeded'))
  api.getArtifacts.mockImplementation(async (id: string) => [
    { name: 'propeller_preview.stl', size_bytes: 1, download_url: `/preview-${id[0]}` },
    { name: 'propeller_solid.step', size_bytes: 1, download_url: `/step-${id[0]}` },
    { name: 'validation.json', size_bytes: 1, download_url: `/validation-${id[0]}` },
  ])
  vi.stubGlobal('fetch', vi.fn(async () => ({ json: async () => validation })))
  vi.stubGlobal('confirm', vi.fn(() => true))
  vi.stubGlobal('crypto', { randomUUID: vi.fn(() => Math.random().toString(36)) })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

async function loadPropeller() {
  render(<App />)
  await screen.findByText('Airfoil Stations (5)')
  await userEvent.click(screen.getByRole('button', { name: 'Full Propeller' }))
}

function setNumber(label: string, value: number) {
  const input = screen.getByLabelText(label)
  fireEvent.change(input, { target: { value: String(value) } })
  fireEvent.blur(input)
}

describe('Patch 04A.1 assembly validation and project state', () => {
  it('keeps the successful result historical when 60×30 is rejected, then replaces it with 90×30', async () => {
    const idA = 'a'.repeat(32)
    const idB = 'b'.repeat(32)
    api.buildPropeller
      .mockResolvedValueOnce(job(idA, 'queued'))
      .mockResolvedValueOnce(job(idB, 'queued'))
    await loadPropeller()
    fireEvent.change(screen.getByLabelText('Number of Blades'), { target: { value: '2' } })
    setNumber('Hub Length', 30)
    await userEvent.click(screen.getByRole('button', { name: 'Generate Propeller' }))
    expect(await screen.findByText(/Preview from completed job aaaaaaaa/)).toBeVisible()

    setNumber('Hub Diameter', 60)
    expect(screen.getByText('Hub diameter is too small for the current blade root.')).toBeVisible()
    expect(screen.getByText('40 mm')).toBeVisible()
    expect(screen.getByText('30 mm')).toBeVisible()
    expect(screen.getByText('10 mm')).toBeVisible()
    expect(screen.getByText('greater than 80 mm')).toBeVisible()

    const rejection = Object.assign(new Error('Hub diameter is too small for the current blade root.'), {
      issues: [{
        code: 'hub_root_nominal_overlap_required',
        field: 'assembly.hub_diameter_mm',
        message: 'Hub diameter is too small for the current blade root.',
        operator: '>',
        bound: 80,
      }],
    })
    api.validatePropeller.mockRejectedValueOnce(rejection)
    await userEvent.click(screen.getByRole('button', { name: 'Generate Propeller' }))
    expect(await screen.findByText('Current inputs are invalid. No new CAD build was started.')).toBeVisible()
    expect(screen.getByText(/Last successful build — previous inputs/)).toBeVisible()
    expect(api.buildPropeller).toHaveBeenCalledTimes(1)

    setNumber('Hub Diameter', 90)
    await userEvent.click(screen.getByRole('button', { name: 'Generate Propeller' }))
    expect(await screen.findByText(/Preview from completed job bbbbbbbb/)).toBeVisible()
    expect(screen.getByText(/Last successful build — current inputs/)).toBeVisible()
    expect(api.buildPropeller).toHaveBeenCalledTimes(2)
    expect(api.buildPropeller.mock.calls[1][0].assembly).toMatchObject({
      blade_count: 2,
      hub_diameter_mm: 90,
      hub_length_mm: 30,
      shaft_bore_diameter_mm: 12,
    })
  })

  it('opens a complete PropellerSpec atomically and resets its full project baseline', async () => {
    await loadPropeller()
    const imported: PropellerSpec = {
      ...structuredClone(propeller),
      name: 'customer_two_blade_90x30',
      assembly: {
        ...propeller.assembly,
        blade_count: 2,
        hub_diameter_mm: 90,
        hub_length_mm: 30,
        initial_azimuth_deg: 17.125,
      },
    }
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = { name: 'customer.json', text: async () => JSON.stringify(imported) } as File
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(screen.getByLabelText('Propeller Name')).toHaveValue('customer_two_blade_90x30'))
    await waitFor(() => expect(screen.getByLabelText('Hub Length')).toHaveValue(30))
    expect(screen.getByLabelText('Initial Azimuth')).toHaveValue(17.125)

    await userEvent.click(screen.getByRole('button', { name: 'Single Blade' }))
    await userEvent.click(screen.getByRole('button', { name: 'Full Propeller' }))
    expect(screen.getByLabelText('Hub Length')).toHaveValue(30)
    setNumber('Hub Length', 37)
    await userEvent.click(screen.getByRole('button', { name: 'Reset' }))
    expect(screen.getByLabelText('Hub Length')).toHaveValue(30)
    expect(screen.getByLabelText('Propeller Name')).toHaveValue('customer_two_blade_90x30')

    const invalid = {
      ...imported,
      name: 'must_not_load',
      assembly: { ...imported.assembly, hub_diameter_mm: 60 },
    }
    api.validatePropeller.mockRejectedValueOnce(new Error('invalid hub'))
    const invalidFile = { name: 'invalid.json', text: async () => JSON.stringify(invalid) } as File
    fireEvent.change(input, { target: { files: [invalidFile] } })
    await screen.findByText(/Import rejected/)
    expect(screen.getByText('Project import rejected. The current project was preserved.')).toBeVisible()
    expect(screen.queryByText('Current inputs are invalid. No new CAD build was started.')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Propeller Name')).toHaveValue('customer_two_blade_90x30')
    expect(screen.getByLabelText('Hub Diameter')).toHaveValue(90)
    expect(api.buildPropeller).not.toHaveBeenCalled()
  })

  it('ignores a validation success for an obsolete design revision', async () => {
    let resolveValidation!: (value: object) => void
    api.validatePropeller.mockReturnValueOnce(new Promise(resolve => { resolveValidation = resolve }))
    await loadPropeller()
    await userEvent.click(screen.getByRole('button', { name: 'Validate Assembly' }))
    expect(screen.getByText(/Checking inputs/)).toBeVisible()
    setNumber('Hub Length', 30)
    resolveValidation({ valid: true })
    await waitFor(() => expect(screen.getByText(/Modified \/ not yet checked/)).toBeVisible())
    expect(screen.queryByText(/Input validation passed; final geometric qualification/)).not.toBeInTheDocument()
    expect(api.buildPropeller).not.toHaveBeenCalled()
  })
})
