import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { PreviewStation } from '../types/bladespec'
import { AirfoilComparison, type ComparisonChoice } from './AirfoilComparison'

const metricsA = { max_thickness_ratio: .15, max_thickness_x_over_c: .31, max_camber_ratio: .04, max_camber_x_over_c: .4, trailing_edge_gap_ratio: 0 }
const metricsB = { max_thickness_ratio: .103, max_thickness_x_over_c: .28, max_camber_ratio: .011, max_camber_x_over_c: .35, trailing_edge_gap_ratio: .01 }
const sourceA = { upper: [[0, 0], [.5, .075], [1, 0]], lower: [[0, 0], [.5, -.075], [1, 0]], metrics: metricsA }
const resolvedA = { upper: [[0, 0], [.5, .06], [1, .004]], lower: [[0, 0], [.5, -.06], [1, -.004]], metrics: { ...metricsA, max_thickness_ratio: .12, trailing_edge_gap_ratio: .008 } }
const sourceB = { upper: [[0, 0], [.4, .052], [1, .003]], lower: [[0, 0], [.4, -.051], [1, -.003]], metrics: metricsB }
const resolvedB = { upper: [[0, 0], [.4, .047], [1, .006]], lower: [[0, 0], [.4, -.046], [1, -.006]], metrics: { ...metricsB, max_thickness_ratio: .093, trailing_edge_gap_ratio: .012 } }

const station = (overrides: Partial<PreviewStation>): PreviewStation => ({
  r_over_R: .2,
  name: 'NACA 4415',
  kind: 'naca4',
  local_chord_mm: 64,
  nominal_thickness_ratio: .15,
  effective_thickness_ratio: .12,
  requested_trailing_edge_thickness_mm: .8,
  source: sourceA,
  resolved: resolvedA,
  preview_status: 'canonical design definition',
  ...overrides,
})

const choices: ComparisonChoice[] = [
  { id: 'a', index: 0, station: station({}) },
  { id: 'b', index: 3, station: station({ r_over_R: .8, name: 'Imported analytic 41-point', kind: 'coordinates', local_chord_mm: 31.5, effective_thickness_ratio: .093, requested_trailing_edge_thickness_mm: .4, source: sourceB, resolved: resolvedB }) },
]

afterEach(cleanup)

describe('AirfoilComparison', () => {
  it('renders canonical source coordinates on a shared undistorted scale and engineering metrics', () => {
    const before = JSON.stringify(choices)
    const { container } = render(<AirfoilComparison choices={choices} stationAId="a" stationBId="b" onStationA={vi.fn()} onStationB={vi.fn()} onClose={vi.fn()} />)
    const plot = screen.getByRole('img', { name: /source airfoil comparison/i })
    expect(plot).toHaveAttribute('data-coordinate-scale', '1:1')
    expect(plot).toHaveAttribute('data-profile-mode', 'source')
    expect(container.querySelector('[data-station="A-upper"]')).toHaveAttribute('points', '0,0 0.5,-0.075 1,0')
    expect(container.querySelector('[data-station="B-lower"]')).toHaveAttribute('points', '0,0 0.4,0.051 1,0.003')
    expect(screen.getByText('Imported analytic 41-point (coordinates)')).toBeInTheDocument()
    expect(screen.getByText('31.500 mm')).toBeInTheDocument()
    expect(screen.getByText('0.10300')).toBeInTheDocument()
    expect(JSON.stringify(choices)).toBe(before)
  })

  it('switches to backend-provided resolved coordinates including the finite trailing edge', async () => {
    const user = userEvent.setup()
    const { container } = render(<AirfoilComparison choices={choices} stationAId="a" stationBId="b" onStationA={vi.fn()} onStationB={vi.fn()} onClose={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: 'Resolved Design Profiles' }))
    expect(screen.getByRole('img', { name: /resolved airfoil comparison/i })).toHaveAttribute('data-profile-mode', 'resolved')
    expect(container.querySelector('[data-station="A-upper"]')).toHaveAttribute('points', '0,0 0.5,-0.06 1,-0.004')
    expect(container.querySelector('[data-station="B-lower"]')).toHaveAttribute('points', '0,0 0.4,0.046 1,0.006')
    expect(screen.getAllByText('0.09300')).toHaveLength(2)
  })

  it('keeps A/B selection controlled and returns to single inspection without editing data', () => {
    const onStationA = vi.fn()
    const onStationB = vi.fn()
    const onClose = vi.fn()
    render(<AirfoilComparison choices={choices} stationAId="a" stationBId="b" onStationA={onStationA} onStationB={onStationB} onClose={onClose} />)
    fireEvent.change(screen.getByLabelText('Comparison Station A'), { target: { value: 'b' } })
    fireEvent.change(screen.getByLabelText('Comparison Station B'), { target: { value: 'a' } })
    fireEvent.click(screen.getByRole('button', { name: 'Return to Single Station' }))
    expect(onStationA).toHaveBeenCalledWith('b')
    expect(onStationB).toHaveBeenCalledWith('a')
    expect(onClose).toHaveBeenCalledOnce()
  })
})
