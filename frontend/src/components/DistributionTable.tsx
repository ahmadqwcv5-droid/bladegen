import { useEffect, useRef, useState } from 'react'
import { addControlPoint, removeControlPoint, updateControlPoint } from '../editor/bladespecEditor'
import type { Distribution } from '../types/bladespec'
import { NumericInput } from './NumericInput'

let nextId=0
const id=()=>`curve-${++nextId}`

export function DistributionTable({title,valueKey,value,onChange,onError}:{title:string;valueKey:string;value:Distribution;onChange:(value:Distribution)=>void;onError:(message:string)=>void}) {
  const [ids,setIds]=useState(()=>value.points.map(id)); const previousLength=useRef(value.points.length)
  useEffect(()=>{ if(value.points.length!==previousLength.current){setIds(value.points.map((_,i)=>ids[i]??id()));previousLength.current=value.points.length} },[value.points.length])
  const update=(index:number,change:Record<string,number>)=>{try{onChange(updateControlPoint(value,index,change));onError('')}catch(e){onError(e instanceof Error?e.message:String(e))}}
  const add=()=>{try{let left=0,gap=-1;for(let i=0;i<value.points.length-1;i++){const candidate=value.points[i+1].r_over_R-value.points[i].r_over_R;if(candidate>gap){gap=candidate;left=i}}const radius=(value.points[left].r_over_R+value.points[left+1].r_over_R)/2;const next=addControlPoint(value,valueKey,radius);const insertion=next.points.findIndex(p=>p.r_over_R===radius);setIds(current=>[...current.slice(0,insertion),id(),...current.slice(insertion)]);previousLength.current=next.points.length;onChange(next);onError('')}catch(e){onError(e instanceof Error?e.message:String(e))}}
  const remove=(index:number)=>{try{const next=removeControlPoint(value,index);setIds(current=>current.filter((_,i)=>i!==index));previousLength.current=next.points.length;onChange(next);onError('')}catch(e){onError(e instanceof Error?e.message:String(e))}}
  return <section className="curve"><div className="section-title"><h3>{title} ({value.points.length})</h3><button type="button" onClick={add}>Add Control Point</button></div>
    <label>Interpolation <select aria-label={`${title} interpolation`} value={value.interpolation} onChange={e=>onChange({...value,interpolation:e.target.value as 'linear'|'pchip'})}><option value="linear">Linear</option><option value="pchip">PCHIP</option></select></label>
    <table><thead><tr><th>r/R</th><th>{valueKey}</th><th/></tr></thead><tbody>{value.points.map((point,i)=><tr key={ids[i]}><td><NumericInput label={`${title} radius ${i+1}`} step="0.01" value={point.r_over_R} disabled={i===0||i===value.points.length-1} onCommit={r=>update(i,{r_over_R:r})}/></td><td><NumericInput label={`${title} value ${i+1}`} step="0.001" value={point[valueKey]} onCommit={v=>update(i,{[valueKey]:v})}/></td><td><button type="button" disabled={i===0||i===value.points.length-1} onClick={()=>remove(i)}>Remove</button></td></tr>)}</tbody></table>
  </section>
}
