import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import example from '../../examples/custom_multi_airfoil_finite_te.json'
import App from './App'
import type { AirfoilSection, BladeSpec, Job } from './types/bladespec'

const api = vi.hoisted(() => ({
  getExample: vi.fn(),
  validate: vi.fn(),
  build: vi.fn(),
  getJob: vi.fn(),
  getArtifacts: vi.fn(),
}))
vi.mock('./api/client', () => api)
vi.mock('./components/BladeViewer', () => ({
  BladeViewer: ({ url }: { url?: string }) => <div data-testid="viewer">{url ?? 'empty'}</div>,
}))

const idA = 'a'.repeat(32)
const idB = 'b'.repeat(32)
const makeJob = (id: string, status: Job['status'], progress?: number, stage?: string): Job => ({
  job_id: id,
  status,
  stage: stage ?? (status === 'succeeded' ? 'complete' : status === 'queued' ? 'queued' : 'openvsp'),
  stage_label: status === 'succeeded' ? 'Build complete' : status === 'queued' ? 'Queued' : 'Generating blade surfaces',
  progress_percent: progress ?? (status === 'succeeded' ? 100 : status === 'queued' ? 0 : 18),
  message: status === 'succeeded' ? 'Artifacts ready' : 'CAD operation active',
  elapsed_seconds: 12,
  error: status === 'failed' ? 'intentional OpenVSP failure' : null,
})

const validation = {
  solidification: {
    solid_after_reimport: {
      solids: 1,
      closed_shell: true,
      brepcheck_valid: true,
      free_edges: 0,
      volume_mm3: 12,
      volume_method: 'adaptive',
    },
    roundtrip: { one_solid: true, volume_delta_mm3: 0 },
  },
  geometry_validation: {
    passed: true,
    max_chord_error_mm: 0.001,
    max_twist_error_deg: 0.001,
    max_reference_axis_error_mm: 0.001,
    max_te_error_mm: 0.001,
    control_contour_rms_max_mm: 0.001,
    control_contour_p95_max_mm: 0.001,
    control_contour_max_mm: 0.001,
    root_measurement: { requested_r_over_R: 0.2, measured_r_over_R: 0.203 },
    tip_measurement: { requested_r_over_R: 1, measured_r_over_R: 0.9995 },
    stations: [],
  },
}

afterEach(() => cleanup())

beforeEach(() => {
  vi.clearAllMocks()
  api.getExample.mockResolvedValue(structuredClone(example))
  api.validate.mockResolvedValue({ valid: true })
  api.build.mockResolvedValue(makeJob(idA, 'queued'))
  api.getJob.mockResolvedValue(makeJob(idA, 'succeeded'))
  api.getArtifacts.mockImplementation(async (id: string) => [
    { name: 'blade_preview.stl', size_bytes: 1, download_url: `/preview-${id[0]}` },
    { name: 'blade_solid.step', size_bytes: 1, download_url: `/step-${id[0]}` },
    { name: 'validation.json', size_bytes: 1, download_url: `/validation-${id[0]}` },
  ])
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ json: async () => validation }))
  vi.stubGlobal('confirm', vi.fn(() => true))
  vi.stubGlobal('crypto', { randomUUID: vi.fn(() => Math.random().toString(36)) })
})

async function loaded() {
  render(<App />)
  await screen.findByText('Airfoil Stations (5)')
}

async function generateA(user = userEvent.setup()) {
  await user.click(screen.getByRole('button', { name: 'Generate Blade' }))
  await screen.findByText(/Preview from completed job aaaaaaaa/)
  return user
}

