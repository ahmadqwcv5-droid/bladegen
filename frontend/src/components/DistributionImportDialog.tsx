import { useEffect, useMemo, useRef, useState } from 'react'
import type { BladeSpec } from '../types/bladespec'
import { CURVES } from '../editor/curveEditing'
import { canonicalJson } from '../editor/bladespecEditor'
import {
  buildDistributionCandidate,
  parseDelimitedTable,
  sortTableByRadius,
  suggestedImportPlan,
  unitsForCurve,
  unmappedColumns,
  type DelimitedTable,
  type DistributionImportPlan,
  type ImportUnit,
} from '../editor/distributionImport'

type Props = {
  snapshot: BladeSpec
  onApply: (candidate: BladeSpec, label: string, expectedSnapshot: string, signal: AbortSignal) => Promise<boolean>
  onCancel: () => void
}

export function DistributionImportDialog({ snapshot, onApply, onCancel }: Props) {
  const expectedSnapshot = useRef(canonicalJson(snapshot)).current
  const transaction = useRef<AbortController | undefined>(undefined)
  const [paste, setPaste] = useState('')
  const [table, setTable] = useState<DelimitedTable>()
  const [plan, setPlan] = useState<DistributionImportPlan>()
  const [parseDurationMs, setParseDurationMs] = useState<number>()
  const [error, setError] = useState('')
  const [applying, setApplying] = useState(false)
  useEffect(() => () => transaction.current?.abort(), [])
  const cancel = () => {
    transaction.current?.abort()
    onCancel()
  }

  const review = (text: string, sourceName: string) => {
    const started = performance.now()
    try {
      const parsed = parseDelimitedTable(text, sourceName)
      setTable(parsed)
      setPlan(suggestedImportPlan(parsed, snapshot))
      setError('')
      setParseDurationMs(performance.now() - started)
    } catch (reason) {
      setTable(undefined)
      setPlan(undefined)
      setError(reason instanceof Error ? reason.message : String(reason))
      setParseDurationMs(performance.now() - started)
    }
  }
  const candidate = useMemo(() => {
    if (!table || !plan) return { value: undefined, error: '' }
    try { return { value: buildDistributionCandidate(snapshot, table, plan), error: '' } }
    catch (reason) { return { value: undefined, error: reason instanceof Error ? reason.message : String(reason) } }
  }, [plan, snapshot, table])
  const updateSelection = (curve: typeof CURVES[number], column: string) => {
    if (!plan) return
    const selections = { ...plan.selections }
    if (!column) delete selections[curve.name]
    else {
      const current = selections[curve.name]
      selections[curve.name] = {
        column,
        unit: current && unitsForCurve(curve.name).includes(current.unit)
          ? current.unit
          : unitsForCurve(curve.name)[0],
        interpolation: current?.interpolation ?? snapshot[curve.key].interpolation,
      }
    }
    setPlan({ ...plan, selections })
  }
  const apply = async () => {
    if (!candidate.value) return
    const controller = new AbortController()
    transaction.current = controller
    setApplying(true)
    setError('')
    try {
      const accepted = await onApply(
        candidate.value.spec,
        `Import ${candidate.value.summaries.map(summary => summary.title).join('/')} distributions`,
        expectedSnapshot,
        controller.signal,
      )
      if (controller.signal.aborted) return
      if (accepted) onCancel()
      else setError('The import was not committed; review current validation messages.')
    } finally {
      if (transaction.current === controller) transaction.current = undefined
      if (!controller.signal.aborted) setApplying(false)
    }
  }
  const unknown = table && plan ? unmappedColumns(table, plan) : []

  return <div className="selector-backdrop" role="dialog" aria-modal="true" aria-label="Import Distributions">
    <section className="bulk-dialog">
      <div className="section-title"><div><p className="eyebrow">ENGINEERING TRANSACTION</p><h2>Import Distributions</h2></div><button onClick={cancel}>Cancel</button></div>
      <p>Paste spreadsheet cells or choose a UTF-8 CSV. Review mappings, units, interpolation, and point counts before replacing only the selected distributions.</p>
      <div className="bulk-source-grid">
        <label>CSV file<input aria-label="Distribution CSV file" type="file" accept=".csv,text/csv,text/plain" onChange={event => {
          const file = event.target.files?.[0]
          if (file) void file.text().then(text => review(text, file.name))
          event.target.value = ''
        }} /></label>
        <label>Paste CSV or rectangular TSV<textarea aria-label="Distribution pasted data" rows={7} value={paste} onChange={event => setPaste(event.target.value)} onPaste={() => setError('')} /></label>
        <button type="button" disabled={!paste.trim()} onClick={() => review(paste, 'Pasted spreadsheet data')}>Review Pasted Data</button>
      </div>
      {error && <div className="error-panel" role="alert">{error}</div>}
      {table && plan && <>
        <div className="bulk-summary"><strong>{table.sourceName}</strong><span>{table.rows.length} rows</span><span>{table.headers.length} columns</span>{parseDurationMs !== undefined && <span>Parsed in {parseDurationMs.toFixed(1)} ms</span>}</div>
        <label>Normalized radial column<select aria-label="Radial column" value={plan.radialColumn} onChange={event => setPlan({ ...plan, radialColumn: event.target.value })}><option value="">Select column…</option>{table.headers.map(header => <option key={header}>{header}</option>)}</select></label>
        <table className="mapping-table"><thead><tr><th>Target</th><th>Source column</th><th>Units</th><th>Interpolation</th><th>Existing</th></tr></thead><tbody>{CURVES.map(curve => {
          const selection = plan.selections[curve.name]
          return <tr key={curve.name}><th>{curve.title}</th><td><select aria-label={`${curve.title} source column`} value={selection?.column ?? ''} onChange={event => updateSelection(curve, event.target.value)}><option value="">Unchanged</option>{table.headers.filter(header => header !== plan.radialColumn && header !== 'row').map(header => <option key={header}>{header}</option>)}</select></td><td>{selection ? <select aria-label={`${curve.title} import units`} value={selection.unit} onChange={event => setPlan({ ...plan, selections: { ...plan.selections, [curve.name]: { ...selection, unit: event.target.value as ImportUnit } } })}>{unitsForCurve(curve.name).map(unit => <option key={unit}>{unit}</option>)}</select> : '—'}</td><td>{selection ? <select aria-label={`${curve.title} import interpolation`} value={selection.interpolation} onChange={event => setPlan({ ...plan, selections: { ...plan.selections, [curve.name]: { ...selection, interpolation: event.target.value as 'linear' | 'pchip' } } })}><option value="linear">Linear</option><option value="pchip">PCHIP</option></select> : '—'}</td><td>{snapshot[curve.key].points.length} points</td></tr>
        })}</tbody></table>
        <p className="hint"><strong>Informational column:</strong> {table.headers.includes('row') ? 'row is not mapped to BladeSpec.' : 'none'}</p>
        {unknown.length > 0 && <div className="column-warnings"><strong>Unmapped columns require explicit exclusion</strong>{unknown.map(column => <label key={column} className="inline"><input type="checkbox" checked={plan.excludedColumns.includes(column)} onChange={event => setPlan({ ...plan, excludedColumns: event.target.checked ? [...plan.excludedColumns, column] : plan.excludedColumns.filter(value => value !== column) })} /> Exclude {column}</label>)}</div>}
        <button type="button" onClick={() => {
          try { setTable(sortTableByRadius(table, plan.radialColumn)); setError('') }
          catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)) }
        }}>Sort rows by r/R</button>
        {candidate.error && <div className="error-panel" role="alert">{candidate.error}</div>}
        {candidate.value && <div className="candidate-review">
          <h3>Review replacement</h3>
          <p>Diameter snapshot: {snapshot.diameter_mm} mm · radial domain {candidate.value.radialDomain[0]} to {candidate.value.radialDomain[1]} · airfoil stations remain {snapshot.airfoil_sections.length} · Thickness {candidate.value.summaries.some(summary => summary.curve === 'thickness') ? 'selected' : 'unchanged'}.</p>
          <ul>{candidate.value.summaries.map(summary => <li key={summary.curve}><strong>{summary.title}</strong>: {summary.column} ({summary.unit}), {summary.interpolation.toUpperCase()}, {summary.oldPointCount} → {summary.newPointCount} points</li>)}</ul>
          <div className="candidate-preview"><table><thead><tr>{table.headers.map(header => <th key={header}>{header}</th>)}</tr></thead><tbody>{table.rows.slice(0, 10).map(row => <tr key={row.sourceRow}>{table.headers.map(header => <td key={header}>{row.cells[header]}</td>)}</tr>)}</tbody></table>{table.rows.length > 10 && <p>Previewing 10 of {table.rows.length} rows; all rows will be validated.</p>}</div>
          <div className="dialog-actions"><button onClick={cancel}>Cancel</button><button className="primary" disabled={applying} onClick={() => void apply()}>{applying ? 'Validating candidate…' : 'Apply Once'}</button></div>
        </div>}
      </>}
    </section>
  </div>
}
