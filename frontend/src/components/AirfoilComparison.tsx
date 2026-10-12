import { useMemo, useState } from 'react'
import type { PreviewStation } from '../types/bladespec'

export type ComparisonChoice = { id: string; index: number; station: PreviewStation }

const points = (values: number[][]) => values.map(([x, y]) => `${x},${-y}`).join(' ')

export function AirfoilComparison({
  choices,
  stationAId,
  stationBId,
  onStationA,
  onStationB,
  onClose,
}: {
  choices: ComparisonChoice[]
  stationAId: string
  stationBId: string
  onStationA: (id: string) => void
  onStationB: (id: string) => void
  onClose: () => void
}) {
  const [mode, setMode] = useState<'source' | 'resolved'>('source')
  const a = choices.find(choice => choice.id === stationAId) ?? choices[0]
  const b = choices.find(choice => choice.id === stationBId) ?? choices.find(choice => choice.id !== a?.id)
  const geometry = useMemo(() => {
    if (!a || !b) return undefined
    const contourA = a.station[mode]
    const contourB = b.station[mode]
    const all = [...contourA.upper, ...contourA.lower, ...contourB.upper, ...contourB.lower]
    const minimumX = Math.min(0, ...all.map(point => point[0])) - .035
    const maximumX = Math.max(1, ...all.map(point => point[0])) + .035
    const maximumAbsY = Math.max(.06, ...all.map(point => Math.abs(point[1]))) * 1.22
    return { contourA, contourB, minimumX, maximumX, maximumAbsY }
  }, [a, b, mode])
  if (!a || !b || !geometry) return <p className="hint">At least two current preview stations are required for comparison.</p>

  const measurementRows: [string, string, string][] = [
    ['r/R', a.station.r_over_R.toFixed(4), b.station.r_over_R.toFixed(4)],
    ['Airfoil', `${a.station.name} (${a.station.kind})`, `${b.station.name} (${b.station.kind})`],
    ['Chord', `${a.station.local_chord_mm.toFixed(3)} mm`, `${b.station.local_chord_mm.toFixed(3)} mm`],
    ['Effective t/c', a.station.effective_thickness_ratio.toFixed(5), b.station.effective_thickness_ratio.toFixed(5)],
    ['Geometric max t/c', geometry.contourA.metrics.max_thickness_ratio.toFixed(5), geometry.contourB.metrics.max_thickness_ratio.toFixed(5)],
    ['Maximum camber/c', geometry.contourA.metrics.max_camber_ratio.toFixed(5), geometry.contourB.metrics.max_camber_ratio.toFixed(5)],
    ['x/c at max thickness', geometry.contourA.metrics.max_thickness_x_over_c.toFixed(4), geometry.contourB.metrics.max_thickness_x_over_c.toFixed(4)],
    ['Requested physical TE', `${a.station.requested_trailing_edge_thickness_mm.toFixed(3)} mm`, `${b.station.requested_trailing_edge_thickness_mm.toFixed(3)} mm`],
  ]

  return <section className="airfoil-comparison" aria-label="Airfoil station comparison">
    <div className="section-title">
      <div><p className="eyebrow">CURRENT DESIGN · GEOMETRIC COMPARISON</p><h3>Compare Stations</h3></div>
      <button onClick={onClose}>Return to Single Station</button>
    </div>
    <div className="comparison-controls">
      <label>Station A<select aria-label="Comparison Station A" value={a.id} onChange={event => onStationA(event.target.value)}>{choices.map(choice => <option key={choice.id} value={choice.id} disabled={choice.id === b.id}>Station {choice.index + 1} · r/R {choice.station.r_over_R.toFixed(4)}</option>)}</select></label>
      <label>Station B<select aria-label="Comparison Station B" value={b.id} onChange={event => onStationB(event.target.value)}>{choices.map(choice => <option key={choice.id} value={choice.id} disabled={choice.id === a.id}>Station {choice.index + 1} · r/R {choice.station.r_over_R.toFixed(4)}</option>)}</select></label>
      <div className="view-tabs" role="group" aria-label="Comparison profile definition">
        <button aria-pressed={mode === 'source'} onClick={() => setMode('source')}>Source Profiles</button>
        <button aria-pressed={mode === 'resolved'} onClick={() => setMode('resolved')}>Resolved Design Profiles</button>
      </div>
    </div>
    <div className="comparison-legend"><span className="legend-a">Station A · {a.index + 1}</span><span className="legend-b">Station B · {b.index + 1}</span></div>
    <svg className="comparison-plot" viewBox={`${geometry.minimumX} ${-geometry.maximumAbsY} ${geometry.maximumX - geometry.minimumX} ${2 * geometry.maximumAbsY}`} preserveAspectRatio="xMidYMid meet" data-coordinate-scale="1:1" data-profile-mode={mode} role="img" aria-label={`${mode} airfoil comparison for Station A ${a.index + 1} and Station B ${b.index + 1}`}>
      <line className="plot-axis" x1={geometry.minimumX} y1="0" x2={geometry.maximumX} y2="0" />
      <line className="plot-grid" x1="0" y1={-geometry.maximumAbsY} x2="0" y2={geometry.maximumAbsY} />
      <line className="plot-grid" x1="1" y1={-geometry.maximumAbsY} x2="1" y2={geometry.maximumAbsY} />
      <polyline className="comparison-a" data-station="A-upper" points={points(geometry.contourA.upper)} />
      <polyline className="comparison-a" data-station="A-lower" points={points(geometry.contourA.lower)} />
      <polyline className="comparison-b" data-station="B-upper" points={points(geometry.contourB.upper)} />
      <polyline className="comparison-b" data-station="B-lower" points={points(geometry.contourB.lower)} />
    </svg>
    <p className="axis-labels"><span>LE · x/c 0</span><span>equal x/y scale</span><span>TE · x/c 1</span></p>
    <div className="comparison-table-scroll"><table><thead><tr><th>Measurement</th><th>Station A</th><th>Station B</th></tr></thead><tbody>{measurementRows.map(([label, valueA, valueB]) => <tr key={label}><th>{label}</th><td>{valueA}</td><td>{valueB}</td></tr>)}</tbody></table></div>
    <p className="hint">Canonical backend preview coordinates; geometric comparison only. No aerodynamic, structural, or final STEP-section claim is implied.</p>
  </section>
}
