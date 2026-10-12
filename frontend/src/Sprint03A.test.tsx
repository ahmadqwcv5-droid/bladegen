import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import example from '../../examples/custom_multi_airfoil_finite_te.json'
import App from './App'
import type { BladeSpec, DesignPreview, PreviewStation } from './types/bladespec'

const api = vi.hoisted(() => ({
  getExample: vi.fn(), validate: vi.fn(), build: vi.fn(), getJob: vi.fn(), getArtifacts: vi.fn(),
  getDesignPreview: vi.fn(), getPropellerCapabilities: vi.fn(), getAirfoilCatalog: vi.fn(), getAirfoilProfile: vi.fn(), importAirfoil: vi.fn(),
}))
vi.mock('./api/client', () => api)
vi.mock('./components/BladeViewer', () => ({ BladeViewer: () => <div data-testid="viewer" /> }))

const metrics = { max_thickness_ratio: .12, max_thickness_x_over_c: .3, max_camber_ratio: 0, max_camber_x_over_c: 0, trailing_edge_gap_ratio: 0 }
const contour = { upper: [[0, 0], [.5, .06], [1, 0]], lower: [[0, 0], [.5, -.06], [1, 0]], metrics }

function preview(spec: BladeSpec, stationName = 'NACA 4415'): DesignPreview {
  const section = spec.airfoil_sections[0]
  const station: PreviewStation = {
    r_over_R: section.r_over_R, name: stationName, kind: section.airfoil.type,
    local_chord_mm: spec.chord_distribution.points[0].chord_over_R * spec.diameter_mm / 2,
    nominal_thickness_ratio: .12, effective_thickness_ratio: spec.thickness_distribution.points[0].thickness_ratio,
    requested_trailing_edge_thickness_mm: section.trailing_edge_thickness_mm,
    source: contour, resolved: contour,
    preview_status: 'canonical design definition; final CAD validation not yet performed',
  }
  const distribution = (interpolation: 'linear' | 'pchip', values: number[], unit: string) => ({
    interpolation, unit, samples: [[.2, values[0]], [.6, values[1]], [1, values[2]]], controls: [[.2, values[0]], [1, values[2]]],
  })
  const chord = spec.chord_distribution.points.map(point => point.chord_over_R * spec.diameter_mm / 2)
  return {
    schema_version: '1', stations: [station],
    distributions: {
      chord: distribution(spec.chord_distribution.interpolation, [chord[0], chord[Math.floor(chord.length / 2)], chord.at(-1)!], 'mm'),
      twist: distribution(spec.twist_distribution.interpolation, [35, 24, 10], 'deg'),
      rake: distribution(spec.rake_distribution.interpolation, [0, 2, 4], 'mm'),
      skew: distribution(spec.skew_distribution.interpolation, [0, 3, 5], 'mm'),
      thickness: distribution(spec.thickness_distribution.interpolation, [15, 12, 10], '% t/c'),
    },
  }
}

afterEach(() => cleanup())
beforeEach(() => {
  vi.clearAllMocks()
  api.getExample.mockResolvedValue(structuredClone(example))
  api.validate.mockResolvedValue({ valid: true })
  api.getDesignPreview.mockImplementation(async (spec: BladeSpec) => preview(spec))
  vi.stubGlobal('crypto', { randomUUID: vi.fn(() => Math.random().toString(36)) })
})

describe('Sprint 03A live canonical preview', () => {
  it('updates chart samples after control and interpolation edits', async () => {
    const user = userEvent.setup()
    const { container } = render(<App />)
    await screen.findByText('Airfoil Stations (5)')
    const chart = await screen.findByRole('img', { name: /Chord Distribution canonical pchip/ })
    expect(chart).toBeVisible()
    const before = container.querySelector('.chart-line')?.getAttribute('data-values')

    const chordValue = screen.getByLabelText('Chord value 1')
    fireEvent.change(chordValue, { target: { value: '74' } })
    fireEvent.blur(chordValue)
    await waitFor(() => expect(api.getDesignPreview).toHaveBeenLastCalledWith(
      expect.objectContaining({ chord_distribution: expect.objectContaining({ points: expect.arrayContaining([expect.objectContaining({ chord_over_R: .37 })]) }) }),
      expect.any(AbortSignal),
    ))
    await waitFor(() => expect(container.querySelector('.chart-line')?.getAttribute('data-values')).not.toBe(before))

    await user.selectOptions(screen.getByLabelText('Chord interpolation'), 'linear')
    expect(await screen.findByRole('img', { name: /Chord Distribution canonical linear/ })).toBeVisible()
  })

  it('rejects an older overlapping preview response', async () => {
    let resolveOld!: (value: DesignPreview) => void
    let resolveNew!: (value: DesignPreview) => void
    api.getDesignPreview
      .mockReturnValueOnce(new Promise(resolve => { resolveOld = resolve }))
      .mockReturnValueOnce(new Promise(resolve => { resolveNew = resolve }))
    render(<App />)
    await screen.findByText('Airfoil Stations (5)')
    await waitFor(() => expect(api.getDesignPreview).toHaveBeenCalledTimes(1), { timeout: 1500 })
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'new revision' } })
    await waitFor(() => expect(api.getDesignPreview).toHaveBeenCalledTimes(2), { timeout: 1500 })
    const spec = structuredClone(example) as BladeSpec
    resolveNew(preview(spec, 'NEW RESPONSE'))
    expect(await screen.findByText(/NEW RESPONSE at r\/R/)).toBeVisible()
    resolveOld(preview(spec, 'STALE RESPONSE'))
    await new Promise(resolve => setTimeout(resolve, 20))
    expect(screen.queryByText(/STALE RESPONSE/)).not.toBeInTheDocument()
    expect(screen.getByText(/NEW RESPONSE at r\/R/)).toBeVisible()
  })
})
