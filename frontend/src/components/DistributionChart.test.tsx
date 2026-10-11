import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import type { DistributionPreview } from '../types/bladespec'
import { CHART_HEIGHT, CHART_MARGIN, CHART_WIDTH, DistributionChart, nearestSampleIndex } from './DistributionChart'

afterEach(() => cleanup())

const first: DistributionPreview = {
  interpolation: 'pchip', unit: 'mm',
  samples: [[.2, 64], [.4, 59], [.6, 48], [.8, 31], [1, 20]], controls: [[.2, 64], [1, 20]],
}

function bounds(width: number, height: number) {
  return { x: 0, y: 0, left: 0, top: 0, right: width, bottom: height, width, height, toJSON: () => ({}) }
}

function hoverAtSvgX(svg: SVGSVGElement, svgX: number, renderedWidth = CHART_WIDTH, renderedHeight = CHART_HEIGHT) {
  Object.defineProperty(svg, 'getBoundingClientRect', { configurable: true, value: () => bounds(renderedWidth, renderedHeight) })
  const scale = Math.min(renderedWidth / CHART_WIDTH, renderedHeight / CHART_HEIGHT)
  const contentLeft = (renderedWidth - CHART_WIDTH * scale) / 2
  fireEvent.mouseMove(svg, { clientX: contentLeft + svgX * scale, clientY: 100 })
}

it('renders backend samples separately from user controls and updates on new data', () => {
  const { container, rerender } = render(<DistributionChart title="Chord Distribution" data={first} />)
  expect(screen.getByRole('img', { name: /canonical pchip distribution in mm/ })).toBeVisible()
  expect(container.querySelectorAll('.chart-control')).toHaveLength(2)
  const before = container.querySelector('.chart-line')?.getAttribute('points')
  rerender(<DistributionChart title="Chord Distribution" data={{ ...first, interpolation: 'linear', samples: [[.2, 70], [.6, 45], [1, 20]] }} />)
  expect(screen.getByRole('img', { name: /canonical linear distribution in mm/ })).toBeVisible()
  expect(container.querySelector('.chart-line')?.getAttribute('points')).not.toBe(before)
})

it('maps plot boundaries and midpoint to nearest canonical samples after resize', () => {
  const { container } = render(<DistributionChart title="Chord Distribution" data={first} />)
  const svg = container.querySelector('svg')!
  hoverAtSvgX(svg, CHART_MARGIN.left)
  expect(screen.getByText(/r\/R 0\.2000 · 64\.0000 mm/)).toBeVisible()
  hoverAtSvgX(svg, CHART_WIDTH - CHART_MARGIN.right)
  expect(screen.getByText(/r\/R 1\.0000 · 20\.0000 mm/)).toBeVisible()
  hoverAtSvgX(svg, (CHART_MARGIN.left + CHART_WIDTH - CHART_MARGIN.right) / 2, 320, 200)
  expect(screen.getByText(/r\/R 0\.6000 · 48\.0000 mm/)).toBeVisible()
})

it('chooses a backend sample within half local spacing for an intermediate pointer', () => {
  expect(nearestSampleIndex(first.samples, .31)).toBe(1)
  expect(Math.abs(first.samples[1][0] - .31)).toBeLessThanOrEqual(.1)
})
