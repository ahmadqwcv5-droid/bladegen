import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { Job } from '../types/bladespec'
import { BuildProgress } from './BuildProgress'

afterEach(() => cleanup())

function job(status: Job['status'], progress: number): Job {
  return {
    job_id: 'f'.repeat(32),
    build_type: 'blade',
    status,
    stage: status === 'succeeded' ? 'complete' : 'confirmation',
    stage_label: status === 'succeeded' ? 'Build complete' : 'Awaiting build confirmation',
    progress_percent: progress,
    message: 'Status from backend',
    elapsed_seconds: 1,
    error: status === 'failed' ? 'late failure' : null,
  }
}

describe('BuildProgress completion invariant', () => {
  it('never renders 100 percent for a running response', () => {
    render(<BuildProgress job={job('running', 100)} />)
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '95')
    expect(screen.getByText('95%')).toBeInTheDocument()
  })

  it('never renders 100 percent for a failed response', () => {
    render(<BuildProgress job={job('failed', 100)} />)
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '95')
  })

  it('renders 100 percent only for confirmed success', () => {
    render(<BuildProgress job={job('succeeded', 95)} />)
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100')
    expect(screen.getByText('100%')).toBeInTheDocument()
  })
})
