import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import example from '../../examples/custom_multi_airfoil_finite_te.json'
import App from './App'
import type { AirfoilProfile, BladeSpec, DesignPreview } from './types/bladespec'

const api = vi.hoisted(() => ({
  getExample: vi.fn(), validate: vi.fn(), build: vi.fn(), validatePropeller: vi.fn(),
  buildPropeller: vi.fn(), getJob: vi.fn(), getArtifacts: vi.fn(),
  getDesignPreview: vi.fn(), getPropellerCapabilities: vi.fn(),
  getAirfoilCatalog: vi.fn(), getAirfoilProfile: vi.fn(), importAirfoil: vi.fn(),
}))
vi.mock('./api/client', () => api)
vi.mock('./components/BladeViewer', () => ({
  BladeViewer: () => <div data-testid="viewer" />,
}))

const blade = example as unknown as BladeSpec
const naca0012: AirfoilProfile = {
  profile_id: 'naca-0012',
  display_name: 'NACA 0012',
  category: 'naca4',
  source: 'Analytic NACA 4-digit',
  license: 'Public domain formula',
  point_counts: { upper: 101, lower: 101 },
  metrics: {
    max_thickness_ratio: .12,
    max_thickness_x_over_c: .3,
    max_camber_ratio: 0,
    max_camber_x_over_c: 0,
    trailing_edge_gap_ratio: 0,
  },
  airfoil: { type: 'naca4', code: '0012' },
}

function preview(spec: BladeSpec): DesignPreview {
  const curve = (key: keyof BladeSpec, valueKey: string, unit: string) => {
    const source = spec[key] as BladeSpec['chord_distribution']
    const controls = source.points.map(point => [point.r_over_R, point[valueKey]])
    return { interpolation: source.interpolation, unit, controls, samples: controls }
  }
  return {
    schema_version: '1',
    stations: [],
    distributions: {
      chord: curve('chord_distribution', 'chord_over_R', 'mm'),
      twist: curve('twist_distribution', 'twist_deg', 'deg'),
      rake: curve('rake_distribution', 'rake_over_R', 'mm'),
      skew: curve('skew_distribution', 'skew_over_R', 'mm'),
      thickness: curve('thickness_distribution', 'thickness_ratio', '% t/c'),
    },
  }
}

const importedRows = [
  'row\tr_over_R\tchord_mm\ttwist_deg\trake_mm\tskew_mm',
  '1\t.2\t80.000000123\t30\t-2.5\t-1.25',
  '2\t.6\t62.5\t18.25\t-0.001\t0',
  '3\t1\t30\t5\t1.75\t2.5',
].join('\n')