describe('Sprint 02 editor', () => {
  it('adds and removes stable airfoil rows', async () => {
    const user = userEvent.setup()
    await loaded()
    await user.click(screen.getByRole('button', { name: 'Add Airfoil Station' }))
    expect(screen.getByText('Airfoil Stations (6)')).toBeInTheDocument()
    const table = screen.getByText('Airfoil Stations (6)').closest('section')!
    const enabled = within(table).getAllByRole('button', { name: 'Remove' }).filter(button => !button.hasAttribute('disabled'))
    await user.click(enabled[0])
    expect(screen.getByText('Airfoil Stations (5)')).toBeInTheDocument()
  })

  it('synchronizes a root edit across stations and independent curves', async () => {
    await loaded()
    const root = screen.getByLabelText('Root radius')
    fireEvent.change(root, { target: { value: '0.18' } })
    fireEvent.blur(root)
    await waitFor(() => expect(screen.getByLabelText('Airfoil radius 1')).toHaveValue(0.18))
    expect(screen.getByLabelText('Chord radius 1')).toHaveValue(0.18)
    expect(screen.getByLabelText('Twist radius 1')).toHaveValue(0.18)
  })

  it('preserves NACA leading zeroes and coordinates effective thickness', async () => {
    const user = userEvent.setup()
    await loaded()
    const code = screen.getByLabelText('NACA code 5')
    await user.clear(code)
    await user.type(code, '0008')
    expect(code).toHaveValue('0008')
    expect(screen.queryByText(/does not match NACA 0008/)).not.toBeInTheDocument()
  })

  it('edits curve counts and interpolation independently', async () => {
    const user = userEvent.setup()
    await loaded()
    const chord = screen.getByText('Chord (6)').closest('section')!
    await user.click(within(chord).getByRole('button', { name: 'Add Control Point' }))
    expect(screen.getByText('Chord (7)')).toBeInTheDocument()
    expect(screen.getByText('Twist (6)')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Twist interpolation'), 'linear')
    expect(screen.getByLabelText('Twist interpolation')).toHaveValue('linear')
  })

  it('imports a backend-validated BladeSpec without losing fields', async () => {
    const user = userEvent.setup()
    await loaded()
    const imported = structuredClone(example) as unknown as BladeSpec
    imported.name = 'validated_import'
    imported.airfoil_sections = imported.airfoil_sections.slice(0, 3)
    imported.airfoil_sections[2] = structuredClone(example.airfoil_sections.at(-1)!) as unknown as AirfoilSection
    imported.airfoil_sections[1].airfoil = {
      type: 'coordinates',
      upper: [[0, 0], [0.5, 0.08], [1, 0]],
      lower: [[0, 0], [0.5, -0.08], [1, 0]],
    }
    imported.chord_distribution.points = [
      imported.chord_distribution.points[0],
      imported.chord_distribution.points[2],
      imported.chord_distribution.points.at(-1)!,
    ]
    imported.twist_distribution.interpolation = 'linear'
    const file = new File([JSON.stringify(imported)], 'three.json', { type: 'application/json' })
    await user.upload(document.querySelector('input[type=file]') as HTMLInputElement, file)
    expect(await screen.findByText('Airfoil Stations (3)')).toBeInTheDocument()
    expect(screen.getByLabelText('Name')).toHaveValue('validated_import')
    expect(screen.getByText('Coordinate profile')).toBeInTheDocument()
    expect(screen.getByText('Chord (3)')).toBeInTheDocument()
    expect(screen.getByLabelText('Twist interpolation')).toHaveValue('linear')
    expect(api.validate).toHaveBeenCalledWith(imported)
  })

  it('rejects invalid imported JSON without replacing the current project', async () => {
    const user = userEvent.setup()
    await loaded()
    const originalName = (screen.getByLabelText('Name') as HTMLInputElement).value
    const invalid = structuredClone(example)
    invalid.diameter_mm = -1
    api.validate.mockRejectedValueOnce(new Error('diameter_mm must be positive'))
    const file = new File([JSON.stringify(invalid)], 'invalid.json', { type: 'application/json' })
    await user.upload(document.querySelector('input[type=file]') as HTMLInputElement, file)
    expect(await screen.findByText(/Import rejected/)).toBeInTheDocument()
    expect(screen.getByLabelText('Name')).toHaveValue(originalName)
    expect(screen.getByText(/diameter_mm must be positive/)).toBeInTheDocument()
  })

  it('binds results to a snapshot and marks later edits stale', async () => {
    const user = userEvent.setup()
    await loaded()
    await generateA(user)
    const name = screen.getByLabelText('Name')
    await user.clear(name)
    await user.type(name, 'changed')
    expect(screen.getByText(/Inputs changed — regenerate/)).toBeInTheDocument()
    expect(screen.getByText(/Preview from completed job aaaaaaaa/)).toBeInTheDocument()
  })

  it('keeps Preview A labeled as A while Job B runs', async () => {
    const user = userEvent.setup()
    await loaded()
    await generateA(user)
    await user.type(screen.getByLabelText('Name'), '-b')
    api.build.mockResolvedValueOnce(makeJob(idB, 'queued'))
    api.getJob.mockImplementation(async (id: string) => id === idB ? makeJob(idB, 'running', 18) : makeJob(idA, 'succeeded'))
    await user.click(screen.getByRole('button', { name: 'Generate Blade' }))
    await screen.findByText(/Active job bbbbbbbb · running/)
    expect(screen.getByText(/Preview from completed job aaaaaaaa/)).toBeInTheDocument()
    expect(screen.getByTestId('viewer')).toHaveTextContent('/preview-a')
  })

  it('keeps Preview A after Job B fails and attributes the failure to B', async () => {
    const user = userEvent.setup()
    await loaded()
    await generateA(user)
    await user.type(screen.getByLabelText('Name'), '-b')
    api.build.mockResolvedValueOnce(makeJob(idB, 'queued'))
    api.getJob.mockResolvedValueOnce(makeJob(idB, 'failed', 18))
    await user.click(screen.getByRole('button', { name: 'Generate Blade' }))
    expect(await screen.findByText(/intentional OpenVSP failure/)).toBeInTheDocument()
    expect(screen.getByText(/Preview from completed job aaaaaaaa/)).toBeInTheDocument()
    expect(screen.getByTestId('viewer')).toHaveTextContent('/preview-a')
  })

  it('switches preview and artifacts atomically when Job B completes', async () => {
    const user = userEvent.setup()
    await loaded()
    await generateA(user)
    await user.type(screen.getByLabelText('Name'), '-b')
    api.build.mockResolvedValueOnce(makeJob(idB, 'queued'))
    api.getJob.mockResolvedValueOnce(makeJob(idB, 'succeeded'))
    await user.click(screen.getByRole('button', { name: 'Generate Blade' }))
    expect(await screen.findByText(/Preview from completed job bbbbbbbb/)).toBeInTheDocument()
    expect(screen.getByTestId('viewer')).toHaveTextContent('/preview-b')
    expect(screen.getByText(/Artifacts from completed job bbbbbbbb/)).toBeInTheDocument()
  })

  it('reports authoritative input rejection without starting a build', async () => {
    const user = userEvent.setup()
    await loaded()
    api.validate.mockRejectedValueOnce(new Error('root_radius_ratio is inconsistent'))
    await user.click(screen.getByRole('button', { name: 'Generate Blade' }))
    expect(await screen.findByText(/Input validation error: root_radius_ratio is inconsistent/)).toBeInTheDocument()
    expect(api.build).not.toHaveBeenCalled()
  })

  it('prevents duplicate submissions while the first request is pending', async () => {
    await loaded()
    let resolveValidation!: (value: object) => void
    api.validate.mockReturnValueOnce(new Promise(resolve => { resolveValidation = resolve }))
    const button = screen.getByRole('button', { name: 'Generate Blade' })
    fireEvent.click(button)
    fireEvent.click(button)
    expect(api.validate).toHaveBeenCalledTimes(1)
    resolveValidation({ valid: true })
    await waitFor(() => expect(api.build).toHaveBeenCalledTimes(1))
  })
})
