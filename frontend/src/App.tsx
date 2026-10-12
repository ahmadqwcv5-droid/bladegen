import { useEffect, useMemo, useRef, useState } from 'react'
import {
  build,
  getArtifacts,
  getDesignPreview,
  getExample,
  getJob,
  validate as validateBackend,
} from './api/client'
import { AirfoilComparison } from './components/AirfoilComparison'
import { AirfoilInspector } from './components/AirfoilInspector'
import { AirfoilSelector } from './components/AirfoilSelector'
import { BladeViewer } from './components/BladeViewer'
import { makeStationGuide, type StationGuide } from './components/stationGuides'
import { BuildProgress } from './components/BuildProgress'
import { DistributionChart } from './components/DistributionChart'
import { DistributionTable } from './components/DistributionTable'
import { NumericInput } from './components/NumericInput'
import { applyAirfoilProfile } from './editor/airfoilSelection'
import {
  addAirfoilStation,
  canonicalJson,
  clearThicknessOverride,
  changeRootRadius,
  coordinateNacaThickness,
  effectiveThickness,
  hasThicknessOverride,
  parseBladeSpec,
  removeAirfoilStation,
  setThicknessOverride,
  validateEditorSpec,
} from './editor/bladespecEditor'
import type {
  AirfoilProfile,
  AirfoilSection,
  Artifact,
  BladeSpec,
  DesignPreview,
  Distribution,
  Job,
} from './types/bladespec'
import './styles.css'
import './sprint02.css'
import './sprint02_1.css'
import './patch02_1_1.css'
import './sprint03a.css'
import './sprint03b.css'

const curves: [keyof BladeSpec, string, string, keyof DesignPreview['distributions']][] = [
  ['chord_distribution', 'Chord', 'chord_over_R', 'chord'],
  ['twist_distribution', 'Twist', 'twist_deg', 'twist'],
  ['rake_distribution', 'Rake', 'rake_over_R', 'rake'],
  ['skew_distribution', 'Skew', 'skew_over_R', 'skew'],
  ['thickness_distribution', 'Thickness', 'thickness_ratio', 'thickness'],
]

type StationResult = {
  requested_r_over_R: number
  sampled_r_over_R: number
  station_roles: string[]
  chord_absolute_error_mm: number
  twist_absolute_error_deg: number
  reference_axis_position_error_mm: number
  te_absolute_error_mm: number
  contour_rms_mm: number
  contour_p95_mm: number
  contour_max_mm: number
}

type ValidationResult = {
  solidification: {
    solid_after_reimport: {
      solids: number
      closed_shell: boolean
      brepcheck_valid: boolean
      free_edges: number
      volume_mm3: number
      volume_method: string
    }
    roundtrip: { one_solid: boolean; volume_delta_mm3: number }
  }
  geometry_validation?: {
    passed: boolean
    max_chord_error_mm: number
    max_twist_error_deg: number
    max_reference_axis_error_mm: number
    max_te_error_mm: number
    control_contour_rms_max_mm: number
    control_contour_p95_max_mm: number
    control_contour_max_mm: number
    root_measurement: { requested_r_over_R: number; measured_r_over_R: number }
    tip_measurement: { requested_r_over_R: number; measured_r_over_R: number }
    stations: StationResult[]
  }
}

type DisplayedResult = {
  job_id: string
  submitted_bladespec_snapshot: string
  artifacts: Artifact[]
  validation_data?: ValidationResult
  completed_at: string
}

const newIds = (count: number) => Array.from({ length: count }, () => crypto.randomUUID())
const stationLabel = (section: AirfoilSection) => section.airfoil.type === 'naca4'
  ? `NACA ${section.airfoil.code}`
  : 'Coordinate profile'