beforeEach(() => {
  vi.clearAllMocks()
  api.getExample.mockResolvedValue(structuredClone(blade))
  api.validate.mockResolvedValue({ valid: true })
  api.validatePropeller.mockResolvedValue({ valid: true })
  api.getDesignPreview.mockImplementation(async (spec: BladeSpec) => preview(spec))
  api.getPropellerCapabilities.mockResolvedValue({
    contract_blade_count_min: 2,
    contract_blade_count_max: 8,
    supported_blade_counts: [2, 3, 4],
    release_policy: 'Qualified counts: 2, 3, 4',
  })
  api.getAirfoilCatalog.mockResolvedValue([naca0012])
  api.getAirfoilProfile.mockResolvedValue(naca0012)
  vi.stubGlobal('crypto', { randomUUID: vi.fn(() => Math.random().toString(36)) })
  vi.stubGlobal('confirm', vi.fn(() => true))
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

async function loaded() {
  render(<App />)
  await screen.findByText('Airfoil Stations (5)')
  await screen.findByText(/Canonical design preview is current/)
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(next => { resolve = next })
  return { promise, resolve }
}

function curveEditorSnapshot() {
  return Object.fromEntries(['Chord', 'Twist', 'Rake', 'Skew', 'Thickness'].map(title => [title, {
    interpolation: (screen.getByLabelText(`${title} interpolation`) as HTMLSelectElement).value,
    radii: screen.getAllByLabelText(new RegExp(`^${title} radius \\d+$`)).map(input => (input as HTMLInputElement).value),
    values: screen.getAllByLabelText(new RegExp(`^${title} value \\d+$`)).map(input => (input as HTMLInputElement).value),
  }]))
}

function stationEditorSnapshot() {
  const inputValues = (pattern: RegExp) => screen.queryAllByLabelText(pattern).map(input => (input as HTMLInputElement).value)
  return {
    radii: inputValues(/^Airfoil radius \d+$/),
    trailingEdges: inputValues(/^TE thickness \d+$/),
    nacaCodes: inputValues(/^NACA code \d+$/),
    thicknessOverrides: inputValues(/^Thickness override \d+$/),
    profileNames: Array.from(document.querySelectorAll('.station-profile-name'), node => node.textContent),
  }
}

async function waitForCurveEditorIdle() {
  await waitFor(() => expect(document.querySelector('.curve-edit-state')).toHaveTextContent('Ready'))
}

describe('Sprint 04B responsive engineering input', () => {
  it('pastes, reviews, and atomically applies four independent distributions once', async () => {
    const user = userEvent.setup()
    await loaded()
    await user.click(screen.getByRole('button', { name: 'Import Distributions' }))
    const dialog = screen.getByRole('dialog', { name: 'Import Distributions' })
    const textarea = within(dialog).getByLabelText('Distribution pasted data')
    await user.click(textarea)
    await user.paste(importedRows)
    await user.click(within(dialog).getByRole('button', { name: 'Review Pasted Data' }))
    expect(within(dialog).getByText('3 rows')).toBeVisible()
    expect(within(dialog).getByText(/row is not mapped to BladeSpec/)).toBeVisible()
    expect(within(dialog).getByText(/Thickness unchanged/)).toBeVisible()
    expect(within(dialog).getByText((_content, element) => (
      element?.tagName === 'LI' && element.textContent?.includes('Chord: chord_mm (mm), PCHIP, 6 → 3 points') === true
    ))).toBeVisible()
    await user.click(within(dialog).getByRole('button', { name: 'Apply Once' }))
    await waitFor(() => expect(api.validate).toHaveBeenCalledTimes(1))
    expect(await screen.findByText('Chord (3)')).toBeVisible()
    expect(screen.getByText('Twist (3)')).toBeVisible()
    expect(screen.getByText('Rake (3)')).toBeVisible()
    expect(screen.getByText('Skew (3)')).toBeVisible()
    expect(screen.getByText('Thickness (5)')).toBeVisible()
    expect(screen.getByText('Airfoil Stations (5)')).toBeVisible()
    expect(api.build).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Undo curve edit' }))
    expect(await screen.findByText('Chord (6)')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Redo curve edit' }))
    expect(await screen.findByText('Chord (3)')).toBeVisible()
  })

  it('uses real file upload review and Cancel without mutating the project', async () => {
    const user = userEvent.setup()
    await loaded()
    await user.click(screen.getByRole('button', { name: 'Import Distributions' }))
    const dialog = screen.getByRole('dialog', { name: 'Import Distributions' })
    const csv = importedRows.replaceAll('\t', ',')
    await user.upload(within(dialog).getByLabelText('Distribution CSV file'), new File([csv], 'source.csv', { type: 'text/csv' }))
    expect(await within(dialog).findByText('source.csv')).toBeVisible()
    await user.click(within(dialog).getAllByRole('button', { name: 'Cancel' })[0])
    expect(screen.getByText('Chord (6)')).toBeVisible()
    expect(api.validate).not.toHaveBeenCalled()
  })

  it('does not commit a distribution import after Cancel during pending Apply', async () => {
    const validation = deferred<Record<string, unknown>>()
    api.validate.mockReturnValueOnce(validation.promise)
    const user = userEvent.setup()
    await loaded()
    const before = curveEditorSnapshot()
    const previewCalls = api.getDesignPreview.mock.calls.length
    await user.click(screen.getByRole('button', { name: 'Import Distributions' }))
    const dialog = screen.getByRole('dialog', { name: 'Import Distributions' })
    fireEvent.change(within(dialog).getByLabelText('Distribution pasted data'), { target: { value: importedRows } })
    await user.click(within(dialog).getByRole('button', { name: 'Review Pasted Data' }))
    await user.click(within(dialog).getByRole('button', { name: 'Apply Once' }))
    await waitFor(() => expect(api.validate).toHaveBeenCalledTimes(1))
    const signal = api.validate.mock.calls[0][1] as AbortSignal
    expect(signal.aborted).toBe(false)
    await user.click(within(dialog).getAllByRole('button', { name: 'Cancel' })[0])
    expect(signal.aborted).toBe(true)
    expect(screen.queryByRole('dialog', { name: 'Import Distributions' })).not.toBeInTheDocument()
    validation.resolve({ valid: true })
    await waitForCurveEditorIdle()
    expect(curveEditorSnapshot()).toEqual(before)
    expect(screen.getByText('Chord (6)')).toBeVisible()
    expect(screen.getByText('Twist (6)')).toBeVisible()
    expect(screen.getByText('Rake (6)')).toBeVisible()
    expect(screen.getByText('Skew (6)')).toBeVisible()
    expect(screen.getByText('Thickness (5)')).toBeVisible()
    expect(screen.getByText('Airfoil Stations (5)')).toBeVisible()
    expect(api.getDesignPreview).toHaveBeenCalledTimes(previewCalls)
    expect(screen.getByRole('button', { name: 'Undo curve edit' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Undo curve edit' })).toHaveAttribute('title', 'Nothing to undo · Nothing to redo')
  })

  it('sets up five stations as one validated transaction and undoes the full change', async () => {
    const user = userEvent.setup()
    await loaded()
    await user.click(screen.getByRole('button', { name: 'Set Up Airfoil Stations' }))
    const dialog = screen.getByRole('dialog', { name: 'Set Up Airfoil Stations' })
    const count = within(dialog).getByLabelText('Total airfoil stations')
    await user.clear(count)
    await user.type(count, '3')
    expect(within(dialog).getByText(/0.2, 0.6, 1/)).toBeVisible()
    await user.click(within(dialog).getByRole('button', { name: 'Apply Once' }))
    expect(await screen.findByText('Airfoil Stations (3)')).toBeVisible()
    expect(api.validate).toHaveBeenCalledTimes(1)
    expect(api.build).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Undo curve edit' }))
    expect(await screen.findByText('Airfoil Stations (5)')).toBeVisible()
  })

  it('does not commit station setup after Cancel during pending Apply', async () => {
    const validation = deferred<Record<string, unknown>>()
    api.validate.mockReturnValueOnce(validation.promise)
    const user = userEvent.setup()
    await loaded()
    const beforeStations = stationEditorSnapshot()
    const beforeCurves = curveEditorSnapshot()
    const previewCalls = api.getDesignPreview.mock.calls.length
    await user.click(screen.getByRole('button', { name: 'Set Up Airfoil Stations' }))
    const dialog = screen.getByRole('dialog', { name: 'Set Up Airfoil Stations' })
    const count = within(dialog).getByLabelText('Total airfoil stations')
    await user.clear(count)
    await user.type(count, '3')
    await user.click(within(dialog).getByRole('button', { name: 'Apply Once' }))
    await waitFor(() => expect(api.validate).toHaveBeenCalledTimes(1))
    const signal = api.validate.mock.calls[0][1] as AbortSignal
    await user.click(within(dialog).getAllByRole('button', { name: 'Cancel' })[0])
    expect(signal.aborted).toBe(true)
    expect(screen.queryByRole('dialog', { name: 'Set Up Airfoil Stations' })).not.toBeInTheDocument()
    validation.resolve({ valid: true })
    await waitForCurveEditorIdle()
    expect(stationEditorSnapshot()).toEqual(beforeStations)
    expect(curveEditorSnapshot()).toEqual(beforeCurves)
    expect(screen.getByText('Airfoil Stations (5)')).toBeVisible()
    expect(api.getDesignPreview).toHaveBeenCalledTimes(previewCalls)
    expect(screen.getByRole('button', { name: 'Undo curve edit' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Undo curve edit' })).toHaveAttribute('title', 'Nothing to undo · Nothing to redo')
  })

  it('applies one reviewed library profile to selected stations in one validation', async () => {
    const user = userEvent.setup()
    await loaded()
    for (let index = 1; index <= 5; index += 1) {
      await user.click(screen.getByLabelText(`Select airfoil station ${index}`))
    }
    await user.click(screen.getByRole('button', { name: 'Apply Profile to Selected Stations' }))
    const dialog = await screen.findByRole('dialog', { name: 'Airfoil Library for 5 selected stations' })
    await user.click(await within(dialog).findByRole('button', { name: /NACA 0012/ }))
    await user.click(within(dialog).getByLabelText('Use constant thickness for selected common profile'))
    await user.click(await within(dialog).findByRole('button', { name: 'Apply to 5 Selected Stations' }))
    await waitFor(() => expect(api.validate).toHaveBeenCalledTimes(1))
    expect(within(screen.getByLabelText('Select airfoil station 1').closest('tr')!).getByText('NACA 0012')).toBeVisible()
    expect(within(screen.getByLabelText('Select airfoil station 5').closest('tr')!).getByText('NACA 0012')).toBeVisible()
    expect(screen.getByText('Thickness (2)')).toBeVisible()
    expect(api.build).not.toHaveBeenCalled()
  })

  it('rejects Apply when the reviewed diameter snapshot became stale', async () => {
    const user = userEvent.setup()
    await loaded()
    await user.click(screen.getByRole('button', { name: 'Import Distributions' }))
    const dialog = screen.getByRole('dialog', { name: 'Import Distributions' })
    fireEvent.change(within(dialog).getByLabelText('Distribution pasted data'), { target: { value: importedRows } })
    await user.click(within(dialog).getByRole('button', { name: 'Review Pasted Data' }))
    const diameter = screen.getByLabelText('Diameter')
    fireEvent.change(diameter, { target: { value: '720' } })
    fireEvent.blur(diameter)
    await user.click(within(dialog).getByRole('button', { name: 'Apply Once' }))
    expect(await screen.findByText(/design changed after this review opened/i)).toBeVisible()
    expect(api.validate).not.toHaveBeenCalled()
    expect(screen.getByText('Chord (6)')).toBeVisible()
  })
})
