import { useEffect, useRef, useState } from 'react'
import { addControlPoint, removeControlPoint, updateControlPoint } from '../editor/bladespecEditor'
import type { CurveDefinition } from '../editor/curveEditing'
import { formatEngineeringValue, storedToDisplay } from '../editor/curveEditing'
import type { Distribution } from '../types/bladespec'
import { NumericInput } from './NumericInput'

let nextId = 0
const id = () => `curve-${++nextId}`

type Props = {
  definition: CurveDefinition
  diameterMm: number
  value: Distribution
  disabled?: boolean
  lockReason: (radius: number) => string | undefined
  onPointValue: (index: number, displayedValue: number) => Promise<boolean>
  onChange: (value: Distribution, label: string) => Promise<boolean>
  onError: (message: string) => void
}

export function DistributionTable({
  definition, diameterMm, value, disabled = false, lockReason, onPointValue, onChange, onError,
}: Props) {
  const [ids, setIds] = useState(() => value.points.map(id))
  const previousLength = useRef(value.points.length)
  useEffect(() => {
    if (value.points.length !== previousLength.current) {
      setIds(current => value.points.map((_, index) => current[index] ?? id()))
      previousLength.current = value.points.length
    }
  }, [value.points.length])
  const updateRadius = (index: number, radius: number) => {
    try { return onChange(updateControlPoint(value, index, { r_over_R: radius }), `${definition.title} control radius`) }
    catch (error) { onError(error instanceof Error ? error.message : String(error)); return Promise.resolve(false) }
  }
  const add = async () => {
    try {
      let left = 0; let gap = -1
      for (let index = 0; index < value.points.length - 1; index += 1) {
        const candidate = value.points[index + 1].r_over_R - value.points[index].r_over_R
        if (candidate > gap) { gap = candidate; left = index }
      }
      const radius = (value.points[left].r_over_R + value.points[left + 1].r_over_R) / 2
      const next = addControlPoint(value, definition.valueKey, radius)
      const insertion = next.points.findIndex(point => point.r_over_R === radius)
      if (!await onChange(next, `Add ${definition.title} control point`)) return
      setIds(current => [...current.slice(0, insertion), id(), ...current.slice(insertion)])
      previousLength.current = next.points.length
      onError('')
    } catch (error) { onError(error instanceof Error ? error.message : String(error)) }
  }
  const remove = async (index: number) => {
    try {
      const next = removeControlPoint(value, index)
      if (!await onChange(next, `Remove ${definition.title} control point`)) return
      setIds(current => current.filter((_, currentIndex) => currentIndex !== index))
      previousLength.current = next.points.length
      onError('')
    } catch (error) { onError(error instanceof Error ? error.message : String(error)) }
  }
  return <section className="curve">
    <div className="section-title"><h3>{definition.title} ({value.points.length})</h3><button type="button" disabled={disabled} onClick={add}>Add Control Point</button></div>
    <label>Interpolation <select aria-label={`${definition.title} interpolation`} disabled={disabled} value={value.interpolation} onChange={event => onChange({ ...value, interpolation: event.target.value as 'linear' | 'pchip' }, `${definition.title} interpolation`)}><option value="linear">Linear</option><option value="pchip">PCHIP</option></select></label>
    <div className="distribution-table-scroll"><table className="distribution-table"><thead><tr><th>r/R</th><th>{definition.title} ({definition.unit})</th><th /></tr></thead><tbody>{value.points.map((point, index) => {
      const locked = lockReason(point.r_over_R)
      return <tr key={ids[index] ?? index} className={locked ? 'curve-point-locked' : ''}>
        <td><NumericInput label={`${definition.title} radius ${index + 1}`} step="0.01" value={point.r_over_R} disabled={disabled || index === 0 || index === value.points.length - 1} onCommit={radius => updateRadius(index, radius)} /></td>
        <td><NumericInput label={`${definition.title} value ${index + 1}`} step={String(definition.step)} value={storedToDisplay(definition.name, point[definition.valueKey], diameterMm)} formatValue={displayed => formatEngineeringValue(definition.name, displayed)} disabled={disabled || Boolean(locked)} onCommit={displayed => onPointValue(index, displayed)} />{locked && <small className="curve-lock-reason">{locked}</small>}</td>
        <td><button type="button" disabled={disabled || index === 0 || index === value.points.length - 1} onClick={() => remove(index)}>Remove</button></td>
      </tr>
    })}</tbody></table></div>
  </section>
}
