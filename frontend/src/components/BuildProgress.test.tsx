import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { BuildProgress } from './BuildProgress'
import type { Job } from '../types/bladespec'

afterEach(() => cleanup())

const job = (status: Job['status'], progress: number, stage = 'openvsp'): Job => ({
  job_id: 'a'.repeat(32),
  status,
  stage,
  stage_label: stage === 'complete' ? 'Build complete' : 'Generating blade surfaces',
  progress_percent: progress,
  message: stage === 'complete' ? 'Artifacts ready' : 'OpenVSP is constructing the blade geometry',
  elapsed_seconds: 38.4,
  error: status === 'failed' ? 'OpenVSP geometry failed' : null,
})

describe('BuildProgress', () => {
  it('shows backend queue and running progress accessibly', () => {
    const { rerender } = render(<BuildProgress job={job('queued', 0, 'queued')} />)
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0')
    rerender(<BuildProgress job={job('running', 18)} />)
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '18')
    expect(screen.getByText('OpenVSP is constructing the blade geometry')).toBeInTheDocument()
    expect(screen.getByText('00:38')).toBeInTheDocument()
  })

  it('shows success only at backend-confirmed 100 percent', () => {
    render(<BuildProgress job={job('succeeded', 100, 'complete')} />)
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100')
    expect(screen.getByText('Build complete')).toBeInTheDocument()
  })

  it('retains the confirmed failure stage and error', () => {
    render(<BuildProgress job={job('failed', 18)} />)
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '18')
    expect(screen.getByText(/OpenVSP geometry failed/)).toBeInTheDocument()
  })

  it('distinguishes topology and independent geometry failures', () => {
    const topology = { ...job('failed', 52, 'solidification'), error: 'shell remained open' }
    const { rerender } = render(<BuildProgress job={topology} />)
    expect(screen.getByText(/STEP topology failure/)).toBeInTheDocument()
    const geometry = { ...job('failed', 80, 'geometry_validation'), error: 'section mismatch' }
    rerender(<BuildProgress job={geometry} />)
    expect(screen.getByText(/Independent geometry-validation failure/)).toBeInTheDocument()
  })
})
