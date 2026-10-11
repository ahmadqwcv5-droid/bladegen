import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it } from 'vitest'
import type { PreviewStation } from '../types/bladespec'
import { AirfoilInspector } from './AirfoilInspector'

afterEach(() => cleanup())

it('distinguishes source and resolved design profiles and reports engineering values', async () => {
  const user = userEvent.setup()
  const metrics = { max_thickness_ratio: .12, max_thickness_x_over_c: .3, max_camber_ratio: .02, max_camber_x_over_c: .4, trailing_edge_gap_ratio: 0 }
  const station: PreviewStation = {
    r_over_R: .6, name: 'NACA 2412', kind: 'naca4', local_chord_mm: 54,
    nominal_thickness_ratio: .12, effective_thickness_ratio: .12,
    requested_trailing_edge_thickness_mm: .8,
    source: { upper: [[0, 0], [.5, .07], [1, 0]], lower: [[0, 0], [.5, -.04], [1, 0]], metrics },
    resolved: { upper: [[0, 0], [.5, .07], [1, .008]], lower: [[0, 0], [.5, -.04], [1, -.008]], metrics: { ...metrics, trailing_edge_gap_ratio: .016 } },
    preview_status: 'canonical design definition; final CAD validation not yet performed',
  }
  render(<AirfoilInspector station={station} />)
  expect(screen.getByRole('img', { name: /resolved airfoil coordinates/ })).toBeVisible()
  expect(screen.getByText('54.000 mm')).toBeVisible()
  expect(screen.getByText('0.800 mm')).toBeVisible()
  expect(screen.getByText(/final CAD validation not yet performed/)).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'Source Profile' }))
  expect(screen.getByRole('img', { name: /source airfoil coordinates/ })).toBeVisible()
  expect(screen.getByText('0.000% chord')).toBeVisible()
})
