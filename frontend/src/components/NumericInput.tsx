import { useEffect, useState } from 'react'

export function NumericInput({value,onCommit,label,step='any',disabled=false}:{value:number;onCommit:(value:number)=>void;label:string;step?:string;disabled?:boolean}) {
  const [draft,setDraft]=useState(String(value)); const [error,setError]=useState('')
  useEffect(()=>setDraft(String(value)),[value])
  const commit=()=>{ const parsed=Number(draft); if (draft.trim()===''||!Number.isFinite(parsed)){setError(`${label} must be a finite number`);return} try{onCommit(parsed);setError('')}catch(e){setError(e instanceof Error?e.message:String(e))} }
  return <span className="numeric"><input aria-label={label} type="number" step={step} value={draft} disabled={disabled} onChange={e=>setDraft(e.target.value)} onBlur={commit}/>{error&&<small className="field-error">{error}</small>}</span>
}
