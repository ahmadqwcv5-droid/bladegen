import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import exampleJson from '../../examples/custom_multi_airfoil_finite_te.json'
import App from './App'
import type { BladeSpec, DesignPreview, Job, PreviewProfile } from './types/bladespec'

const api = vi.hoisted(() => ({
  getExample: vi.fn(), validate: vi.fn(), build: vi.fn(), getJob: vi.fn(), getArtifacts: vi.fn(),
  getDesignPreview: vi.fn(), getAirfoilCatalog: vi.fn(), getAirfoilProfile: vi.fn(), importAirfoil: vi.fn(),
}))
const viewerProbe = vi.hoisted(() => ({ guideRefs: [] as { yMm: number; label: string }[][] }))
vi.mock('./api/client', () => api)
vi.mock('./components/BladeViewer', () => ({
  BladeViewer: ({ url, guides = [], guidesEnabled = false, guideStatus }: { url?: string; guides?: { yMm: number; label: string }[]; guidesEnabled?: boolean; guideStatus?: string }) => {
    viewerProbe.guideRefs.push(guides)
    return <div
      data-testid="viewer"
      data-url={url ?? ''}
      data-guides-enabled={String(guidesEnabled)}
      data-guide-y={guides.map(guide => guide.yMm).join(',')}
      data-guide-labels={guides.map(guide => guide.label).join(',')}
    >{guideStatus}</div>
  },
}))

const example = exampleJson as unknown as BladeSpec
const idA = 'a'.repeat(32)
const idB = 'b'.repeat(32)
const sourceMetrics = { max_thickness_ratio: .12, max_thickness_x_over_c: .3, max_camber_ratio: .02, max_camber_x_over_c: .4, trailing_edge_gap_ratio: 0 }
const resolvedMetrics = { ...sourceMetrics, max_thickness_ratio: .105, trailing_edge_gap_ratio: .012 }
const nacaSource: PreviewProfile = { upper: [[0, 0], [.5, .061], [1, 0]], lower: [[0, 0], [.5, -.059], [1, 0]], metrics: sourceMetrics }
const resolved: PreviewProfile = { upper: [[0, .006], [.5, .053], [1, .006]], lower: [[0, -.006], [.5, -.052], [1, -.006]], metrics: resolvedMetrics }

function preview(spec: BladeSpec): DesignPreview {
  const distribution = (unit: string) => ({ interpolation: 'pchip' as const, unit, samples: [[spec.root_radius_ratio, 1], [1, 2]], controls: [[spec.root_radius_ratio, 1], [1, 2]] })
  return {
    schema_version: '1',
    stations: spec.airfoil_sections.map((section, index) => ({
      r_over_R: section.r_over_R,
      name: section.airfoil.type === 'naca4' ? `NACA ${section.airfoil.code}` : 'Imported analytic 41-point',
      kind: section.airfoil.type,
      local_chord_mm: 70 - index * 8.25,
      nominal_thickness_ratio: .12,
      effective_thickness_ratio: .105,
      requested_trailing_edge_thickness_mm: section.trailing_edge_thickness_mm,
      source: section.airfoil.type === 'coordinates'
        ? { upper: structuredClone(section.airfoil.upper), lower: structuredClone(section.airfoil.lower), metrics: sourceMetrics }
        : nacaSource,
      resolved,
      preview_status: 'canonical design definition; final CAD validation not yet performed',
    })),
    distributions: {
      chord: distribution('mm'), twist: distribution('deg'), rake: distribution('mm'),
      skew: distribution('mm'), thickness: distribution('% t/c'),
    },
  }
}

const job = (id: string, status: Job['status']): Job => ({
  job_id: id,
  build_type: 'blade',
  status,
  stage: status === 'succeeded' ? 'complete' : status === 'failed' ? 'failed' : 'openvsp',
  stage_label: status === 'succeeded' ? 'Build complete' : status === 'failed' ? 'Build failed' : 'Generating blade surfaces',
  progress_percent: status === 'succeeded' ? 100 : 30,
  message: status === 'failed' ? 'OpenVSP rejected the candidate' : 'CAD operation active',
  elapsed_seconds: 4,
  error: status === 'failed' ? 'intentional failure B' : null,
})

