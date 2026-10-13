import { useMemo, useRef, useState } from 'react'
import type { BladeSpec } from '../types/bladespec'
import { canonicalJson } from '../editor/bladespecEditor'
import {
  buildStationSetupCandidate,
  type StationSetupOptions,
} from '../editor/airfoilStationSetup'

type Props = {
  snapshot: BladeSpec
  profileNames: string[]
  onApply: (candidate: BladeSpec, label: string, expectedSnapshot: string) => Promise<boolean>
  onCommitted: (candidate: BladeSpec) => void
  onCancel: () => void
}

export function AirfoilStationSetupDialog({ snapshot, profileNames, onApply, onCommitted, onCancel }: Props) {
  const expectedSnapshot = useRef(canonicalJson(snapshot)).current
  const [options, setOptions] = useState<StationSetupOptions>({
    mode: 'uniform',
    count: snapshot.airfoil_sections.length,
    explicitRadii: snapshot.airfoil_sections.map(section => section.r_over_R).join('\n'),
    sourceStationIndex: 0,
    commonTrailingEdgeMm: snapshot.airfoil_sections[0].trailing_edge_thickness_mm,
    preserveMatchingStations: false,
    constantThicknessDistribution: false,
  })
  const [error, setError] = useState('')
  const [applying, setApplying] = useState(false)
  const candidate = useMemo(() => {
    try { return { value: buildStationSetupCandidate(snapshot, options), error: '' } }
    catch (reason) { return { value: undefined, error: reason instanceof Error ? reason.message : String(reason) } }
  }, [options, snapshot])
  const apply = async () => {
    if (!candidate.value) return
    setApplying(true)
    setError('')
    try {
      const accepted = await onApply(
        candidate.value.spec,
        `Set up ${candidate.value.radii.length} airfoil stations`,
        expectedSnapshot,
      )
      if (accepted) { onCommitted(candidate.value.spec); onCancel() }
      else setError('Station setup was not committed; review current validation messages.')
    } finally { setApplying(false) }
  }
  return <div className="selector-backdrop" role="dialog" aria-modal="true" aria-label="Set Up Airfoil Stations">
    <section className="bulk-dialog station-setup-dialog">
      <div className="section-title"><div><p className="eyebrow">PLACEMENT TEMPLATE</p><h2>Set Up Airfoil Stations</h2></div><button onClick={onCancel}>Cancel</button></div>
      <p>This organizes engineer-defined radial profile stations. It is not aerodynamic design and may change the loft.</p>
      <div className="grid">
        <label>Placement mode<select aria-label="Station placement mode" value={options.mode} onChange={event => setOptions({ ...options, mode: event.target.value as 'uniform' | 'explicit' })}><option value="uniform">Uniform root-to-tip count</option><option value="explicit">Explicit r/R list</option></select></label>
        {options.mode === 'uniform'
          ? <label>Total stations including root and tip<input aria-label="Total airfoil stations" type="number" min="2" max="64" value={options.count} onChange={event => setOptions({ ...options, count: Number(event.target.value) })} /></label>
          : <label>Explicit r/R values<textarea aria-label="Explicit airfoil station radii" rows={7} value={options.explicitRadii} onChange={event => setOptions({ ...options, explicitRadii: event.target.value })} /></label>}
        <label>Starting profile assignment<select aria-label="Station starting profile" value={options.sourceStationIndex} onChange={event => setOptions({ ...options, sourceStationIndex: Number(event.target.value) })}>{snapshot.airfoil_sections.map((section, index) => <option key={section.r_over_R} value={index}>{profileNames[index] ?? `Station ${index + 1}`} · r/R {section.r_over_R}</option>)}</select></label>
        <label>Common physical TE (mm)<input aria-label="Common station trailing edge" type="number" step="any" value={options.commonTrailingEdgeMm} onChange={event => setOptions({ ...options, commonTrailingEdgeMm: Number(event.target.value) })} /></label>
        <label className="inline"><input type="checkbox" checked={options.preserveMatchingStations} onChange={event => setOptions({ ...options, preserveMatchingStations: event.target.checked })} /> Preserve complete assignments and TE for existing stations at matching radii</label>
        <label className="inline"><input type="checkbox" checked={options.constantThicknessDistribution} onChange={event => setOptions({ ...options, constantThicknessDistribution: event.target.checked })} /> Replace Thickness with a reviewed two-point constant matching the selected common profile</label>
      </div>
      {(error || candidate.error) && <div className="error-panel" role="alert">{error || candidate.error}</div>}
      {candidate.value && <div className="candidate-review">
        <h3>Review station replacement</h3>
        <p>{snapshot.airfoil_sections.length} → {candidate.value.radii.length} stations · {candidate.value.retainedCount} retained · {candidate.value.assignedCount} assigned from {profileNames[options.sourceStationIndex] ?? `station ${options.sourceStationIndex + 1}`}.</p>
        <p>Radii: {candidate.value.radii.map(radius => Number(radius.toPrecision(12))).join(', ')}</p>
        <p>Thickness coordination controls: {candidate.value.oldThicknessPointCount} → {candidate.value.newThicknessPointCount}. Chord, Twist, Rake, and Skew remain unchanged.</p>
        <p className="hint">A real station replacement marks existing CAD stale. It does not claim that the previous loft is preserved.</p>
        <div className="dialog-actions"><button onClick={onCancel}>Cancel</button><button className="primary" disabled={applying || !candidate.value.changed} onClick={() => void apply()}>{applying ? 'Validating candidate…' : candidate.value.changed ? 'Apply Once' : 'No Changes'}</button></div>
      </div>}
    </section>
  </div>
}
