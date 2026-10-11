import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import type { DistributionPreview } from '../types/bladespec'
import { DistributionChart } from './DistributionChart'

afterEach(() => cleanup())

it('renders backend samples separately from user controls and updates on new data', () => {
  const first: DistributionPreview = {
    interpolation: 'pchip', unit: 'mm',
    samples: [[.2, 64], [.6, 48], [1, 20]], controls: [[.2, 64], [1, 20]],
  }
  const { container, rerender } = render(<DistributionChart title="Chord Distribution" data={first} />)
  expect(screen.getByRole('img', { name: /canonical pchip distribution in mm/ })).toBeVisible()
  expect(container.querySelectorAll('.chart-control')).toHaveLength(2)
  const before = container.querySelector('.chart-line')?.getAttribute('points')
  rerender(<DistributionChart title="Chord Distribution" data={{ ...first, interpolation: 'linear', samples: [[.2, 70], [.6, 45], [1, 20]] }} />)
  expect(screen.getByRole('img', { name: /canonical linear distribution in mm/ })).toBeVisible()
  expect(container.querySelector('.chart-line')?.getAttribute('points')).not.toBe(before)
})
