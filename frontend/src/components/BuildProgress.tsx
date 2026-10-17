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
  if (stage === 'blade_resolution' || stage === 'blade_generation') return 'Reference blade generation failure'
  if (stage === 'blade_copies') return 'Rotation/positioning failure'
  if (stage === 'hub_intersection') return 'Hub intersection failure'
  if (stage === 'fusion') return 'Boolean fusion failure'
  if (stage === 'bore') return 'Bore-cut failure'
  if (stage === 'assembly_validation' || stage === 'artifacts') return 'Final STEP validation failure'
  if (stage === 'validation' || stage === 'resolution') return 'Input validation failure'
  return 'Build execution failure'
}

export function BuildProgress({ job }: { job?: Job }) {
  if (!job) return null
  const product = job.build_type === 'propeller' ? 'Propeller' : 'Blade'
  const displayedProgress = job.status === 'succeeded' ? 100 : Math.min(job.progress_percent, 95)
  return (
    <section className={`build-progress ${job.status}`} aria-live="polite">
      <div className="build-progress-heading">
        <div>
          <p className="eyebrow">Generating {product}</p>
          <h2>{job.stage_label}</h2>
        </div>
        <strong>{displayedProgress}%</strong>
      </div>
      <div
        className="progress-track"
        role="progressbar"
        aria-label={`${product} generation progress`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={displayedProgress}
      >
        <span style={{ width: `${displayedProgress}%` }} />
      </div>
      <dl>
        <dt>Status</dt><dd>{job.status}</dd>
        <dt>Elapsed</dt><dd>{formatElapsed(job.elapsed_seconds)}</dd>
        <dt>Queue wait</dt><dd>{formatElapsed(job.queue_wait_seconds ?? 0)}</dd>
        <dt>Worker elapsed</dt><dd>{formatElapsed(job.worker_elapsed_seconds ?? 0)}</dd>
        <dt>Current operation</dt><dd>{job.message}</dd>
      </dl>
      {job.status === 'running' && <span className="activity" aria-label="Build stage active" />}
      {job.error && <p className="build-error"><strong>{failureCategory(job.stage)}:</strong> {job.error}</p>}
    </section>
  )
}