export default function App() {
  const [spec, setSpec] = useState<BladeSpec>()
  const [baseline, setBaseline] = useState<BladeSpec>()
  const [rowIds, setRowIds] = useState<string[]>([])
  const [profileNames, setProfileNames] = useState<string[]>([])
  const [epoch, setEpoch] = useState(0)
  const [message, setMessage] = useState('Loading example…')
  const [errors, setErrors] = useState<string[]>([])
  const [activeJob, setActiveJob] = useState<Job>()
  const [displayedResult, setDisplayedResult] = useState<DisplayedResult>()
  const [submitting, setSubmitting] = useState(false)
  const [cadPreviewError, setCadPreviewError] = useState('')
  const [designPreview, setDesignPreview] = useState<DesignPreview>()
  const [designPreviewSnapshot, setDesignPreviewSnapshot] = useState('')
  const [designPreviewLoading, setDesignPreviewLoading] = useState(false)
  const [designPreviewError, setDesignPreviewError] = useState('')
  const [selectedStationId, setSelectedStationId] = useState('')
  const [inspectionMode, setInspectionMode] = useState<'single' | 'compare'>('single')
  const [comparisonAId, setComparisonAId] = useState('')
  const [comparisonBId, setComparisonBId] = useState('')
  const [selectorStation, setSelectorStation] = useState<number>()
  const [activeDistribution, setActiveDistribution] = useState<keyof DesignPreview['distributions']>('chord')
  const activeJobId = useRef<string | undefined>(undefined)
  const submissionPending = useRef(false)
  const submissionSnapshots = useRef(new Map<string, string>())
  const previewRevision = useRef(0)
  const fileInput = useRef<HTMLInputElement>(null)
  const selectedStation = Math.max(rowIds.indexOf(selectedStationId), 0)

  const load = (next: BladeSpec, remember = false) => {
    const ids = newIds(next.airfoil_sections.length)
    setSpec(structuredClone(next))
    setRowIds(ids)
    setProfileNames(next.airfoil_sections.map(stationLabel))
    setSelectedStationId(ids[0] ?? '')
    setComparisonAId(ids[0] ?? '')
    setComparisonBId(ids[1] ?? ids[0] ?? '')
    setInspectionMode('single')
    setSelectorStation(undefined)
    setEpoch(value => value + 1)
    setErrors([])
    setMessage('BladeSpec loaded')
    if (remember) setBaseline(structuredClone(next))
  }

  useEffect(() => {
    getExample().then(value => load(value, true)).catch(error => setMessage(String(error)))
  }, [])

  useEffect(() => {
    if (!spec) return
    const requestNumber = ++previewRevision.current
    const requestedSnapshot = canonicalJson(spec)
    const controller = new AbortController()
    setDesignPreviewLoading(true)
    setDesignPreviewError('')
    const timer = window.setTimeout(() => {
      getDesignPreview(spec, controller.signal)
        .then(value => {
          if (previewRevision.current !== requestNumber) return
          setDesignPreview(value)
          setDesignPreviewSnapshot(requestedSnapshot)
          setDesignPreviewError('')
        })
        .catch(error => {
          if (controller.signal.aborted || previewRevision.current !== requestNumber) return
          setDesignPreviewSnapshot('')
          setDesignPreviewError(error instanceof Error ? error.message : String(error))
        })
        .finally(() => {
          if (previewRevision.current === requestNumber) setDesignPreviewLoading(false)
        })
    }, 250)
    return () => { clearTimeout(timer); controller.abort() }
  }, [spec])

  useEffect(() => {
    if (!activeJob || !['queued', 'running'].includes(activeJob.status)) return
    const id = activeJob.job_id
    const timer = window.setTimeout(() => {
      getJob(id)
        .then(next => { if (activeJobId.current === id) setActiveJob(next) })
        .catch(error => { if (activeJobId.current === id) setMessage(`Build status failure: ${String(error)}`) })
    }, 500)
    return () => clearTimeout(timer)
  }, [activeJob])

  useEffect(() => {
    if (activeJob?.status !== 'succeeded' || activeJobId.current !== activeJob.job_id) return
    const id = activeJob.job_id
    const snapshot = submissionSnapshots.current.get(id)
    if (!snapshot) return
    getArtifacts(id)
      .then(async items => {
        if (activeJobId.current !== id) return
        const validationArtifact = items.find(item => item.name === 'validation.json')
        const validation = validationArtifact
          ? await fetch(validationArtifact.download_url).then(response => response.json()) as ValidationResult
          : undefined
        if (activeJobId.current !== id) return
        setDisplayedResult({
          job_id: id,
          submitted_bladespec_snapshot: snapshot,
          artifacts: items,
          validation_data: validation,
          completed_at: new Date().toISOString(),
        })
        setCadPreviewError('')
        setMessage('Build, STEP topology, and independent geometry validation passed')
      })
      .catch(error => { if (activeJobId.current === id) setMessage(`Artifact loading failure: ${String(error)}`) })
  }, [activeJob])

  const revision = useMemo(() => spec ? canonicalJson(spec) : '', [spec])
  const stale = Boolean(displayedResult && displayedResult.submitted_bladespec_snapshot !== revision)
  const busy = submitting || activeJob?.status === 'queued' || activeJob?.status === 'running'
  const designPreviewCurrent = Boolean(designPreview && designPreviewSnapshot === revision && !designPreviewLoading && !designPreviewError)
  const currentDesignPreview = designPreviewCurrent ? designPreview : undefined
  const stationGuides = useMemo<StationGuide[]>(() => {
    if (!spec || !currentDesignPreview) return []
    const sourceIds = inspectionMode === 'compare'
      ? [comparisonAId, comparisonBId]
      : [selectedStationId]
    return sourceIds
      .filter((id, index, ids) => Boolean(id) && ids.indexOf(id) === index)
      .flatMap(id => {
        const index = rowIds.indexOf(id)
        const station = currentDesignPreview.stations[index]
        if (index < 0 || !station) return []
        const role: StationGuide['role'] = inspectionMode === 'single'
          ? 'selected'
          : id === comparisonBId ? 'B' : 'A'
        return [makeStationGuide(id, index, spec.diameter_mm, station.r_over_R, role)]
      })
  }, [
    comparisonAId,
    comparisonBId,
    currentDesignPreview,
    inspectionMode,
    rowIds,
    selectedStationId,
    spec?.diameter_mm,
  ])

  if (!spec) return <main><h1>BladeGen</h1><p>{message}</p></main>

  const update = (next: BladeSpec) => {
    setSpec(next)
    setErrors(validateEditorSpec(next))
  }
  const field = <K extends keyof BladeSpec>(key: K, value: BladeSpec[K]) => update({ ...spec, [key]: value })
  const updateSection = (index: number, change: Partial<AirfoilSection>) => update({
    ...spec,
    airfoil_sections: spec.airfoil_sections.map((section, current) => current === index ? { ...section, ...change } : section),
  })
  const changeStationRadius = (index: number, radius: number) => {
    if (index === 0 || index === spec.airfoil_sections.length - 1) throw new Error('Root and tip radii are controlled by the global domain')
    const before = spec.airfoil_sections[index - 1].r_over_R
    const after = spec.airfoil_sections[index + 1].r_over_R
    if (radius <= before || radius >= after) throw new Error(`Radius must be between ${before} and ${after}`)
    let next = {
      ...spec,
      airfoil_sections: spec.airfoil_sections.map((section, current) => current === index ? { ...section, r_over_R: radius } : section),
    }
    const section = next.airfoil_sections[index]
    if (section.airfoil.type === 'naca4' && !hasThicknessOverride(section)) next = coordinateNacaThickness(next, index, section.airfoil.code)
    update(next)
  }
  const addStation = () => {
    try {
      let gap = -1
      let radius = 0
      for (let index = 0; index < spec.airfoil_sections.length - 1; index += 1) {
        const candidate = spec.airfoil_sections[index + 1].r_over_R - spec.airfoil_sections[index].r_over_R
        if (candidate > gap) { gap = candidate; radius = (spec.airfoil_sections[index + 1].r_over_R + spec.airfoil_sections[index].r_over_R) / 2 }
      }
      const next = addAirfoilStation(spec, radius)
      const insertion = next.airfoil_sections.findIndex(section => section.r_over_R === radius)
      setRowIds(ids => [...ids.slice(0, insertion), crypto.randomUUID(), ...ids.slice(insertion)])
      setProfileNames(names => [...names.slice(0, insertion), 'NACA 0012', ...names.slice(insertion)])
      update(next)
      setMessage(`Inserted airfoil station at r/R=${radius}`)
    } catch (error) { setErrors([error instanceof Error ? error.message : String(error)]) }
  }
  const removeStation = (index: number) => {
    try {
      const removedId = rowIds[index]
      const nextIds = rowIds.filter((_, current) => current !== index)
      update(removeAirfoilStation(spec, index))
      setRowIds(nextIds)
      setProfileNames(names => names.filter((_, current) => current !== index))
      const fallbackId = nextIds[Math.min(index, nextIds.length - 1)] ?? ''
      const nextSelectedId = selectedStationId === removedId ? fallbackId : selectedStationId
      const nextAId = comparisonAId === removedId ? fallbackId : comparisonAId
      const retainedBId = comparisonBId === removedId ? '' : comparisonBId
      const nextBId = retainedBId && retainedBId !== nextAId ? retainedBId : nextIds.find(id => id !== nextAId) ?? nextAId
      setSelectedStationId(nextSelectedId)
      setComparisonAId(nextAId)
      setComparisonBId(nextBId)
    } catch (error) { setErrors([error instanceof Error ? error.message : String(error)]) }
  }
  const changeNaca = (index: number, code: string) => {
    update(coordinateNacaThickness(spec, index, code))
    setProfileNames(names => names.map((name, current) => current === index ? `NACA ${code}` : name))
  }
  const toggleOverride = (index: number, enabled: boolean) => {
    const section = spec.airfoil_sections[index]
    update(enabled
      ? setThicknessOverride(spec, index, effectiveThickness(spec, section))
      : clearThicknessOverride(spec, index))
  }
  const applyProfile = (index: number, profile: AirfoilProfile) => {
    try {
      update(applyAirfoilProfile(spec, index, profile))
      setProfileNames(names => names.map((name, current) => current === index ? profile.display_name : name))
      setSelectedStationId(rowIds[index])
      setInspectionMode('single')
      setSelectorStation(undefined)
      setMessage(`${profile.display_name} applied to station ${index + 1}; design preview updating`)
    } catch (error) { setErrors([error instanceof Error ? error.message : String(error)]) }
  }
  const submit = async () => {
    if (submissionPending.current || busy) return
    submissionPending.current = true
    setSubmitting(true)
    const local = validateEditorSpec(spec)
    setErrors(local)
    if (local.length) {
      setMessage('Input validation failed — correct errors before generation')
      submissionPending.current = false
      setSubmitting(false)
      return
    }
    setMessage('Validating BladeSpec input…')
    try {
      await validateBackend(spec)
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      setErrors([`Backend BladeSpec validation: ${detail}`])
      setMessage(`Input validation error: ${detail}`)
      submissionPending.current = false
      setSubmitting(false)
      return
    }
    try {
      const snapshot = canonicalJson(structuredClone(spec))
      const next = await build(spec)
      submissionSnapshots.current.set(next.job_id, snapshot)
      activeJobId.current = next.job_id
      setActiveJob(next)
      setMessage(`Build ${next.job_id.slice(0, 8)} accepted by the CAD worker`)
    } catch (error) {
      setMessage(`Build submission failure: ${error instanceof Error ? error.message : String(error)}`)
    } finally {
      submissionPending.current = false
      setSubmitting(false)
    }
  }
  const check = async () => {
    const local = validateEditorSpec(spec)
    setErrors(local)
    if (local.length) { setMessage('Input validation failed'); return }
    try {
      await validateBackend(spec)
      setMessage('BladeSpec input validation passed; no CAD build was performed')
    } catch (error) { setMessage(`Input validation error: ${error instanceof Error ? error.message : String(error)}`) }
  }
  const exportJson = () => {
    const blob = new Blob([`${JSON.stringify(spec, null, 2)}\n`], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${spec.name || 'blade'}.json`
    anchor.click()
    URL.revokeObjectURL(url)
  }
  const importJson = async (file?: File) => {
    if (!file) return
    try {
      const candidate = parseBladeSpec(await file.text())
      await validateBackend(candidate)
      load(candidate)
      setMessage(`Opened and validated ${file.name}`)
    } catch (error) {
      setErrors([`Imported BladeSpec validation error: ${error instanceof Error ? error.message : String(error)}`])
      setMessage('Import rejected — the current project was preserved')
    }
  }
  const reset = () => { if (baseline && window.confirm('Discard current edits and reload the example?')) load(baseline) }
  const createNew = () => { if (window.confirm('Start a new blade from neutral defaults?')) load({ ...structuredClone(baseline ?? spec), name: 'untitled_blade' }) }

  const artifacts = displayedResult?.artifacts ?? []
  const preview = artifacts.find(artifact => artifact.name === 'blade_preview.stl')
  const solid = displayedResult?.validation_data?.solidification.solid_after_reimport
  const geometry = displayedResult?.validation_data?.geometry_validation
  const selectedPreview = currentDesignPreview?.stations[selectedStation]
  const profileWarnings = currentDesignPreview?.stations.filter(station => station.diagnostics?.has_warning) ?? []
  const comparisonChoices = currentDesignPreview?.stations.map((station, index) => ({ id: rowIds[index], index, station })).filter(choice => Boolean(choice.id)) ?? []
  const guidesEnabled = Boolean(preview && !stale && designPreviewCurrent)
  const guideStatus = !preview
    ? 'Generate the blade to place station guides on matching CAD.'
    : stale
      ? 'Station guides hidden: displayed CAD belongs to previous inputs. Regenerate to align current stations.'
      : !designPreviewCurrent
        ? 'Station guides hidden until the canonical preview for this revision is current.'
        : 'Visual radial-location guides derived from the current design; they are not extracted STEP cross-sections.'
  const activeCurve = curves.find(([, , , name]) => name === activeDistribution)!

  return (
    <main>
      <header>
        <div>
          <p className="eyebrow">LEVEL 1 · SPRINT 03B</p>
          <h1>BladeGen</h1>
          <p>Visual design definition → OpenVSP → independently validated OCP solid</p>
        </div>
        <div className="actions">
          <button onClick={createNew}>New</button>
          <button onClick={() => fileInput.current?.click()}>Open JSON</button>
          <input ref={fileInput} hidden type="file" accept="application/json,.json" onChange={event => { void importJson(event.target.files?.[0]); event.target.value = '' }} />
          <button onClick={exportJson}>Export JSON</button>
          <button onClick={() => baseline && load(baseline)}>Load Example</button>
          <button onClick={reset}>Reset</button>
          <button onClick={check}>Validate</button>
          <button className="primary" disabled={busy} onClick={submit}>{busy ? 'Generating…' : 'Generate Blade'}</button>
        </div>
      </header>

      <div className={`status ${stale ? 'stale' : ''}`}>
        <strong>{activeJob ? `Active job ${activeJob.job_id.slice(0, 8)} · ${activeJob.status}` : 'Editor'}</strong>
        {' — '}{message}{stale && <b> · Inputs changed — regenerate to update CAD.</b>}
      </div>
      <BuildProgress job={activeJob} />
      {errors.length > 0 && <div className="error-panel"><strong>Input validation</strong><ul>{errors.map(error => <li key={error}>{error}</li>)}</ul></div>}
      {cadPreviewError && <div className="error-panel"><strong>Preview loading failure:</strong> {cadPreviewError}</div>}

      <div className="layout">
        <div className="editor">
          <section>
            <h2>Global settings</h2>
            <div className="grid">
              <label>Name<input value={spec.name} onChange={event => field('name', event.target.value)} /></label>
              <label>Diameter (mm)<NumericInput label="Diameter" value={spec.diameter_mm} onCommit={value => field('diameter_mm', value)} /></label>
              <label>Root r/R<NumericInput label="Root radius" step=".01" value={spec.root_radius_ratio} onCommit={value => update(changeRootRadius(spec, value))} /></label>
              <label>Reference x/c<NumericInput label="Reference axis" step=".01" value={spec.reference_axis_x_over_c} onCommit={value => field('reference_axis_x_over_c', value)} /></label>
              <label>Rotation<select value={spec.rotation_direction} onChange={event => field('rotation_direction', event.target.value as 'normal' | 'reverse')}><option value="normal">Normal</option><option value="reverse">Reverse</option></select></label>
            </div>
          </section>

          <section>
            <div className="section-title"><h2>Airfoil Stations ({spec.airfoil_sections.length})</h2><button onClick={addStation}>Add Airfoil Station</button></div>
            <p className="selected-station-summary">{inspectionMode === 'single'
              ? <>Inspecting Station {selectedStation + 1} · r/R {spec.airfoil_sections[selectedStation]?.r_over_R.toFixed(4)}</>
              : <>Comparing Station A {rowIds.indexOf(comparisonAId) + 1} with Station B {rowIds.indexOf(comparisonBId) + 1}</>}</p>
            <div className="station-table-scroll"><table>
              <thead><tr><th>r/R</th><th>Profile</th><th>TE mm</th><th>Effective t/c</th><th>Override</th><th>Status</th><th /></tr></thead>
              <tbody>{spec.airfoil_sections.map((section, index) => {
                const stationId = rowIds[index]
                const rowState = inspectionMode === 'single' && selectedStationId === stationId ? 'selected' : inspectionMode === 'compare' && comparisonAId === stationId ? 'compare-a' : inspectionMode === 'compare' && comparisonBId === stationId ? 'compare-b' : ''
                return <tr key={stationId} className={'station-row ' + rowState} data-station-id={stationId}>
                <td><NumericInput label={`Airfoil radius ${index + 1}`} step=".01" value={section.r_over_R} disabled={index === 0 || index === spec.airfoil_sections.length - 1} onCommit={value => changeStationRadius(index, value)} /></td>
                <td className="station-profile">
                  <span className="station-profile-name">{profileNames[index] ?? stationLabel(section)}</span>
                  {section.airfoil.type === 'naca4'
                    ? <input aria-label={`NACA code ${index + 1}`} inputMode="numeric" maxLength={4} value={section.airfoil.code} onChange={event => changeNaca(index, event.target.value)} />
                    : <details><summary>Embedded coordinates</summary><pre>{JSON.stringify(section.airfoil, null, 2)}</pre></details>}
                  <div className="station-profile-actions"><button onClick={() => setSelectorStation(index)}>Choose from Library</button><button onClick={() => { setSelectedStationId(stationId); setInspectionMode('single') }}>Inspect</button><button onClick={() => { setComparisonAId(stationId); setComparisonBId(current => current === stationId ? rowIds.find(id => id !== stationId) ?? stationId : current); setInspectionMode('compare') }}>Compare as A</button></div>
                </td>
                <td><NumericInput label={`TE thickness ${index + 1}`} step=".1" value={section.trailing_edge_thickness_mm} onCommit={value => updateSection(index, { trailing_edge_thickness_mm: value })} /></td>
                <td>{effectiveThickness(spec, section).toFixed(4)}</td>
                <td>
                  {section.airfoil.type === 'naca4' ? <>
                    <label className="inline"><input type="checkbox" checked={hasThicknessOverride(section)} onChange={event => toggleOverride(index, event.target.checked)} /> explicit</label>
                    {hasThicknessOverride(section) && <NumericInput label={`Thickness override ${index + 1}`} step=".01" value={section.thickness_override_ratio} onCommit={value => update(setThicknessOverride(spec, index, value))} />}
                  </> : <span className="hint">natural coordinate t/c</span>}
                </td>
                <td className="station-state">{inspectionMode === 'single' && selectedStationId === stationId ? 'Selected' : inspectionMode === 'compare' && comparisonAId === stationId ? 'Station A' : inspectionMode === 'compare' && comparisonBId === stationId ? 'Station B' : '—'}</td>
                <td><button disabled={index === 0 || index === spec.airfoil_sections.length - 1} onClick={() => removeStation(index)}>Remove</button></td>
              </tr>})}</tbody>
            </table></div>
            <p className="hint">Library selections embed exact coordinates in BladeSpec. Physical trailing-edge thickness remains an independent millimeter requirement.</p>
            <div className="inspection-tabs" role="group" aria-label="Station inspection mode">
              <button aria-pressed={inspectionMode === 'single'} onClick={() => setInspectionMode('single')}>Single Station</button>
              <button aria-pressed={inspectionMode === 'compare'} disabled={spec.airfoil_sections.length < 2} onClick={() => setInspectionMode('compare')}>Compare Stations</button>
            </div>
            <p className="design-preview-state">{designPreviewLoading ? 'Updating canonical design preview for this design revision…' : designPreviewError ? 'Preview unavailable for current draft: ' + designPreviewError : designPreviewCurrent ? 'Canonical design preview is current; no OpenVSP process was run.' : 'Canonical preview pending for this design revision.'}</p>
            {!designPreviewCurrent && <p className="preview-pending" role="status">Station inspection is hidden until the canonical backend preview matches the current BladeSpec revision.</p>}
            {designPreviewCurrent && <>
              {profileWarnings.length > 0 && <div className="profile-quality-warning" role="status" aria-label="Design coordinate diagnostic summary"><strong>Coordinate profile warnings</strong><ul>{profileWarnings.map(station => <li key={station.r_over_R}>r/R {station.r_over_R.toFixed(4)}: {station.diagnostics?.advisory}</li>)}</ul></div>}
              {inspectionMode === 'compare'
                ? <AirfoilComparison choices={comparisonChoices} stationAId={comparisonAId} stationBId={comparisonBId} onStationA={setComparisonAId} onStationB={setComparisonBId} onClose={() => setInspectionMode('single')} />
                : selectedPreview && <AirfoilInspector station={selectedPreview} />}
            </>}
          </section>

          <section>
            <h2>Independent Spanwise Distributions</h2>
            <div className="distribution-visual">
              <div className="distribution-tabs" role="group" aria-label="Distribution chart selection">{curves.map(([, title, , name]) => <button key={name} aria-pressed={activeDistribution === name} onClick={() => setActiveDistribution(name)}>{title}</button>)}</div>
              <DistributionChart title={`${activeCurve[1]} Distribution`} data={currentDesignPreview?.distributions[activeDistribution]} />
            </div>
            <div className="curves">{curves.map(([key, title, valueKey]) => <DistributionTable
              key={`${String(key)}-${epoch}`}
              title={title}
              valueKey={valueKey}
              value={spec[key] as Distribution}
              onChange={value => field(key, value as BladeSpec[typeof key])}
              onError={error => setErrors(error ? [error] : [])}
            />)}</div>
          </section>
        </div>

        <aside>
          <h2>Solid preview</h2>
          {displayedResult && <p className={stale ? 'preview-label stale' : 'preview-label'}>Preview from completed job {displayedResult.job_id.slice(0, 8)}{stale ? ' · previous inputs' : ''}</p>}
          <BladeViewer url={preview?.download_url} onError={setCadPreviewError} guides={stationGuides} guidesEnabled={guidesEnabled} guideStatus={guideStatus} />
          {solid && <><h2>STEP topology</h2><dl><dt>Solid / free edges</dt><dd>{solid.solids} / {solid.free_edges}</dd><dt>Closed / BRep valid</dt><dd>{String(solid.closed_shell)} / {String(solid.brepcheck_valid)}</dd><dt>Adaptive volume</dt><dd>{solid.volume_mm3.toFixed(6)} mm³</dd></dl></>}
          {geometry && <><h2>Independent geometry</h2><dl><dt>Overall</dt><dd>{geometry.passed ? 'PASS' : 'FAIL'}</dd><dt>Chord / twist max</dt><dd>{geometry.max_chord_error_mm.toFixed(5)} mm / {geometry.max_twist_error_deg.toFixed(5)}°</dd><dt>Axis / TE max</dt><dd>{geometry.max_reference_axis_error_mm.toFixed(5)} / {geometry.max_te_error_mm.toFixed(5)} mm</dd><dt>Contour RMS / P95 / max</dt><dd>{geometry.control_contour_rms_max_mm.toFixed(5)} / {geometry.control_contour_p95_max_mm.toFixed(5)} / {geometry.control_contour_max_mm.toFixed(5)} mm</dd><dt>Root requested / sampled</dt><dd>{geometry.root_measurement.requested_r_over_R} / {geometry.root_measurement.measured_r_over_R}</dd><dt>Tip requested / sampled</dt><dd>{geometry.tip_measurement.requested_r_over_R} / {geometry.tip_measurement.measured_r_over_R}</dd></dl><details><summary>Per-station measurements ({geometry.stations.length})</summary><table><thead><tr><th>Requested</th><th>Sampled</th><th>Roles</th><th>Chord</th><th>Twist</th><th>TE</th></tr></thead><tbody>{geometry.stations.map(row => <tr key={row.requested_r_over_R}><td>{row.requested_r_over_R}</td><td>{row.sampled_r_over_R}</td><td>{row.station_roles.join(', ')}</td><td>{row.chord_absolute_error_mm.toFixed(4)}</td><td>{row.twist_absolute_error_deg.toFixed(4)}</td><td>{row.te_absolute_error_mm.toFixed(4)}</td></tr>)}</tbody></table></details></>}
          <h2>Artifacts</h2>
          {displayedResult && <p className="hint">Artifacts from completed job {displayedResult.job_id.slice(0, 8)}</p>}
          {artifacts.length ? <ul>{artifacts.map(artifact => <li key={artifact.name}><a href={artifact.download_url}>{artifact.name}</a> <small>{Math.ceil(artifact.size_bytes / 1024)} KB</small></li>)}</ul> : <p>No completed build artifacts yet.</p>}
        </aside>
      </div>
      {selectorStation !== undefined && <AirfoilSelector
        stationIndex={selectorStation}
        radius={spec.airfoil_sections[selectorStation].r_over_R}
        onApply={profile => applyProfile(selectorStation, profile)}
        onCancel={() => setSelectorStation(undefined)}
      />}
    </main>
  )
}