const validation = {
  solidification: {
    solid_after_reimport: { solids: 1, closed_shell: true, brepcheck_valid: true, free_edges: 0, volume_mm3: 12, volume_method: 'adaptive' },
    roundtrip: { one_solid: true, volume_delta_mm3: 0 },
  },
}

afterEach(cleanup)
beforeEach(() => {
  vi.clearAllMocks()
  viewerProbe.guideRefs.length = 0
  api.getExample.mockResolvedValue(structuredClone(example))
  api.validate.mockResolvedValue({ valid: true })
  api.getDesignPreview.mockImplementation(async (spec: BladeSpec) => preview(spec))
  api.build.mockResolvedValue(job(idA, 'queued'))
  api.getJob.mockResolvedValue(job(idA, 'succeeded'))
  api.getArtifacts.mockImplementation(async (id: string) => [
    { name: 'blade_preview.stl', size_bytes: 12, download_url: `/preview-${id[0]}.stl` },
    { name: 'validation.json', size_bytes: 12, download_url: `/validation-${id[0]}.json` },
  ])
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ json: async () => validation }))
  vi.stubGlobal('confirm', vi.fn(() => true))
  let nextId = 0
  vi.stubGlobal('crypto', { randomUUID: vi.fn(() => `s03b-${++nextId}`) })
})

async function loadApp() {
  render(<App />)
  await screen.findByText('Airfoil Stations (5)')
  await screen.findByText(/Canonical design preview is current/)
}

async function generate() {
  await userEvent.click(screen.getByRole('button', { name: 'Generate Blade' }))
  await waitFor(() => expect(screen.getByTestId('viewer')).toHaveAttribute('data-url', '/preview-a.stl'), { timeout: 2500 })
}

