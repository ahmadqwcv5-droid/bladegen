import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { AirfoilProfile } from '../types/bladespec'
import { AirfoilSelector } from './AirfoilSelector'

const api = vi.hoisted(() => ({
  getAirfoilCatalog: vi.fn(),
  getAirfoilProfile: vi.fn(),
  importAirfoil: vi.fn(),
}))
vi.mock('../api/client', () => api)

const naca: AirfoilProfile = {
  profile_id: 'naca-2412', display_name: 'NACA 2412', category: 'naca4',
  source: 'canonical', license: 'not applicable', point_counts: { upper: 3, lower: 3 },
  metrics: { max_thickness_ratio: .12, max_thickness_x_over_c: .3, max_camber_ratio: .02, max_camber_x_over_c: .4, trailing_edge_gap_ratio: 0 },
  airfoil: { type: 'naca4', code: '2412' },
  source_coordinates: { type: 'coordinates', upper: [[0, 0], [.5, .07], [1, 0]], lower: [[0, 0], [.5, -.04], [1, 0]] },
}
const imported: AirfoilProfile = {
  ...naca,
  profile_id: 'imported-independent', display_name: 'Independent profile', category: 'imported',
  license: 'unknown', original_filename: 'independent.dat',
  canonical_coordinate_sha256: 'a'.repeat(64),
  airfoil: { type: 'coordinates', upper: [[0, 0], [.5, .075], [1, .005]], lower: [[0, 0], [.5, -.035], [1, -.005]] },
  metrics: { ...naca.metrics, max_thickness_ratio: .11, trailing_edge_gap_ratio: .01 },
}

afterEach(() => cleanup())
beforeEach(() => {
  vi.clearAllMocks()
  api.getAirfoilCatalog.mockResolvedValue([naca, imported])
  api.getAirfoilProfile.mockImplementation(async (id: string) => id.startsWith('naca-') ? naca : imported)
  api.importAirfoil.mockResolvedValue(imported)
})

describe('Airfoil Selector', () => {
  it('searches NACA profiles, previews, applies, and can cancel without applying', async () => {
    const user = userEvent.setup()
    const apply = vi.fn()
    const cancel = vi.fn()
    render(<AirfoilSelector stationIndex={2} radius={.6} onApply={apply} onCancel={cancel} />)
    await screen.findByRole('button', { name: /NACA 2412/ })
    await user.type(screen.getByLabelText('Search airfoils'), '2412')
    expect(screen.getByRole('button', { name: /NACA 2412/ })).toBeVisible()
    expect(screen.queryByRole('button', { name: /Independent profile/ })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /NACA 2412/ }))
    expect(await screen.findByRole('img', { name: /NACA 2412 source airfoil coordinates/ })).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Apply to Station 3' }))
    expect(apply).toHaveBeenCalledWith(naca, { constantThickness: false })

    render(<AirfoilSelector stationIndex={1} radius={.4} onApply={apply} onCancel={cancel} />)
    await user.click(screen.getAllByRole('button', { name: 'Cancel' }).at(-1)!)
    expect(cancel).toHaveBeenCalledOnce()
  })

  it.each([
    ['custom.dat', 'text/plain'],
    ['custom.csv', 'text/csv'],
  ])('imports and previews a valid %s profile', async (filename, mime) => {
    const user = userEvent.setup()
    render(<AirfoilSelector stationIndex={0} radius={.2} onApply={vi.fn()} onCancel={vi.fn()} />)
    await screen.findByText('Import DAT or CSV')
    await user.click(screen.getByText('Import DAT or CSV'))
    const file = new File(['1,0\n0,0\n1,0'], filename, { type: mime })
    await user.upload(screen.getByLabelText('Airfoil coordinate file'), file)
    await user.type(screen.getByLabelText('Airfoil source'), 'User measurement')
    await user.click(screen.getByRole('button', { name: 'Import and Preview' }))
    await waitFor(() => expect(api.importAirfoil).toHaveBeenCalled())
    expect(api.importAirfoil.mock.calls[0][0]).toBe(file)
    expect(await screen.findByText(/natural geometric t\/c 0.11000/)).toBeVisible()
  })

  it('rejects an invalid import without applying or replacing the selected design', async () => {
    const user = userEvent.setup()
    const apply = vi.fn()
    api.importAirfoil.mockRejectedValueOnce(new Error('Leading edge is ambiguous'))
    render(<AirfoilSelector stationIndex={0} radius={.2} onApply={apply} onCancel={vi.fn()} />)
    await screen.findByText('Import DAT or CSV')
    await user.click(screen.getByText('Import DAT or CSV'))
    await user.upload(screen.getByLabelText('Airfoil coordinate file'), new File(['bad'], 'bad.dat'))
    await user.click(screen.getByRole('button', { name: 'Import and Preview' }))
    expect(await screen.findByText('Leading edge is ambiguous')).toBeVisible()
    expect(apply).not.toHaveBeenCalled()
  })
})
