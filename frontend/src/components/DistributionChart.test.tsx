import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { StrictMode, useState } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import type { DistributionPreview } from '../types/bladespec'
import { CHART_HEIGHT, CHART_MARGIN, CHART_WIDTH, clientPointToSvg, DistributionChart, nearestSampleIndex, valueFromSvgY } from './DistributionChart'

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

it('converts client coordinates through scaling, letterboxing, and scrolled offsets', () => {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
  Object.defineProperty(svg, 'getScreenCTM', { configurable: true, value: () => null })
  Object.defineProperty(svg, 'getBoundingClientRect', { configurable: true, value: () => ({ ...bounds(1000, 260), left: 100, top: 250 }) })
  expect(clientPointToSvg(svg, 280, 250)).toEqual({ x: 0, y: 0 })
  expect(clientPointToSvg(svg, 600, 380)).toEqual({ x: 320, y: 130 })
  expect(clientPointToSvg(svg, 920, 510)).toEqual({ x: 640, y: 260 })
  expect(valueFromSvgY(CHART_MARGIN.top, -10, 30)).toBe(30)
  expect(valueFromSvgY(CHART_HEIGHT - CHART_MARGIN.bottom, -10, 30)).toBe(-10)
  expect(valueFromSvgY((CHART_MARGIN.top + CHART_HEIGHT - CHART_MARGIN.bottom) / 2, -10, 30)).toBe(10)
})

it('drags vertically with stable r/R, exposes a draft, and commits once on release', async () => {
  const commit = vi.fn(async (_index: number, _value: number) => true)
  const interaction = vi.fn()
  const { container } = render(<DistributionChart
    title="Chord Distribution" data={first}
    controls={[{ radius: .2, value: 64 }, { radius: 1, value: 20 }]}
    unit="mm" step={.5} onCommit={commit} onInteractionChange={interaction}
  />)
  const svg = container.querySelector('svg')!
  Object.defineProperty(svg, 'getBoundingClientRect', { configurable: true, value: () => bounds(CHART_WIDTH, CHART_HEIGHT) })
  const marker = screen.getByRole('slider', { name: /control 1/ })
  fireEvent.pointerDown(marker, { pointerId: 7, clientX: 58, clientY: 37 })
  fireEvent.pointerMove(svg, { pointerId: 7, clientX: 500, clientY: CHART_MARGIN.top })
  expect(screen.getByText(/Draft · r\/R 0\.2000/)).toBeVisible()
  expect(commit).not.toHaveBeenCalled()
  fireEvent.pointerUp(svg, { pointerId: 7, clientX: 500, clientY: CHART_MARGIN.top })
  await waitFor(() => expect(commit).toHaveBeenCalledTimes(1))
  expect(commit.mock.calls[0][0]).toBe(0)
  expect(commit.mock.calls[0][1]).toBeCloseTo(69.28)
})

it('supports keyboard increments and prevents locked controls from editing', async () => {
  const commit = vi.fn(async (_index: number, _value: number) => true)
  const { rerender } = render(<DistributionChart title="Twist Distribution" data={{ ...first, unit: 'deg' }} controls={[{ radius: .2, value: 23 }]} unit="deg" step={.25} onCommit={commit} />)
  fireEvent.keyDown(screen.getByRole('slider'), { key: 'ArrowUp', shiftKey: true })
  await waitFor(() => expect(commit).toHaveBeenCalledWith(0, 25.5))
  rerender(<DistributionChart title="Thickness Distribution" data={{ ...first, unit: '% t/c' }} controls={[{ radius: .2, value: 12, lockedReason: 'Natural t/c protected' }]} unit="% t/c" onCommit={commit} />)
  expect(screen.getByRole('slider')).toHaveAttribute('tabindex', '-1')
  fireEvent.pointerDown(screen.getByRole('slider'), { pointerId: 9 })
  expect(commit).toHaveBeenCalledTimes(1)
})

it('does not commit clicks or pointer motion below the intent threshold', async () => {
  const commit = vi.fn(async (_index: number, _value: number) => true)
  const interaction = vi.fn()
  const { container } = render(<DistributionChart title="Chord Distribution" data={first} controls={[{ radius: .2, value: 64 }]} unit="mm" onCommit={commit} onInteractionChange={interaction} />)
  const svg = container.querySelector('svg')!
  const marker = screen.getByRole('slider')
  fireEvent.pointerDown(marker, { pointerId: 20, clientX: 100, clientY: 100 })
  fireEvent.pointerUp(svg, { pointerId: 20, clientX: 100, clientY: 100 })
  fireEvent.pointerDown(marker, { pointerId: 21, clientX: 100, clientY: 100 })
  fireEvent.pointerMove(svg, { pointerId: 21, clientX: 102, clientY: 101 })
  fireEvent.pointerUp(svg, { pointerId: 21, clientX: 102, clientY: 101 })
  expect(commit).not.toHaveBeenCalled()
  expect(interaction).toHaveBeenLastCalledWith('idle')
})

