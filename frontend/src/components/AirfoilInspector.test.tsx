import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it } from 'vitest'
import type { PreviewStation, ProfileDiagnostics } from '../types/bladespec'
import '../sprint03a.css'
import { AirfoilInspector } from './AirfoilInspector'

afterEach(() => cleanup())

const metrics = { max_thickness_ratio: .12, max_thickness_x_over_c: .3, max_camber_ratio: .02, max_camber_x_over_c: .4, trailing_edge_gap_ratio: 0 }

function station(diagnostics?: ProfileDiagnostics): PreviewStation {
  return {
    r_over_R: .6, name: 'NACA 2412', kind: diagnostics ? 'coordinates' : 'naca4', local_chord_mm: 54,
    nominal_thickness_ratio: .12, effective_thickness_ratio: .12,
    requested_trailing_edge_thickness_mm: .8,
    source: { upper: [[0, 0], [.5, .07], [1, 0]], lower: [[0, 0], [.5, -.04], [1, 0]], metrics },
    resolved: { upper: [[0, 0], [.5, .07], [1, .008]], lower: [[0, 0], [.5, -.04], [1, -.008]], metrics: { ...metrics, trailing_edge_gap_ratio: .016 } },
    diagnostics,
    preview_status: 'canonical design definition; final CAD validation not yet performed',
  }
}

it('renders legible upper/lower contours at equal scale and switches source/resolved data', async () => {
  const user = userEvent.setup()
  const { container } = render(<AirfoilInspector station={station()} />)
  const plot = screen.getByRole('img', { name: /resolved airfoil coordinates/ })
  const upper = container.querySelector<SVGPolylineElement>('.airfoil-upper')!
  const lower = container.querySelector<SVGPolylineElement>('.airfoil-lower')!
  expect(plot).toBeVisible()
  expect(plot).toHaveAttribute('preserveAspectRatio', 'xMidYMid meet')
  expect(plot).toHaveAttribute('data-coordinate-scale', '1:1')
  expect(upper.getAttribute('points')).not.toBe(lower.getAttribute('points'))
  expect(getComputedStyle(upper).strokeWidth).toBe('2px')
  expect(getComputedStyle(lower).strokeWidth).toBe('2px')
  expect(screen.getByText('54.000 mm')).toBeVisible()
  expect(screen.getByText('0.800 mm')).toBeVisible()
  expect(screen.getByText(/final CAD validation not yet performed/)).toBeVisible()
  const resolvedPoints = upper.getAttribute('points')
  await user.click(screen.getByRole('button', { name: 'Source Profile' }))
  expect(screen.getByRole('img', { name: /source airfoil coordinates/ })).toBeVisible()
  expect(upper.getAttribute('points')).not.toBe(resolvedPoints)
  expect(screen.getByText('0.000% chord')).toBeVisible()
})

it('shows a non-blocking sparse warning without changing embedded coordinates', () => {
  const diagnostics: ProfileDiagnostics = {
    upper_point_count: 5, lower_point_count: 5, maximum_chordwise_spacing: .25,
    upper_leading_edge_point_count: 1, lower_leading_edge_point_count: 1,
    warning_codes: ['low_coordinate_density'], warnings: ['Sparse'], has_warning: true,
    advisory: 'Low coordinate density detected. OpenVSP surface reconstruction may deviate from the supplied polyline. Final STEP fidelity will be checked after generation.',
  }
  const value = station(diagnostics)
  const before = JSON.stringify(value.source)
  render(<AirfoilInspector station={value} />)
  expect(screen.getByRole('status', { name: 'Coordinate profile quality warning' })).toHaveTextContent('Upper surface5 points')
  expect(screen.getByRole('status')).toHaveTextContent('0.2500 c')
  expect(JSON.stringify(value.source)).toBe(before)
})