describe('Sprint 03B station identity and comparison', () => {
  it('keeps guide references stable for unrelated parent rerenders and invalidates relevant selections', async () => {
    const user = userEvent.setup()
    await loadApp()
    const initial = viewerProbe.guideRefs.at(-1)
    expect(initial).toBeDefined()
    viewerProbe.guideRefs.length = 0

    await user.click(screen.getByRole('button', { name: 'Validate' }))
    await screen.findByText(/input validation passed/i)
    expect(viewerProbe.guideRefs.length).toBeGreaterThan(0)
    viewerProbe.guideRefs.forEach(reference => expect(reference).toBe(initial))

    await user.click(screen.getAllByRole('button', { name: 'Inspect' })[2])
    const selectedStation = viewerProbe.guideRefs.at(-1)
    expect(selectedStation).not.toBe(initial)
    await user.click(screen.getByRole('button', { name: 'Compare Stations' }))
    const comparison = viewerProbe.guideRefs.at(-1)
    expect(comparison).not.toBe(selectedStation)
    await user.selectOptions(
      screen.getByLabelText('Comparison Station B'),
      within(screen.getByLabelText('Comparison Station B')).getByRole('option', { name: /Station 4 · r\/R 0.8000/ }),
    )
    expect(viewerProbe.guideRefs.at(-1)).not.toBe(comparison)
  })

  it('keeps the intended station selected through insertion, radius editing, and removal of another row', async () => {
    const user = userEvent.setup()
    await loadApp()
    await user.click(screen.getAllByRole('button', { name: 'Inspect' })[2])
    expect(screen.getByText(/Inspecting Station 3 · r\/R 0.6000/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Add Airfoil Station' }))
    expect(screen.getByText(/Inspecting Station .* · r\/R 0.6000/)).toBeInTheDocument()
    let selectedRow = screen.getByText('Selected').closest('tr')!
    const radius = within(selectedRow).getByLabelText(/Airfoil radius/)
    fireEvent.change(radius, { target: { value: '.625' } })
    fireEvent.blur(radius)
    await screen.findByText(/Inspecting Station .* · r\/R 0.6250/)

    selectedRow = screen.getByText('Selected').closest('tr')!
    const otherRemove = screen.getAllByRole('button', { name: 'Remove' }).find(button => !button.hasAttribute('disabled') && button.closest('tr') !== selectedRow)!
    await user.click(otherRemove)
    expect(screen.getByText(/Inspecting Station .* · r\/R 0.6250/)).toBeInTheDocument()
  })

  it('selects a deterministic neighboring station when the selected row is removed', async () => {
    const user = userEvent.setup()
    await loadApp()
    await user.click(screen.getAllByRole('button', { name: 'Inspect' })[2])
    const selectedRow = screen.getByText('Selected').closest('tr')!
    await user.click(within(selectedRow).getByRole('button', { name: 'Remove' }))
    expect(screen.getAllByText('Selected')).toHaveLength(1)
    expect(screen.queryByText(/r\/R 0.6000/)).not.toBeInTheDocument()
    expect(screen.getByText(/Inspecting Station 3 · r\/R 0.8000/)).toBeInTheDocument()
  })

  it('resets station identity safely on import and example reload', async () => {
    const user = userEvent.setup()
    await loadApp()
    const imported = structuredClone(example)
    imported.name = 'three-station-import'
    imported.airfoil_sections = [imported.airfoil_sections[0], {
      ...imported.airfoil_sections[2],
      airfoil: { type: 'coordinates' as const, upper: [[0, 0], [.5, .07], [1, 0]], lower: [[0, 0], [.5, -.06], [1, 0]] },
    }, imported.airfoil_sections[4]]
    const file = new File([JSON.stringify(imported)], 'three-station.json', { type: 'application/json' })
    await user.upload(document.querySelector('input[type=file]') as HTMLInputElement, file)
    await screen.findByText('Airfoil Stations (3)')
    expect(screen.getByText(/Inspecting Station 1 · r\/R 0.2000/)).toBeInTheDocument()
    await user.click(screen.getAllByRole('button', { name: 'Inspect' })[1])
    expect(screen.getByText(/r\/R 0.6000/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Load Example' }))
    await screen.findByText('Airfoil Stations (5)')
    expect(screen.getByText(/Inspecting Station 1 · r\/R 0.2000/)).toBeInTheDocument()
  })

  it('compares NACA and embedded coordinates without mutating or generating BladeSpec', async () => {
    const user = userEvent.setup()
    await loadApp()
    const imported = structuredClone(example)
    imported.airfoil_sections[3] = {
      ...imported.airfoil_sections[3],
      airfoil: { type: 'coordinates', upper: [[0, 0], [.5, .052], [1, .002]], lower: [[0, 0], [.5, -.049], [1, -.002]] },
    }
    await user.upload(document.querySelector('input[type=file]') as HTMLInputElement, new File([JSON.stringify(imported)], 'embedded.json', { type: 'application/json' }))
    await screen.findByText(/Canonical design preview is current/)
    const previewCalls = api.getDesignPreview.mock.calls.length
    const nameBefore = (screen.getByLabelText('Name') as HTMLInputElement).value
    await user.click(screen.getByRole('button', { name: 'Compare Stations' }))
    await user.selectOptions(screen.getByLabelText('Comparison Station B'), within(screen.getByLabelText('Comparison Station B')).getByRole('option', { name: /Station 4 · r\/R 0.8000/ }))
    expect(screen.getByText('Imported analytic 41-point (coordinates)')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Resolved Design Profiles' }))
    expect(screen.getByRole('img', { name: /resolved airfoil comparison/i })).toBeInTheDocument()
    expect(api.build).not.toHaveBeenCalled()
    expect(api.getDesignPreview).toHaveBeenCalledTimes(previewCalls)
    expect(screen.getByLabelText('Name')).toHaveValue(nameBefore)
    await user.click(screen.getByRole('button', { name: 'Return to Single Station' }))
    expect(screen.getByText(/Inspecting Station/)).toBeInTheDocument()
  })
})

describe('Sprint 03B design/CAD synchronization', () => {
  it('uses exact physical Y, hides guides on stale CAD, and restores them only for matching successful CAD', async () => {
    const user = userEvent.setup()
    await loadApp()
    await user.click(screen.getAllByRole('button', { name: 'Inspect' })[2])
    await generate()
    expect(screen.getByTestId('viewer')).toHaveAttribute('data-guides-enabled', 'true')
    expect(screen.getByTestId('viewer')).toHaveAttribute('data-guide-y', '120')

    await user.type(screen.getByLabelText('Name'), '-revised')
    expect(screen.getByTestId('viewer')).toHaveAttribute('data-guides-enabled', 'false')
    expect(screen.getByTestId('viewer')).toHaveTextContent(/previous inputs/)
    await screen.findByText(/Canonical design preview is current/)
    await user.click(screen.getByRole('button', { name: 'Compare Stations' }))
    expect(screen.getByRole('img', { name: /source airfoil comparison/i })).toBeInTheDocument()
    expect(screen.getByTestId('viewer')).toHaveAttribute('data-guides-enabled', 'false')

    api.build.mockResolvedValueOnce(job(idB, 'queued'))
    api.getJob.mockResolvedValueOnce(job(idB, 'succeeded'))
    await user.click(screen.getByRole('button', { name: 'Generate Blade' }))
    await waitFor(() => expect(screen.getByTestId('viewer')).toHaveAttribute('data-url', '/preview-b.stl'), { timeout: 2500 })
    expect(screen.getByTestId('viewer')).toHaveAttribute('data-guides-enabled', 'true')
    expect(screen.getByTestId('viewer')).toHaveAttribute('data-guide-y', '40,80')
  })

  it('keeps failed Blade B from relabeling Blade A or enabling current-design guides', async () => {
    const user = userEvent.setup()
    await loadApp()
    await generate()
    await user.type(screen.getByLabelText('Name'), '-failed-b')
    await screen.findByText(/Canonical design preview is current/)
    api.build.mockResolvedValueOnce(job(idB, 'queued'))
    api.getJob.mockResolvedValueOnce(job(idB, 'failed'))
    await user.click(screen.getByRole('button', { name: 'Generate Blade' }))
    await screen.findByText(/intentional failure B/)
    expect(screen.getByTestId('viewer')).toHaveAttribute('data-url', '/preview-a.stl')
    expect(screen.getByTestId('viewer')).toHaveAttribute('data-guides-enabled', 'false')
    expect(screen.getByText(/Preview from completed job aaaaaaaa/)).toBeInTheDocument()
  })

  it('hides an old canonical preview throughout debounce and ignores an overlapping response', async () => {
    let resolveOld!: (value: DesignPreview) => void
    let resolveNew!: (value: DesignPreview) => void
    api.getDesignPreview
      .mockReturnValueOnce(new Promise(resolve => { resolveOld = resolve }))
      .mockReturnValueOnce(new Promise(resolve => { resolveNew = resolve }))
    render(<App />)
    await screen.findByText('Airfoil Stations (5)')
    await waitFor(() => expect(api.getDesignPreview).toHaveBeenCalledOnce(), { timeout: 1500 })
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'new-revision' } })
    expect(screen.getByText(/Station inspection is hidden/)).toBeInTheDocument()
    await waitFor(() => expect(api.getDesignPreview).toHaveBeenCalledTimes(2), { timeout: 1500 })
    const revised = structuredClone(example)
    revised.name = 'new-revision'
    resolveNew(preview(revised))
    await screen.findByText(/Canonical design preview is current/)
    resolveOld(preview(example))
    await new Promise(resolve => setTimeout(resolve, 20))
    expect(screen.queryByText(/Station inspection is hidden/)).not.toBeInTheDocument()
  })
})