it('recovers from rejection, Escape, and pointer cancellation for the next gesture', async () => {
  const commit = vi.fn()
    .mockRejectedValueOnce(new Error('network unavailable'))
    .mockResolvedValue(true)
  const error = vi.fn()
  const { container } = render(<DistributionChart title="Chord Distribution" data={first} controls={[{ radius: .2, value: 64 }]} unit="mm" onCommit={commit} onError={error} />)
  const svg = container.querySelector('svg')!
  const marker = screen.getByRole('slider')
  const meaningful = async (pointerId: number) => {
    fireEvent.pointerDown(marker, { pointerId, clientX: 100, clientY: 100 })
    fireEvent.pointerMove(svg, { pointerId, clientX: 100, clientY: 80 })
    fireEvent.pointerUp(svg, { pointerId, clientX: 100, clientY: 80 })
  }
  await meaningful(30)
  await waitFor(() => expect(error).toHaveBeenCalledWith('Curve edit failed: network unavailable'))
  await meaningful(31)
  await waitFor(() => expect(commit).toHaveBeenCalledTimes(2))
  fireEvent.pointerDown(marker, { pointerId: 32, clientX: 100, clientY: 100 })
  fireEvent.keyDown(window, { key: 'Escape' })
  fireEvent.pointerDown(marker, { pointerId: 33, clientX: 100, clientY: 100 })
  fireEvent.pointerCancel(svg, { pointerId: 33 })
  await meaningful(34)
  await waitFor(() => expect(commit).toHaveBeenCalledTimes(3))
})

it('invalidates a superseded validation through explicit parent cancellation', async () => {
  let resolveFirst!: (accepted: boolean) => void
  const commit = vi.fn()
    .mockImplementationOnce(() => new Promise<boolean>(resolve => { resolveFirst = resolve }))
    .mockResolvedValue(true)
  const interaction = vi.fn()
  const props = { title: 'Chord Distribution', data: first, controls: [{ radius: .2, value: 64 }], unit: 'mm', onCommit: commit, onInteractionChange: interaction }
  const { container, rerender } = render(<DistributionChart {...props} cancelVersion={0} />)
  const svg = container.querySelector('svg')!
  const drag = (pointerId: number, y: number) => {
    fireEvent.pointerDown(screen.getByRole('slider'), { pointerId, clientX: 100, clientY: 100 })
    fireEvent.pointerMove(svg, { pointerId, clientX: 100, clientY: y })
    fireEvent.pointerUp(svg, { pointerId, clientX: 100, clientY: y })
  }
  drag(50, 75)
  await waitFor(() => expect(commit).toHaveBeenCalledTimes(1))
  rerender(<DistributionChart {...props} cancelVersion={1} />)
  drag(51, 85)
  await waitFor(() => expect(commit).toHaveBeenCalledTimes(2))
  await act(async () => { resolveFirst(true); await Promise.resolve() })
  expect(interaction).toHaveBeenLastCalledWith('idle')
})

it('does not update or report an obsolete component after pending validation unmounts', async () => {
  let rejectCommit!: (reason: Error) => void
  const commit = vi.fn(() => new Promise<boolean>((_resolve, reject) => { rejectCommit = reject }))
  const interaction = vi.fn()
  const error = vi.fn()
  const { container, unmount } = render(<DistributionChart title="Chord Distribution" data={first} controls={[{ radius: .2, value: 64 }]} unit="mm" onCommit={commit} onInteractionChange={interaction} onError={error} />)
  const svg = container.querySelector('svg')!
  fireEvent.pointerDown(screen.getByRole('slider'), { pointerId: 60, clientX: 100, clientY: 100 })
  fireEvent.pointerMove(svg, { pointerId: 60, clientX: 100, clientY: 75 })
  fireEvent.pointerUp(svg, { pointerId: 60, clientX: 100, clientY: 75 })
  await waitFor(() => expect(commit).toHaveBeenCalledOnce())
  error.mockClear()
  unmount()
  await act(async () => { rejectCommit(new Error('late network failure')); await Promise.resolve() })
  expect(error).not.toHaveBeenCalled()
  expect(interaction).toHaveBeenLastCalledWith('validating')
})

it('supports repeated same-marker drags under StrictMode without a remount workaround', async () => {
  const commits = vi.fn(async (_index: number, _value: number) => true)
  function Harness() {
    const [value, setValue] = useState(23)
    const [interaction, setInteraction] = useState<'idle' | 'drafting' | 'validating'>('idle')
    return <><output>{interaction}</output><DistributionChart
      title="Twist Distribution" data={{ ...first, unit: 'deg' }} controls={[{ radius: .65, value }]}
      unit="deg" onInteractionChange={setInteraction}
      onCommit={async (index, next) => { const accepted = await commits(index, next); setValue(next); return accepted }}
    /></>
  }
  const { container } = render(<StrictMode><Harness /></StrictMode>)
  const svg = container.querySelector('svg')!
  Object.defineProperty(svg, 'getBoundingClientRect', { configurable: true, value: () => bounds(CHART_WIDTH, CHART_HEIGHT) })
  for (let edit = 0; edit < 3; edit += 1) {
    const marker = screen.getByRole('slider')
    const pointerId = 40 + edit
    fireEvent.pointerDown(marker, { pointerId, clientX: 100, clientY: 100 })
    fireEvent.pointerMove(svg, { pointerId, clientX: 100, clientY: 75 + edit * 8 })
    fireEvent.pointerUp(svg, { pointerId, clientX: 100, clientY: 75 + edit * 8 })
    await waitFor(() => expect(screen.getByText('idle')).toBeVisible())
    await waitFor(() => expect(commits).toHaveBeenCalledTimes(edit + 1))
  }
})
