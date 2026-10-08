import type { Distribution } from '../types/bladespec'

export function DistributionTable({title, valueKey, value, onChange}: {
  title: string; valueKey: string; value: Distribution; onChange: (value: Distribution) => void
}) {
  const change = (index: number, key: string, raw: string) => {
    const points = value.points.map((point, i) => i === index ? {...point, [key]: Number(raw)} : point)
    onChange({...value, points})
  }
  return <section className="curve"><h3>{title}</h3>
    <label>Interpolation <select value={value.interpolation} onChange={e => onChange({...value, interpolation: e.target.value as 'linear'|'pchip'})}>
      <option value="linear">Linear</option><option value="pchip">PCHIP</option>
    </select></label>
    <table><thead><tr><th>r/R</th><th>{valueKey}</th></tr></thead><tbody>
      {value.points.map((point, i) => <tr key={i}><td><input type="number" step="0.01" value={point.r_over_R} onChange={e => change(i, 'r_over_R', e.target.value)}/></td>
      <td><input type="number" step="0.001" value={point[valueKey]} onChange={e => change(i, valueKey, e.target.value)}/></td></tr>)}
    </tbody></table></section>
}
