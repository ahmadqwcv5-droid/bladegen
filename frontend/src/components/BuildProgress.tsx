import type { Job } from '../types/bladespec'

function formatElapsed(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds))
  const minutes = Math.floor(total / 60)
  const remainder = total % 60
  return `${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`
}

function failureCategory(stage: string): string {
  if (stage === 'solidification') return 'STEP topology failure'
  if (stage === 'geometry_validation') return 'Independent geometry-validation failure'
  if (stage === 'validation' || stage === 'resolution') return 'Input validation failure'
  return 'Build execution failure'
}

export function BuildProgress({ job }: { job?: Job }) {
  if (!job) return null
  return (
    <section className={`build-progress ${job.status}`} aria-live="polite">
      <div className="build-progress-heading">
        <div>
          <p className="eyebrow">Generating Blade</p>
          <h2>{job.stage_label}</h2>
        </div>
        <strong>{job.progress_percent}%</strong>
      </div>
      <div
        className="progress-track"
        role="progressbar"
        aria-label="Blade generation progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={job.progress_percent}
      >
        <span style={{ width: `${job.progress_percent}%` }} />
      </div>
      <dl>
        <dt>Status</dt><dd>{job.status}</dd>
        <dt>Elapsed</dt><dd>{formatElapsed(job.elapsed_seconds)}</dd>
        <dt>Current operation</dt><dd>{job.message}</dd>
      </dl>
      {job.status === 'running' && <span className="activity" aria-label="Build stage active" />}
      {job.error && <p className="build-error"><strong>{failureCategory(job.stage)}:</strong> {job.error}</p>}
    </section>
  )
}
