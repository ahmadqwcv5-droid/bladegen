import { useMemo, useState } from 'react'
import type { AirfoilMetrics, AirfoilProfile, PreviewStation, ProfileDiagnostics } from '../types/bladespec'

type Contour = { upper: number[][]; lower: number[][]; metrics: AirfoilMetrics }

function pointsAttribute(points: number[][]): string {
  return points.map(([x, y]) => `${x},${-y}`).join(' ')
}

function QualityWarning({ diagnostics }: { diagnostics?: ProfileDiagnostics }) {
  if (!diagnostics?.has_warning) return null
  return <div className="profile-quality-warning" role="status" aria-label="Coordinate profile quality warning">
    <strong>Warning: Sparse coordinate definition</strong>
    <p>{diagnostics.advisory}</p>
    <dl>
      <dt>Upper surface</dt><dd>{diagnostics.upper_point_count} points</dd>
      <dt>Lower surface</dt><dd>{diagnostics.lower_point_count} points</dd>
      <dt>Maximum chordwise spacing</dt><dd>{diagnostics.maximum_chordwise_spacing.toFixed(4)} c</dd>
    </dl>
  </div>
}

export function AirfoilInspector({
  station,
  profile,
}: {
  station?: PreviewStation
  profile?: AirfoilProfile
}) {
  const [mode, setMode] = useState<'source' | 'resolved'>('resolved')
  const profileContour = useMemo<Contour | undefined>(() => {
    const coordinates = profile?.source_coordinates
      ?? (profile?.airfoil.type === 'coordinates' ? profile.airfoil : undefined)
    return coordinates && profile ? {
      upper: coordinates.upper,
      lower: coordinates.lower,
      metrics: profile.metrics,
    } : undefined
  }, [profile])
  const contour = station
    ? (mode === 'source' ? station.source : station.resolved)
    : profileContour
  if (!contour) return <p className="hint">Select an airfoil to inspect its canonical coordinates.</p>

  const all = [...contour.upper, ...contour.lower]
  const minimumX = Math.min(0, ...all.map(point => point[0])) - .035
  const maximumX = Math.max(1, ...all.map(point => point[0])) + .035
  const maximumAbsY = Math.max(.06, ...all.map(point => Math.abs(point[1]))) * 1.22
  const title = station ? `${station.name} at r/R ${station.r_over_R.toFixed(4)}` : profile?.display_name
  const diagnostics = station?.diagnostics ?? profile?.diagnostics

  return (
    <section className="airfoil-inspector" aria-label="2D Airfoil Inspector">
      <div className="section-title">
        <div><p className="eyebrow">Design-definition preview</p><h3>{title}</h3></div>
        {station && <div className="view-tabs" role="group" aria-label="Airfoil definition view">
          <button aria-pressed={mode === 'source'} onClick={() => setMode('source')}>Source Profile</button>
          <button aria-pressed={mode === 'resolved'} onClick={() => setMode('resolved')}>Resolved Design Profile</button>
        </div>}
      </div>
      <svg
        className="airfoil-plot"
        viewBox={`${minimumX} ${-maximumAbsY} ${maximumX - minimumX} ${2 * maximumAbsY}`}
        preserveAspectRatio="xMidYMid meet"
        data-coordinate-scale="1:1"
        data-profile-mode={station ? mode : 'source'}
        role="img"
        aria-label={`${title} ${station ? mode : 'source'} airfoil coordinates`}
      >
        <line className="plot-axis" x1={minimumX} y1="0" x2={maximumX} y2="0" />
        <line className="plot-grid" x1="0" y1={-maximumAbsY} x2="0" y2={maximumAbsY} />
        <line className="plot-grid" x1="1" y1={-maximumAbsY} x2="1" y2={maximumAbsY} />
        <polyline className="airfoil-upper" data-surface="upper" points={pointsAttribute(contour.upper)} />
        <polyline className="airfoil-lower" data-surface="lower" points={pointsAttribute(contour.lower)} />
        <circle className="leading-edge" cx="0" cy="0" r=".006" />
        <circle className="trailing-edge" cx="1" cy={-(contour.upper.at(-1)?.[1] ?? 0)} r=".006" />
      </svg>
      <div className="axis-labels"><span>LE · x/c 0</span><span>x/c → · equal x/y scale</span><span>TE · x/c 1</span></div>
      <dl className="inspector-metrics">
        {station && <><dt>Local chord</dt><dd>{station.local_chord_mm.toFixed(3)} mm</dd></>}
        {station && <><dt>Nominal / effective t/c</dt><dd>{station.nominal_thickness_ratio.toFixed(4)} / {station.effective_thickness_ratio.toFixed(4)}</dd></>}
        <dt>Geometric max t/c</dt><dd>{contour.metrics.max_thickness_ratio.toFixed(5)} at x/c {contour.metrics.max_thickness_x_over_c.toFixed(3)}</dd>
        <dt>Maximum camber</dt><dd>{contour.metrics.max_camber_ratio.toFixed(5)} at x/c {contour.metrics.max_camber_x_over_c.toFixed(3)}</dd>
        <dt>Source TE gap</dt><dd>{(contour.metrics.trailing_edge_gap_ratio * 100).toFixed(3)}% chord</dd>
        {station && <><dt>Requested physical TE</dt><dd>{station.requested_trailing_edge_thickness_mm.toFixed(3)} mm</dd></>}
      </dl>
      <QualityWarning diagnostics={diagnostics} />
      <p className="hint">{station?.preview_status ?? 'Canonical source profile; no final CAD validation is implied.'}</p>
    </section>
  )
}
