import { useEffect, useState } from 'react'
import { build, getArtifacts, getExample, getJob, validate } from './api/client'
import { BladeViewer } from './components/BladeViewer'
import { DistributionTable } from './components/DistributionTable'
import type { AirfoilSection, Artifact, BladeSpec, Distribution, Job } from './types/bladespec'
import './styles.css'

const curves: [keyof BladeSpec, string, string][] = [
  ['chord_distribution','Chord','chord_over_R'], ['twist_distribution','Twist','twist_deg'],
  ['rake_distribution','Rake','rake_over_R'], ['skew_distribution','Skew','skew_over_R'],
  ['thickness_distribution','Thickness','thickness_ratio'],
]
type ValidationResult = {
  solidification: { solid_after_reimport: { solids:number; closed_shell:boolean; brepcheck_valid:boolean; free_edges:number; volume_mm3:number; volume_method:string }; roundtrip: { one_solid:boolean; volume_delta_mm3:number } }
  geometry_validation?: { passed:boolean; max_chord_error_mm:number; max_twist_error_deg:number; max_te_error_mm:number }
}

export default function App() {
  const [spec, setSpec] = useState<BladeSpec>(); const [message, setMessage] = useState('Loading example…')
  const [job, setJob] = useState<Job>(); const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [validationResult, setValidationResult] = useState<ValidationResult>()
  useEffect(() => { getExample().then(s => {setSpec(s); setMessage('Example ready')}).catch(e => setMessage(String(e))) }, [])
  useEffect(() => {
    if (!job || !['queued','running'].includes(job.status)) return
    const timer = window.setTimeout(() => getJob(job.job_id).then(setJob).catch(e => setMessage(String(e))), 1000)
    return () => clearTimeout(timer)
  }, [job])
  useEffect(() => {
    if (job?.status !== 'succeeded') return
    getArtifacts(job.job_id).then(items => {
      setArtifacts(items)
      const validation = items.find(item => item.name === 'validation.json')
      if (validation) fetch(validation.download_url).then(r => r.json()).then(setValidationResult)
    }).catch(e => setMessage(String(e)))
  }, [job])
  if (!spec) return <main><h1>BladeGen</h1><p>{message}</p></main>
  const field = (key: keyof BladeSpec, value: unknown) => setSpec({...spec, [key]: value})
  const updateSection = (index:number, update:Partial<AirfoilSection>) => field('airfoil_sections', spec.airfoil_sections.map((item,i) => i===index ? {...item,...update} : item))
  const changeNaca = (index:number, code:string) => {
    const section = spec.airfoil_sections[index]
    const airfoil_sections = spec.airfoil_sections.map((item,i) => i===index ? {...item,airfoil:{type:'naca4' as const,code}} : item)
    const thickness_distribution = !/^\d{4}$/.test(code) || section.thickness_override_ratio !== undefined
      ? spec.thickness_distribution
      : {...spec.thickness_distribution, points: spec.thickness_distribution.points.map(point => point.r_over_R === section.r_over_R ? {...point, thickness_ratio:Number(code.slice(2))/100} : point)}
    setSpec({...spec, airfoil_sections, thickness_distribution})
  }
  const setOverride = (index:number, enabled:boolean) => {
    const section = spec.airfoil_sections[index]
    if (!enabled) { const {thickness_override_ratio: _, ...without} = section; field('airfoil_sections',spec.airfoil_sections.map((x,i)=>i===index?without:x)); return }
    const nominal = section.airfoil.type === 'naca4' ? Number(section.airfoil.code.slice(2))/100 : .12
    updateSection(index,{thickness_override_ratio:nominal})
  }
  const submit = async () => { try { setArtifacts([]); setValidationResult(undefined); setMessage('Submitting real CAD build…'); const next = await build(spec); setJob(next); setMessage('Build queued') } catch(e) { setMessage(String(e)) } }
  const check = async () => { try { await validate(spec); setMessage('BladeSpec is valid') } catch(e) { setMessage(String(e)) } }
  const preview = artifacts.find(a => a.name === 'blade_preview.stl')
  const solid = validationResult?.solidification.solid_after_reimport
  return <main><header><div><p className="eyebrow">LEVEL 1 ALPHA</p><h1>BladeGen</h1><p>BladeSpec → OpenVSP → validated OCP solid</p></div><div className="actions"><button onClick={() => getExample().then(setSpec)}>Load example</button><button onClick={check}>Validate inputs</button><button className="primary" onClick={submit}>Generate blade</button></div></header>
    <div className="status"><strong>Status:</strong> {job?.status ?? message}{job?.error && <span className="error"> — {job.error}</span>}</div>
    <div className="layout"><div className="editor"><section><h2>Global settings</h2><div className="grid">
      <label>Name<input value={spec.name} onChange={e=>field('name',e.target.value)}/></label><label>Diameter (mm)<input type="number" value={spec.diameter_mm} onChange={e=>field('diameter_mm',Number(e.target.value))}/></label><label>Root r/R<input type="number" step=".01" value={spec.root_radius_ratio} onChange={e=>field('root_radius_ratio',Number(e.target.value))}/></label><label>Reference x/c<input type="number" step=".01" value={spec.reference_axis_x_over_c} onChange={e=>field('reference_axis_x_over_c',Number(e.target.value))}/></label><label>Rotation<select value={spec.rotation_direction} onChange={e=>field('rotation_direction',e.target.value)}><option value="normal">Normal</option><option value="reverse">Reverse</option></select></label>
    </div></section><section><h2>Airfoil stations</h2><table><thead><tr><th>r/R</th><th>Type</th><th>NACA</th><th>TE mm</th><th>Thickness override</th></tr></thead><tbody>{spec.airfoil_sections.map((s,i)=><tr key={i}><td><input type="number" step=".01" value={s.r_over_R} onChange={e=>updateSection(i,{r_over_R:Number(e.target.value)})}/></td><td><select value={s.airfoil.type} disabled><option value="naca4">NACA 4</option><option value="coordinates">Coordinates (JSON)</option></select></td><td>{s.airfoil.type==='naca4'?<input pattern="[0-9]{4}" value={s.airfoil.code} onChange={e=>changeNaca(i,e.target.value)}/>: 'advanced JSON'}</td><td><input type="number" step=".1" value={s.trailing_edge_thickness_mm} onChange={e=>updateSection(i,{trailing_edge_thickness_mm:Number(e.target.value)})}/></td><td><label className="inline"><input type="checkbox" checked={s.thickness_override_ratio!==undefined} onChange={e=>setOverride(i,e.target.checked)}/> explicit</label>{s.thickness_override_ratio!==undefined&&<input type="number" step=".01" value={s.thickness_override_ratio} onChange={e=>updateSection(i,{thickness_override_ratio:Number(e.target.value)})}/>}</td></tr>)}</tbody></table><p className="hint">Changing a NACA code updates a thickness control at the same radius. Non-coincident grids and coordinate profiles remain supported through the API/advanced JSON input.</p></section>
    <section><h2>Spanwise distributions</h2><div className="curves">{curves.map(([key,title,valueKey])=><DistributionTable key={String(key)} title={title} valueKey={valueKey} value={spec[key] as Distribution} onChange={v=>field(key,v)}/>)}</div></section></div>
    <aside><h2>Solid preview</h2><BladeViewer url={preview?.download_url}/>{solid&&<><h2>Validation summary</h2><dl><dt>Solid / free edges</dt><dd>{solid.solids} / {solid.free_edges}</dd><dt>Closed / BRep valid</dt><dd>{String(solid.closed_shell)} / {String(solid.brepcheck_valid)}</dd><dt>Adaptive volume</dt><dd>{solid.volume_mm3.toFixed(6)} mm³</dd><dt>STEP round-trip</dt><dd>{validationResult!.solidification.roundtrip.one_solid?'PASS':'FAIL'} (Δ {validationResult!.solidification.roundtrip.volume_delta_mm3.toExponential(2)} mm³)</dd><dt>Geometry</dt><dd>{validationResult?.geometry_validation?.passed?'PASS':'Unavailable'}</dd></dl><p className="hint">{solid.volume_method}</p></>}<h2>Artifacts</h2>{artifacts.length ? <ul>{artifacts.map(a=><li key={a.name}><a href={a.download_url}>{a.name}</a> <small>{Math.ceil(a.size_bytes/1024)} KB</small></li>)}</ul>:<p>No completed build artifacts yet.</p>}</aside></div>
  </main>
}
