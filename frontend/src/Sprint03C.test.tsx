import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import exampleJson from '../../examples/custom_multi_airfoil_finite_te.json'
import App from './App'
import type { BladeSpec, DesignPreview } from './types/bladespec'

const api = vi.hoisted(() => ({
  getExample: vi.fn(), validate: vi.fn(), build: vi.fn(), getJob: vi.fn(), getArtifacts: vi.fn(),
  getDesignPreview: vi.fn(), getAirfoilCatalog: vi.fn(), getAirfoilProfile: vi.fn(), importAirfoil: vi.fn(),
}))
vi.mock('./api/client', () => api)
vi.mock('./components/BladeViewer', () => ({ BladeViewer: () => <div data-testid="viewer" /> }))

const example = exampleJson as unknown as BladeSpec
const metrics = { max_thickness_ratio: .12, max_thickness_x_over_c: .3, max_camber_ratio: 0, max_camber_x_over_c: 0, trailing_edge_gap_ratio: 0 }
const profile = { upper: [[0, 0], [.5, .06], [1, 0]], lower: [[0, 0], [.5, -.06], [1, 0]], metrics }

function preview(spec: BladeSpec): DesignPreview {
  const distribution = (key: keyof BladeSpec, valueKey: string, unit: string) => {
    const source = spec[key] as BladeSpec['chord_distribution']
    const physical = (value: number) => key === 'twist_distribution' ? value : key === 'thickness_distribution' ? value * 100 : value * spec.diameter_mm / 2
    const controls = source.points.map(point => [point.r_over_R, physical(point[valueKey])])
    return { interpolation: source.interpolation, unit, controls, samples: controls }
  }
  return {
    schema_version: '1',
    stations: spec.airfoil_sections.map(section => ({
      r_over_R: section.r_over_R, name: section.airfoil.type === 'naca4' ? `NACA ${section.airfoil.code}` : 'Coordinates', kind: section.airfoil.type,
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

beforeEach(() => {
  vi.clearAllMocks()
  api.getExample.mockResolvedValue(structuredClone(example))
  api.validate.mockResolvedValue({ valid: true })
  api.getDesignPreview.mockImplementation(async (spec: BladeSpec) => preview(spec))
  vi.stubGlobal('crypto', { randomUUID: vi.fn(() => Math.random().toString(36)) })
})
afterEach(cleanup)

async function load() {
  render(<App />)
  await screen.findByText('Airfoil Stations (5)')
  await screen.findByRole('img', { name: /Chord Distribution canonical/ })
}

describe('Sprint 03C committed curve transactions', () => {
  it('commits 60 → 64 mm with one validation, then undo/redo without a CAD build', async () => {
    const user = userEvent.setup()
    await load()
    const input = screen.getByLabelText('Chord value 3')
    expect(input).toHaveValue(60)
    fireEvent.change(input, { target: { value: '64' } })
    fireEvent.blur(input)
    await waitFor(() => expect(api.validate).toHaveBeenCalledTimes(1))
    const candidate = api.validate.mock.calls[0][0] as BladeSpec
    expect(candidate.chord_distribution.points[2]).toEqual({ r_over_R: .5, chord_over_R: .32 })
    expect(candidate.twist_distribution).toEqual(example.twist_distribution)
    await waitFor(() => expect(screen.getByLabelText('Chord value 3')).toHaveValue(64))
    expect(api.build).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Undo curve edit' }))
    expect(screen.getByLabelText('Chord value 3')).toHaveValue(60)
    await user.click(screen.getByRole('button', { name: 'Redo curve edit' }))
    expect(screen.getByLabelText('Chord value 3')).toHaveValue(64)
    expect(api.validate).toHaveBeenCalledTimes(1)
    expect(api.build).not.toHaveBeenCalled()
  })

  it('keeps the committed spec unchanged while validating and ignores a stale response', async () => {
    let resolve!: (value: object) => void
    api.validate.mockReturnValueOnce(new Promise(value => { resolve = value }))
    await load()
    const chord = screen.getByLabelText('Chord value 3')
    fireEvent.change(chord, { target: { value: '64' } })
    fireEvent.blur(chord)
    await screen.findByText(/Validating Chord control edit/)
    expect(screen.getByLabelText('Chord value 3')).toHaveValue(64)
    expect(api.getDesignPreview).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: /Validating curve/ })).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'newer global edit' } })
    resolve({ valid: true })
    await new Promise(value => setTimeout(value, 20))
    await waitFor(() => expect(screen.getByLabelText('Chord value 3')).toHaveValue(60))
    expect(screen.getByRole('button', { name: 'Undo curve edit' })).toBeDisabled()
  })

  it('rolls back a rejected candidate and exposes a meaningful backend error', async () => {
    api.validate.mockRejectedValueOnce(new Error('chord distribution is outside the accepted domain'))
    await load()
    const chord = screen.getByLabelText('Chord value 3')
    fireEvent.change(chord, { target: { value: '64' } })
    fireEvent.blur(chord)
    expect(await screen.findByText(/Curve edit rejected by backend/)).toBeVisible()
    await waitFor(() => expect(screen.getByLabelText('Chord value 3')).toHaveValue(60))
    expect(screen.getByRole('button', { name: 'Undo curve edit' })).toBeDisabled()
  })

  it('locks natural thickness and updates distribution plus explicit NACA override atomically', async () => {
    const user = userEvent.setup()
    await load()
    expect(screen.getByLabelText('Thickness value 2')).toBeDisabled()
    expect(screen.getAllByText(/Enable its explicit thickness override first/).length).toBeGreaterThan(0)
    const stationRows = screen.getAllByRole('row').filter(row => within(row).queryByLabelText(/explicit/))
    await user.click(within(stationRows[1]).getByLabelText(/explicit/))
    const thickness = screen.getByLabelText('Thickness value 2')
    expect(thickness).toBeEnabled()
    fireEvent.change(thickness, { target: { value: '13.5' } })
    fireEvent.blur(thickness)
    await waitFor(() => expect(api.validate).toHaveBeenCalledTimes(1))
    const candidate = api.validate.mock.calls[0][0] as BladeSpec
    expect(candidate.thickness_distribution.points[1].thickness_ratio).toBe(.135)
    expect(candidate.airfoil_sections[1].thickness_override_ratio).toBe(.135)
  })
})
