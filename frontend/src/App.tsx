import { useEffect, useMemo, useRef, useState } from 'react'
import {
  build as buildBlade,
  buildPropeller,
  getArtifacts,
  getDesignPreview,
  getExample,
  getJob,
  getPropellerCapabilities,
  validate as validateBackend,
  validatePropeller,
} from './api/client'
import { AirfoilComparison } from './components/AirfoilComparison'
import { AirfoilInspector } from './components/AirfoilInspector'
import { AirfoilSelector } from './components/AirfoilSelector'
import { AirfoilStationSetupDialog } from './components/AirfoilStationSetupDialog'
import { BladeViewer } from './components/BladeViewer'
import { makeStationGuide, type StationGuide } from './components/stationGuides'
import { BuildProgress } from './components/BuildProgress'
import { DistributionChart } from './components/DistributionChart'
import { DistributionTable } from './components/DistributionTable'
import { DistributionImportDialog } from './components/DistributionImportDialog'
import { NumericInput } from './components/NumericInput'
import { applyAirfoilProfile } from './editor/airfoilSelection'
import {
  CURVES,
  CurveHistory,
  replaceCurvePoint,
  storedToDisplay,
  thicknessControlLock,
} from './editor/curveEditing'
import { nominalHubGuidance } from './editor/assemblyValidation'
import {
  addAirfoilStation,
  canonicalJson,
  clearThicknessOverride,
  changeRootRadius,
  coordinateNacaThickness,
  effectiveThickness,
  hasThicknessOverride,
  removeAirfoilStation,
  setThicknessOverride,
  validateEditorSpec,
} from './editor/bladespecEditor'
import {
  bladeProject,
  DEFAULT_ASSEMBLY,
  parseProjectDocument,
  propellerFromProject,
  type ProjectDocument,
} from './editor/projectDocument'
import type {
  AirfoilProfile,
  AirfoilSection,
  AssemblySpec,
  Artifact,
  BladeSpec,
  DesignPreview,
  Distribution,
  Job,
  PropellerSpec,
  PropellerCapabilities,
  ValidationIssue,
} from './types/bladespec'
import type { ChartInteraction } from './components/DistributionChart'
import './styles.css'
import './sprint02.css'
import './sprint02_1.css'
import './patch02_1_1.css'
import './sprint03a.css'
import './sprint03b.css'
import './sprint03c.css'
import './sprint04a.css'
import './sprint04b.css'

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

const formatMillimetres = (value: number) => Number(value.toFixed(6)).toString()

type ValidationResult = {
  solidification?: {
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
  assembly_validation?: {
    passed: boolean
    requested_blade_count: number
    actual_blade_placement_count: number
    azimuth_angles_deg: number[]
    rotation_axis: number[]
    hub_diameter_mm: number
    hub_length_mm: number
    shaft_bore_diameter_mm: number
    hub_blade_overlap_mm3: number[]
    maximum_copy_volume_delta_mm3: number
    bore: {
      requested_radius_mm: number
      measured_radii_mm: number[]
      maximum_radius_error_mm: number | null
      continuous_through_hole: boolean
      residual_material_volume_mm3: number
    }
    final_after_reimport: {
      solids: number
      shells: number
      closed_shell: boolean
      brepcheck_valid: boolean
      free_edges: number
      volume_mm3: number
      volume_method: string
    }
    roundtrip: { passed: boolean; volume_delta_mm3: number; bbox_max_abs_delta_mm: number }
  }
}

type DisplayedResult = {
  job_id: string
  build_type: 'blade' | 'propeller'
  submitted_snapshot: string
  artifacts: Artifact[]
  validation_data?: ValidationResult
  completed_at: string
}

type DraftValidation = {
  state: 'modified' | 'checking' | 'valid' | 'invalid'
  snapshot?: string
}

type ProjectImportFailure = {
  detail: string
  issues: ValidationIssue[]
}

const newIds = (count: number) => Array.from({ length: count }, () => crypto.randomUUID())
const stationLabel = (section: AirfoilSection) => section.airfoil.type === 'naca4'
  ? `NACA ${section.airfoil.code}`
  : 'Coordinate profile'
const structuredIssues = (error: unknown): ValidationIssue[] => {
  if (typeof error !== 'object' || error === null || !('issues' in error)) return []
  const issues = (error as { issues?: unknown }).issues
  return Array.isArray(issues) ? issues as ValidationIssue[] : []
}

export default function App() {
  const [spec, setSpec] = useState<BladeSpec>()
  const [baseline, setBaseline] = useState<ProjectDocument>()
  const [exampleProject, setExampleProject] = useState<ProjectDocument>()
  const [rowIds, setRowIds] = useState<string[]>([])
  const [profileNames, setProfileNames] = useState<string[]>([])
  const [epoch, setEpoch] = useState(0)
  const [message, setMessage] = useState('Loading example…')
  const [errors, setErrors] = useState<string[]>([])
  const [validationIssues, setValidationIssues] = useState<ValidationIssue[]>([])
  const [projectImportFailure, setProjectImportFailure] = useState<ProjectImportFailure>()
  const [draftValidation, setDraftValidation] = useState<DraftValidation>({ state: 'modified' })
  const [activeJob, setActiveJob] = useState<Job>()
  const [displayedResult, setDisplayedResult] = useState<DisplayedResult>()
  const [submitting, setSubmitting] = useState(false)
  const [cadPreviewError, setCadPreviewError] = useState('')
  const [designMode, setDesignMode] = useState<'blade' | 'propeller'>('blade')
  const [assembly, setAssembly] = useState<AssemblySpec>(structuredClone(DEFAULT_ASSEMBLY))
  const [propellerName, setPropellerName] = useState('untitled_blade_propeller')
  const [propellerCapabilities, setPropellerCapabilities] = useState<PropellerCapabilities>()
  const [designPreview, setDesignPreview] = useState<DesignPreview>()
  const [designPreviewSnapshot, setDesignPreviewSnapshot] = useState('')
  const [designPreviewLoading, setDesignPreviewLoading] = useState(false)
  const [designPreviewError, setDesignPreviewError] = useState('')
  const [selectedStationId, setSelectedStationId] = useState('')
  const [inspectionMode, setInspectionMode] = useState<'single' | 'compare'>('single')
  const [comparisonAId, setComparisonAId] = useState('')
  const [comparisonBId, setComparisonBId] = useState('')
  const [selectorStation, setSelectorStation] = useState<number>()
  const [selectorTargets, setSelectorTargets] = useState<number[]>([])
  const [selectedProfileStationIds, setSelectedProfileStationIds] = useState<string[]>([])
  const [distributionImportSnapshot, setDistributionImportSnapshot] = useState<BladeSpec>()
  const [stationSetupSnapshot, setStationSetupSnapshot] = useState<BladeSpec>()
  const [activeDistribution, setActiveDistribution] = useState<keyof DesignPreview['distributions']>('chord')
  const [curveInteraction, setCurveInteraction] = useState<ChartInteraction>('idle')
  const [curveCancelVersion, setCurveCancelVersion] = useState(0)
  const [, setHistoryVersion] = useState(0)
  const activeJobId = useRef<string | undefined>(undefined)
  const submissionPending = useRef(false)
  const submissionSnapshots = useRef(new Map<string, { snapshot: string; buildType: 'blade' | 'propeller' }>())
  const previewRevision = useRef(0)
  const curveValidationRevision = useRef(0)
  const inputValidationRevision = useRef(0)
  const designSnapshotRef = useRef('')
  const curveHistory = useRef(new CurveHistory(50))
  const specRef = useRef<BladeSpec | undefined>(undefined)
  const fileInput = useRef<HTMLInputElement>(null)
  const selectedStation = Math.max(rowIds.indexOf(selectedStationId), 0)
  specRef.current = spec

  const refreshHistory = () => setHistoryVersion(value => value + 1)
  const cancelCurveWork = () => {
    curveValidationRevision.current += 1
    setCurveCancelVersion(value => value + 1)
    setCurveInteraction('idle')
  }
  const clearCurveHistory = () => {
    curveHistory.current.clear()
    refreshHistory()
  }
  const resetStationUi = (next: BladeSpec) => {
    const ids = newIds(next.airfoil_sections.length)
    setRowIds(ids)
    setProfileNames(next.airfoil_sections.map(stationLabel))
    setSelectedStationId(ids[0] ?? '')
    setComparisonAId(ids[0] ?? '')
    setComparisonBId(ids[1] ?? ids[0] ?? '')
    setSelectedProfileStationIds([])
  }
  const markDraftModified = () => {
    inputValidationRevision.current += 1
    setDraftValidation({ state: 'modified' })
    setValidationIssues([])
    setProjectImportFailure(undefined)
  }

  const loadProject = (project: ProjectDocument, remember = false, loadedMessage = 'Project loaded') => {
    inputValidationRevision.current += 1
    cancelCurveWork()
    clearCurveHistory()
    const next = project.bladeSpec
    const ids = newIds(next.airfoil_sections.length)
    setSpec(structuredClone(next))
    setAssembly(structuredClone(project.assembly))
    setPropellerName(project.propellerName)
    setDesignMode(project.kind)
    setRowIds(ids)
    setProfileNames(next.airfoil_sections.map(stationLabel))
    setSelectedStationId(ids[0] ?? '')
    setComparisonAId(ids[0] ?? '')
    setComparisonBId(ids[1] ?? ids[0] ?? '')
    setInspectionMode('single')
    setSelectorStation(undefined)
    setSelectorTargets([])
    setSelectedProfileStationIds([])
    setDistributionImportSnapshot(undefined)
    setStationSetupSnapshot(undefined)
    setEpoch(value => value + 1)
    setErrors([])
    setValidationIssues([])
    setProjectImportFailure(undefined)
    setDraftValidation({ state: 'modified' })
    setMessage(loadedMessage)
    if (remember) setBaseline(structuredClone(project))
  }

  useEffect(() => {
    getExample()
      .then(value => {
        const project = bladeProject(value)
        setExampleProject(structuredClone(project))
        loadProject(project, true, 'BladeSpec example loaded')
      })
      .catch(error => setMessage(String(error)))
    Promise.resolve(getPropellerCapabilities())
      .then(setPropellerCapabilities)
      .catch(error => setMessage(`Assembly capabilities unavailable: ${String(error)}`))
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

  const undoCurveEdit = () => {
    cancelCurveWork()
    const current = specRef.current
    if (!current) return
    const next = curveHistory.current.undo(current)
    refreshHistory()
    if (!next) return
    if (JSON.stringify(current.airfoil_sections) !== JSON.stringify(next.airfoil_sections)) resetStationUi(next)
    markDraftModified()
    setSpec(next)
    setErrors(validateEditorSpec(next))
    setMessage('Curve edit undone; canonical preview updating')
  }
  const redoCurveEdit = () => {
    cancelCurveWork()
    const current = specRef.current
    if (!current) return
    const next = curveHistory.current.redo(current)
    refreshHistory()
    if (!next) return
    if (JSON.stringify(current.airfoil_sections) !== JSON.stringify(next.airfoil_sections)) resetStationUi(next)
    markDraftModified()
    setSpec(next)
    setErrors(validateEditorSpec(next))
    setMessage('Curve edit redone; canonical preview updating')
  }

  useEffect(() => {
    const keydown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      if (target instanceof Element && target.closest('input, textarea, select, [contenteditable="true"], [role="dialog"]')) return
      const command = event.ctrlKey || event.metaKey
      if (!command) return
      if (curveInteraction !== 'idle') { event.preventDefault(); return }
      if (event.key.toLowerCase() === 'z' && event.shiftKey) { event.preventDefault(); redoCurveEdit() }
      else if (event.key.toLowerCase() === 'z') { event.preventDefault(); undoCurveEdit() }
      else if (event.key.toLowerCase() === 'y') { event.preventDefault(); redoCurveEdit() }
    }
    window.addEventListener('keydown', keydown)
    return () => window.removeEventListener('keydown', keydown)
  })

  useEffect(() => {
    if (activeJob?.status !== 'succeeded' || activeJobId.current !== activeJob.job_id) return
    const id = activeJob.job_id
    const submission = submissionSnapshots.current.get(id)
    if (!submission) return
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
          build_type: submission.buildType,
          submitted_snapshot: submission.snapshot,
          artifacts: items,
          validation_data: validation,
          completed_at: new Date().toISOString(),
        })
        setCadPreviewError('')
        setMessage(submission.buildType === 'propeller'
          ? 'Propeller assembly, STEP topology, bore, and placement validation passed'
          : 'Build, STEP topology, and independent geometry validation passed')
      })
      .catch(error => { if (activeJobId.current === id) setMessage(`Artifact loading failure: ${String(error)}`) })
  }, [activeJob])

  const revision = useMemo(() => spec ? canonicalJson(spec) : '', [spec])
  const propellerSpec = useMemo<PropellerSpec | undefined>(() => spec ? ({
    schema_version: '0.1',
    name: propellerName,
    units: 'mm',
    blade_spec: spec,
    assembly,
  }) : undefined, [assembly, propellerName, spec])
  const resultRevision = designMode === 'propeller' ? JSON.stringify(propellerSpec) : revision
  designSnapshotRef.current = resultRevision
  const stale = Boolean(displayedResult && (
    displayedResult.build_type !== designMode
    || displayedResult.submitted_snapshot !== resultRevision
  ))
  const busy = submitting || activeJob?.status === 'queued' || activeJob?.status === 'running'
  const curveBusy = curveInteraction !== 'idle'
  const hubGuidance = useMemo(
    () => spec ? nominalHubGuidance(spec, assembly) : undefined,
    [assembly, spec],
  )
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
    markDraftModified()
    cancelCurveWork()
    clearCurveHistory()
    setSpec(next)
    setErrors(validateEditorSpec(next))
  }
  const commitCurveCandidate = async (
    candidate: BladeSpec,
    label: string,
    expectedSnapshot?: string,
    signal?: AbortSignal,
  ): Promise<boolean> => {
    const before = specRef.current
    if (!before || curveInteraction === 'validating' || signal?.aborted) return false
    const beforeSnapshot = canonicalJson(before)
    if (expectedSnapshot && beforeSnapshot !== expectedSnapshot) {
      setErrors(['The design changed after this review opened. Reopen the operation to review values against the current snapshot.'])
      setMessage(`${label} cancelled because the design changed`)
      return false
    }
    if (canonicalJson(candidate) === beforeSnapshot) return true
    const local = validateEditorSpec(candidate)
    if (local.length) {
      setErrors(local)
      setMessage(`Curve edit rejected: ${local[0]}`)
      setCurveInteraction('idle')
      return false
    }
    const token = ++curveValidationRevision.current
    setCurveInteraction('validating')
    setErrors([])
    setMessage(`Validating ${label}…`)
    try {
      await validateBackend(candidate, signal)
      if (signal?.aborted || curveValidationRevision.current !== token || !specRef.current || canonicalJson(specRef.current) !== beforeSnapshot) return false
      curveHistory.current.push({ before, after: candidate, label })
      refreshHistory()
      markDraftModified()
      setSpec(structuredClone(candidate))
      setErrors([])
      setMessage(`${label} committed; canonical preview updating`)
      return true
    } catch (error) {
      if (signal?.aborted || curveValidationRevision.current !== token) return false
      const detail = error instanceof Error ? error.message : String(error)
      setErrors([`Curve edit rejected by backend: ${detail}`])
      setMessage(`Curve edit rejected: ${detail}`)
      return false
    } finally {
      if (curveValidationRevision.current === token) setCurveInteraction('idle')
    }
  }
  const commitCurvePoint = (definition: typeof CURVES[number], index: number, displayed: number) => {
    try {
      return commitCurveCandidate(replaceCurvePoint(spec, definition, index, displayed), `${definition.title} control edit`)
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      setErrors([detail])
      setMessage(`Curve edit rejected: ${detail}`)
      setCurveInteraction('idle')
      return Promise.resolve(false)
    }
  }
  const field = <K extends keyof BladeSpec>(key: K, value: BladeSpec[K]) => update({ ...spec, [key]: value })
  const assemblyField = <K extends keyof AssemblySpec>(key: K, value: AssemblySpec[K]) => {
    cancelCurveWork()
    markDraftModified()
    setAssembly(current => ({ ...current, [key]: value }))
    setErrors([])
    setMessage('Assembly parameters changed; validate or generate explicitly')
  }
  const switchDesignMode = (mode: 'blade' | 'propeller') => {
    if (mode === designMode) return
    cancelCurveWork()
    setDistributionImportSnapshot(undefined)
    setStationSetupSnapshot(undefined)
    markDraftModified()
    setDesignMode(mode)
    setMessage(`${mode === 'propeller' ? 'Full Propeller' : 'Single Blade'} mode selected`)
  }
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
  const applyProfiles = async (
    indices: number[],
    profile: AirfoilProfile,
    constantThickness = false,
  ) => {
    try {
      const unique = [...new Set(indices)].sort((left, right) => left - right)
      let candidate = spec
      for (const index of unique) candidate = applyAirfoilProfile(candidate, index, profile)
      if (constantThickness) {
        if (unique.length !== spec.airfoil_sections.length) {
          throw new Error('Select every airfoil station before replacing Thickness with a common constant')
        }
        const ratio = profile.airfoil.type === 'coordinates'
          ? profile.metrics.max_thickness_ratio
          : Number(profile.airfoil.code.slice(2)) / 100
        candidate = {
          ...candidate,
          thickness_distribution: {
            interpolation: candidate.thickness_distribution.interpolation,
            points: [
              { r_over_R: candidate.root_radius_ratio, thickness_ratio: ratio },
              { r_over_R: 1, thickness_ratio: ratio },
            ],
          },
        }
      }
      const accepted = await commitCurveCandidate(
        candidate,
        `Apply ${profile.display_name} to ${unique.length} airfoil station${unique.length === 1 ? '' : 's'}`,
      )
      if (!accepted) return
      setProfileNames(names => names.map((name, current) => unique.includes(current) ? profile.display_name : name))
      setSelectedStationId(rowIds[unique[0]])
      setInspectionMode('single')
      setSelectorStation(undefined)
      setSelectorTargets([])
      setSelectedProfileStationIds([])
      setMessage(`${profile.display_name} applied to ${unique.length} station${unique.length === 1 ? '' : 's'}; design preview updating`)
    } catch (error) { setErrors([error instanceof Error ? error.message : String(error)]) }
  }
  const validateCurrentInputs = async (): Promise<boolean> => {
    const snapshot = resultRevision
    const token = ++inputValidationRevision.current
    const local = validateEditorSpec(spec)
    setErrors(local)
    setValidationIssues([])
    if (local.length) {
      setDraftValidation({ state: 'invalid', snapshot })
      setMessage('Current inputs are invalid. No new CAD build was started.')
      return false
    }
    setDraftValidation({ state: 'checking', snapshot })
    setMessage('Checking current inputs…')
    try {
      if (designMode === 'propeller') {
        if (!propellerSpec) throw new Error('PropellerSpec is unavailable')
        await validatePropeller(structuredClone(propellerSpec))
      } else {
        await validateBackend(structuredClone(spec))
      }
      if (inputValidationRevision.current !== token || designSnapshotRef.current !== snapshot) {
        return false
      }
      setDraftValidation({ state: 'valid', snapshot })
      setValidationIssues([])
      setMessage('Input validation passed; final geometric qualification has not yet run.')
      return true
    } catch (error) {
      if (inputValidationRevision.current !== token || designSnapshotRef.current !== snapshot) {
        return false
      }
      const issues = structuredIssues(error)
      const detail = error instanceof Error ? error.message : String(error)
      setValidationIssues(issues.length ? issues : [{
        code: 'input_validation_failed',
        field: '',
        message: detail,
      }])
      setDraftValidation({ state: 'invalid', snapshot })
      setMessage('Current inputs are invalid. No new CAD build was started.')
      return false
    }
  }
  const submit = async () => {
    if (submissionPending.current || busy) return
    submissionPending.current = true
    setSubmitting(true)
    const valid = await validateCurrentInputs()
    if (!valid) {
      submissionPending.current = false
      setSubmitting(false)
      return
    }
    const propeller = propellerSpec
    try {
      const buildType = designMode
      const snapshot = buildType === 'propeller'
        ? JSON.stringify(structuredClone(propeller!))
        : canonicalJson(structuredClone(spec))
      const next = buildType === 'propeller' ? await buildPropeller(propeller!) : await buildBlade(spec)
      submissionSnapshots.current.set(next.job_id, { snapshot, buildType })
      activeJobId.current = next.job_id
      setActiveJob(next)
      setMessage(`Build ${next.job_id.slice(0, 8)} accepted by the CAD worker`)
    } catch (error) {
      const issues = structuredIssues(error)
      if (issues.length) {
        setValidationIssues(issues)
        setDraftValidation({ state: 'invalid', snapshot: resultRevision })
        setMessage('Current inputs are invalid. No new CAD build was started.')
      } else {
        setMessage(`Build submission failure: ${error instanceof Error ? error.message : String(error)}`)
      }
    } finally {
      submissionPending.current = false
      setSubmitting(false)
    }
  }
  const check = async () => {
    await validateCurrentInputs()
  }
  const exportJson = () => {
    const exported = designMode === 'propeller' ? propellerSpec : spec
    const blob = new Blob([`${JSON.stringify(exported, null, 2)}\n`], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${designMode === 'propeller' ? propellerSpec?.name || 'propeller' : spec.name || 'blade'}.json`
    anchor.click()
    URL.revokeObjectURL(url)
  }
  const importJson = async (file?: File) => {
    if (!file) return
    const token = ++inputValidationRevision.current
    setProjectImportFailure(undefined)
    try {
      const candidate = parseProjectDocument(await file.text())
      if (candidate.kind === 'propeller') {
        await validatePropeller(propellerFromProject(candidate))
      } else {
        await validateBackend(candidate.bladeSpec)
      }
      if (inputValidationRevision.current !== token) return
      loadProject(candidate, true, `Opened and validated ${file.name}`)
    } catch (error) {
      if (inputValidationRevision.current !== token) return
      const detail = error instanceof Error ? error.message : String(error)
      const issues = structuredIssues(error)
      setProjectImportFailure({
        detail,
        issues: issues.length ? issues : [{
          code: 'project_import_invalid',
          field: '',
          message: detail,
        }],
      })
      setMessage('Import rejected — the current project was preserved')
    }
  }
  const reset = () => {
    if (baseline && window.confirm('Discard current edits and restore the complete project baseline?')) {
      loadProject(baseline, false, 'Complete project baseline restored')
    }
  }
  const loadExample = () => {
    if (exampleProject) loadProject(exampleProject, true, 'Blade example loaded with default assembly settings')
  }
  const createNew = () => {
    if (!window.confirm('Start a new project from neutral defaults?')) return
    const source = structuredClone(exampleProject?.bladeSpec ?? baseline?.bladeSpec ?? spec)
    const project = bladeProject({ ...source, name: 'untitled_blade' })
    project.propellerName = 'untitled_propeller'
    loadProject(project, true, 'New single-blade project created with default assembly settings')
  }

  const artifacts = displayedResult?.artifacts ?? []
  const previewName = displayedResult?.build_type === 'propeller' ? 'propeller_preview.stl' : 'blade_preview.stl'
  const preview = artifacts.find(artifact => artifact.name === previewName)
  const assemblyValidation = displayedResult?.validation_data?.assembly_validation
  const solid = assemblyValidation?.final_after_reimport
    ?? displayedResult?.validation_data?.solidification?.solid_after_reimport
  const geometry = displayedResult?.validation_data?.geometry_validation
  const selectedPreview = currentDesignPreview?.stations[selectedStation]
  const profileWarnings = currentDesignPreview?.stations.filter(station => station.diagnostics?.has_warning) ?? []
  const comparisonChoices = currentDesignPreview?.stations.map((station, index) => ({ id: rowIds[index], index, station })).filter(choice => Boolean(choice.id)) ?? []
  const guidesEnabled = Boolean(
    displayedResult?.build_type === 'blade' && designMode === 'blade'
    && preview && !stale && designPreviewCurrent,
  )
  const guideStatus = displayedResult?.build_type === 'propeller' || designMode === 'propeller'
    ? 'Station guides are disabled for full-propeller preview; inspect stations in Single Blade mode.'
    : !preview
    ? 'Generate the blade to place station guides on matching CAD.'
    : stale
      ? 'Station guides hidden: displayed CAD belongs to previous inputs. Regenerate to align current stations.'
      : !designPreviewCurrent
        ? 'Station guides hidden until the canonical preview for this revision is current.'
        : 'Visual radial-location guides derived from the current design; they are not extracted STEP cross-sections.'
  const activeCurve = CURVES.find(curve => curve.name === activeDistribution)!
  const activeControls = (spec[activeCurve.key] as Distribution).points.map(point => ({
    radius: point.r_over_R,
    value: storedToDisplay(activeCurve.name, point[activeCurve.valueKey], spec.diameter_mm),
    lockedReason: activeCurve.name === 'thickness' ? thicknessControlLock(spec, point.r_over_R) : undefined,
  }))
  const chartPreview = designPreview?.distributions[activeDistribution]
  const chartPreviewStale = Boolean(chartPreview && designPreviewSnapshot !== revision)
  const historyStatus = `${curveHistory.current.canUndo ? `Undo ${curveHistory.current.undoLabel}` : 'Nothing to undo'} · ${curveHistory.current.canRedo ? `Redo ${curveHistory.current.redoLabel}` : 'Nothing to redo'}`

  return (
    <main>
      <header>
        <div>
          <p className="eyebrow">LEVEL 1 · SPRINT 04B</p>
          <h1>BladeGen</h1>
          <p>One validated blade → OCP propeller assembly → independently qualified solid</p>
        </div>
        <div className="actions">
          <button onClick={createNew}>New</button>
          <button onClick={() => fileInput.current?.click()}>Open JSON</button>
          <input ref={fileInput} hidden type="file" accept="application/json,.json" onChange={event => { void importJson(event.target.files?.[0]); event.target.value = '' }} />
          <button onClick={exportJson}>Export JSON</button>
          <button onClick={loadExample}>Load Example</button>
          <button onClick={reset}>Reset</button>
          <button aria-label="Undo curve edit" disabled={!curveHistory.current.canUndo || curveBusy} title={historyStatus} onClick={undoCurveEdit}>Undo</button>
          <button aria-label="Redo curve edit" disabled={!curveHistory.current.canRedo || curveBusy} title={historyStatus} onClick={redoCurveEdit}>Redo</button>
          <button onClick={check}>{designMode === 'propeller' ? 'Validate Assembly' : 'Validate'}</button>
          <button className="primary" disabled={busy || curveBusy} onClick={submit}>{busy ? 'Generating…' : curveInteraction === 'drafting' ? 'Editing curve…' : curveInteraction === 'validating' ? 'Validating curve…' : designMode === 'propeller' ? 'Generate Propeller' : 'Generate Blade'}</button>
        </div>
      </header>

      <div className="design-mode-tabs" role="group" aria-label="Design mode">
        <button aria-pressed={designMode === 'blade'} onClick={() => switchDesignMode('blade')}>Single Blade</button>
        <button aria-pressed={designMode === 'propeller'} onClick={() => switchDesignMode('propeller')}>Full Propeller</button>
      </div>

      <div className={`status current-design-status ${draftValidation.state} ${stale ? 'stale' : ''}`}>
        <strong>Current design · {draftValidation.state === 'modified' ? 'Modified / not yet checked' : draftValidation.state === 'checking' ? 'Checking inputs' : draftValidation.state === 'valid' ? 'Input checks passed' : 'Input checks failed'}</strong>
        {' — '}{message}{stale && <b> · Inputs changed — regenerate to update CAD.</b>}
      </div>
      {activeJob && activeJob.status !== 'succeeded' && <p className="active-generation-label"><strong>Active job {activeJob.job_id.slice(0, 8)} · {activeJob.status}</strong> · {activeJob.build_type}</p>}
      <BuildProgress job={activeJob?.status === 'succeeded' ? undefined : activeJob} />
      {draftValidation.state === 'invalid' && <div className="error-panel current-input-errors" role="alert">
        <strong>Current inputs are invalid. No new CAD build was started.</strong>
        {validationIssues.length > 0 && <ul>{validationIssues.map((issue, index) => <li key={`${issue.code}-${issue.field}-${index}`}><span className="issue-field">{issue.field || 'project'}</span> — {issue.message}</li>)}</ul>}
      </div>}
      {projectImportFailure && <div className="error-panel project-import-errors" role="alert">
        <strong>Project import rejected. The current project was preserved.</strong>
        <ul>{projectImportFailure.issues.map((issue, index) => <li key={`${issue.code}-${issue.field}-${index}`}><span className="issue-field">{issue.field || 'file'}</span> — {issue.message}</li>)}</ul>
      </div>}
      {errors.length > 0 && <div className="error-panel"><strong>Input validation</strong><ul>{errors.map(error => <li key={error}>{error}</li>)}</ul></div>}
      {cadPreviewError && <div className="error-panel"><strong>Preview loading failure:</strong> {cadPreviewError}</div>}

      <div className="layout">
        <div className="editor">
          {designMode === 'propeller' && <section className="assembly-card">
            <h2>Propeller Assembly</h2>
            <p className="hint">Blade count is the number of identical blades around the hub. It does not change the {spec.airfoil_sections.length} radial airfoil sections that define one blade.</p>
            <div className="grid">
              <label>Propeller Name<input aria-label="Propeller Name" value={propellerName} onChange={event => { markDraftModified(); setPropellerName(event.target.value) }} /></label>
              <label>Number of Blades<select aria-label="Number of Blades" value={assembly.blade_count} onChange={event => assemblyField('blade_count', Number(event.target.value))}>
                {(propellerCapabilities?.supported_blade_counts ?? []).map(count => <option key={count} value={count}>{count}</option>)}
              </select></label>
              <label>Hub Diameter (mm)<NumericInput label="Hub Diameter" value={assembly.hub_diameter_mm} onCommit={value => assemblyField('hub_diameter_mm', value)} /></label>
              <label>Hub Length (mm)<NumericInput label="Hub Length" value={assembly.hub_length_mm} onCommit={value => assemblyField('hub_length_mm', value)} /></label>
              <label>Shaft Bore Diameter (mm)<NumericInput label="Shaft Bore Diameter" value={assembly.shaft_bore_diameter_mm} onCommit={value => assemblyField('shaft_bore_diameter_mm', value)} /></label>
              <label>Initial Azimuth (deg)<NumericInput label="Initial Azimuth" value={assembly.initial_azimuth_deg} onCommit={value => assemblyField('initial_azimuth_deg', value)} /></label>
            </div>
            <div className="assembly-summary" aria-label="Assembly definition summary">
              <span><strong>{assembly.blade_count}</strong> identical blades</span>
              <span><strong>X axis</strong> rotation and bore</span>
              <span><strong>{propellerCapabilities?.supported_blade_counts.join(', ') || 'Loading…'}</strong> qualified blade choices</span>
            </div>
            {hubGuidance && <div className={`hub-guidance ${hubGuidance.passes_nominal_policy ? 'compatible' : 'incompatible'}`} aria-label="Nominal hub compatibility">
              <strong>{hubGuidance.passes_nominal_policy ? 'Nominal radial policy passes.' : 'Hub diameter is too small for the current blade root.'}</strong>
              <dl>
                <dt>Blade root radius</dt><dd>{formatMillimetres(hubGuidance.root_radius_mm)} mm</dd>
                <dt>Current hub radius</dt><dd>{formatMillimetres(hubGuidance.hub_radius_mm)} mm</dd>
                <dt>{hubGuidance.passes_nominal_policy ? 'Nominal radial overlap' : 'Nominal radial gap'}</dt><dd>{formatMillimetres(hubGuidance.passes_nominal_policy ? hubGuidance.nominal_radial_overlap_mm : hubGuidance.nominal_radial_gap_mm)} mm</dd>
                <dt>Required hub diameter</dt><dd>greater than {formatMillimetres(hubGuidance.required_hub_diameter_bound_mm)} mm</dd>
              </dl>
              <p>Hub Length controls axial extent and cannot close a radial gap. Passing this preflight does not guarantee CAD overlap, fusion, or structural suitability.</p>
            </div>}
            {propellerCapabilities && <p className="hint">{propellerCapabilities.release_policy}</p>}
          </section>}
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
            <div className="section-title"><h2>Airfoil Stations ({spec.airfoil_sections.length})</h2><div className="section-actions"><button onClick={addStation}>Add Airfoil Station</button><button onClick={() => setStationSetupSnapshot(structuredClone(spec))}>Set Up Airfoil Stations</button><button disabled={!selectedProfileStationIds.length} onClick={() => {
              const targets = selectedProfileStationIds.map(id => rowIds.indexOf(id)).filter(index => index >= 0)
              if (!targets.length) return
              setSelectorTargets(targets)
              setSelectorStation(targets[0])
            }}>Apply Profile to Selected Stations</button></div></div>
            <p className="selected-station-summary">{inspectionMode === 'single'
              ? <>Inspecting Station {selectedStation + 1} · r/R {spec.airfoil_sections[selectedStation]?.r_over_R.toFixed(4)}</>
              : <>Comparing Station A {rowIds.indexOf(comparisonAId) + 1} with Station B {rowIds.indexOf(comparisonBId) + 1}</>}</p>
            <div className="station-table-scroll"><table>
              <thead><tr><th>Select</th><th>r/R</th><th>Profile</th><th>TE mm</th><th>Effective t/c</th><th>Override</th><th>Status</th><th /></tr></thead>
              <tbody>{spec.airfoil_sections.map((section, index) => {
                const stationId = rowIds[index]
                const rowState = inspectionMode === 'single' && selectedStationId === stationId ? 'selected' : inspectionMode === 'compare' && comparisonAId === stationId ? 'compare-a' : inspectionMode === 'compare' && comparisonBId === stationId ? 'compare-b' : ''
                return <tr key={stationId} className={'station-row ' + rowState} data-station-id={stationId}>
                <td><input aria-label={`Select airfoil station ${index + 1}`} type="checkbox" checked={selectedProfileStationIds.includes(stationId)} onChange={event => setSelectedProfileStationIds(current => event.target.checked ? [...current, stationId] : current.filter(id => id !== stationId))} /></td>
                <td><NumericInput label={`Airfoil radius ${index + 1}`} step=".01" value={section.r_over_R} disabled={index === 0 || index === spec.airfoil_sections.length - 1} onCommit={value => changeStationRadius(index, value)} /></td>
                <td className="station-profile">
                  <span className="station-profile-name">{profileNames[index] ?? stationLabel(section)}</span>
                  {section.airfoil.type === 'naca4'
                    ? <input aria-label={`NACA code ${index + 1}`} inputMode="numeric" maxLength={4} value={section.airfoil.code} onChange={event => changeNaca(index, event.target.value)} />
                    : <details><summary>Embedded coordinates</summary><pre>{JSON.stringify(section.airfoil, null, 2)}</pre></details>}
                  <div className="station-profile-actions"><button onClick={() => { setSelectorTargets([index]); setSelectorStation(index) }}>Choose from Library</button><button onClick={() => { setSelectedStationId(stationId); setInspectionMode('single') }}>Inspect</button><button onClick={() => { setComparisonAId(stationId); setComparisonBId(current => current === stationId ? rowIds.find(id => id !== stationId) ?? stationId : current); setInspectionMode('compare') }}>Compare as A</button></div>
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
            <div className="section-title"><div><h2>Independent Spanwise Distributions</h2><p className="hint">Distribution controls are independent from airfoil stations and computed preview samples.</p></div><button onClick={() => setDistributionImportSnapshot(structuredClone(spec))}>Import Distributions</button></div>
            <div className="distribution-visual">
              <div className="curve-history-toolbar"><span aria-live="polite">{historyStatus}</span><span className={`curve-edit-state ${curveInteraction}`}>{curveInteraction === 'idle' ? 'Ready' : curveInteraction === 'drafting' ? 'Draft — release to validate' : 'Validating candidate…'}</span></div>
              <div className="distribution-tabs" role="group" aria-label="Distribution chart selection">{CURVES.map(curve => <button key={curve.name} aria-pressed={activeDistribution === curve.name} onClick={() => { cancelCurveWork(); setActiveDistribution(curve.name) }}>{curve.title}</button>)}</div>
              <DistributionChart
                key={activeDistribution}
                title={`${activeCurve.title} Distribution`}
                data={chartPreview}
                controls={activeControls}
                unit={activeCurve.unit}
                step={activeCurve.step}
                stale={chartPreviewStale}
                cancelVersion={curveCancelVersion}
                onCommit={(index, value) => commitCurvePoint(activeCurve, index, value)}
                onInteractionChange={setCurveInteraction}
                onError={error => setErrors(error ? [error] : [])}
              />
            </div>
            <div className="curves">{CURVES.map(definition => <DistributionTable
              key={`${definition.key}-${epoch}`}
              definition={definition}
              diameterMm={spec.diameter_mm}
              value={spec[definition.key]}
              disabled={curveBusy}
              lockReason={radius => definition.name === 'thickness' ? thicknessControlLock(spec, radius) : undefined}
              onPointValue={(index, displayed) => commitCurvePoint(definition, index, displayed)}
              onChange={(value, label) => commitCurveCandidate({ ...spec, [definition.key]: value }, label)}
              onError={error => setErrors(error ? [error] : [])}
            />)}</div>
          </section>
        </div>

        <aside>
          <h2>{displayedResult?.build_type === 'propeller' ? 'Full propeller preview' : 'Solid preview'}</h2>
          {displayedResult && <p className={stale ? 'preview-label stale' : 'preview-label'} data-result-job-id={displayedResult.job_id}><strong>Last successful build{stale ? ' — previous inputs' : ' — current inputs'}</strong> · Preview from completed job {displayedResult.job_id.slice(0, 8)} · <span className="build-kind">{displayedResult.build_type}</span>{stale ? ' · previous inputs or mode' : ''}</p>}
          <BladeViewer modelType={displayedResult?.build_type ?? designMode} url={preview?.download_url} onError={setCadPreviewError} guides={stationGuides} guidesEnabled={guidesEnabled} guideStatus={guideStatus} />
          {solid && <><h2>STEP topology</h2><dl><dt>Solid / free edges</dt><dd>{solid.solids} / {solid.free_edges}</dd><dt>Closed / BRep valid</dt><dd>{String(solid.closed_shell)} / {String(solid.brepcheck_valid)}</dd><dt>Adaptive volume</dt><dd>{solid.volume_mm3.toFixed(6)} mm³</dd></dl></>}
          {assemblyValidation && <><h2>Assembly validation</h2><dl>
            <dt>Overall</dt><dd>{assemblyValidation.passed ? 'PASS' : 'FAIL'}</dd>
            <dt>Blades / axis</dt><dd>{assemblyValidation.actual_blade_placement_count} / {assemblyValidation.rotation_axis.join(', ')}</dd>
            <dt>Azimuths</dt><dd>{assemblyValidation.azimuth_angles_deg.map(value => `${value.toFixed(1)}°`).join(', ')}</dd>
            <dt>Hub / length / bore</dt><dd>{assemblyValidation.hub_diameter_mm} / {assemblyValidation.hub_length_mm} / {assemblyValidation.shaft_bore_diameter_mm} mm</dd>
            <dt>Minimum root overlap</dt><dd>{Math.min(...assemblyValidation.hub_blade_overlap_mm3).toFixed(6)} mm³</dd>
            <dt>Bore radius / obstruction</dt><dd>{assemblyValidation.bore.measured_radii_mm[0]?.toFixed(6)} mm / {assemblyValidation.bore.residual_material_volume_mm3.toExponential(2)} mm³</dd>
            <dt>Copy volume delta</dt><dd>{assemblyValidation.maximum_copy_volume_delta_mm3.toExponential(2)} mm³</dd>
            <dt>STEP volume / bbox delta</dt><dd>{assemblyValidation.roundtrip.volume_delta_mm3.toExponential(2)} / {assemblyValidation.roundtrip.bbox_max_abs_delta_mm.toExponential(2)} mm</dd>
          </dl></>}
          {geometry && <><h2>Independent geometry</h2><dl><dt>Overall</dt><dd>{geometry.passed ? 'PASS' : 'FAIL'}</dd><dt>Chord / twist max</dt><dd>{geometry.max_chord_error_mm.toFixed(5)} mm / {geometry.max_twist_error_deg.toFixed(5)}°</dd><dt>Axis / TE max</dt><dd>{geometry.max_reference_axis_error_mm.toFixed(5)} / {geometry.max_te_error_mm.toFixed(5)} mm</dd><dt>Contour RMS / P95 / max</dt><dd>{geometry.control_contour_rms_max_mm.toFixed(5)} / {geometry.control_contour_p95_max_mm.toFixed(5)} / {geometry.control_contour_max_mm.toFixed(5)} mm</dd><dt>Root requested / sampled</dt><dd>{geometry.root_measurement.requested_r_over_R} / {geometry.root_measurement.measured_r_over_R}</dd><dt>Tip requested / sampled</dt><dd>{geometry.tip_measurement.requested_r_over_R} / {geometry.tip_measurement.measured_r_over_R}</dd></dl><details><summary>Per-station measurements ({geometry.stations.length})</summary><table><thead><tr><th>Requested</th><th>Sampled</th><th>Roles</th><th>Chord</th><th>Twist</th><th>TE</th></tr></thead><tbody>{geometry.stations.map(row => <tr key={row.requested_r_over_R}><td>{row.requested_r_over_R}</td><td>{row.sampled_r_over_R}</td><td>{row.station_roles.join(', ')}</td><td>{row.chord_absolute_error_mm.toFixed(4)}</td><td>{row.twist_absolute_error_deg.toFixed(4)}</td><td>{row.te_absolute_error_mm.toFixed(4)}</td></tr>)}</tbody></table></details></>}
          <h2>Artifacts</h2>
          {displayedResult && <p className="hint">Artifacts from completed job {displayedResult.job_id.slice(0, 8)}</p>}
          {artifacts.length ? <ul>{artifacts.map(artifact => <li key={artifact.name}><a href={artifact.download_url}>{artifact.name}</a> <small>{Math.ceil(artifact.size_bytes / 1024)} KB</small></li>)}</ul> : <p>No completed build artifacts yet.</p>}
        </aside>
      </div>
      {selectorStation !== undefined && <AirfoilSelector
        stationIndex={selectorStation}
        radius={spec.airfoil_sections[selectorStation].r_over_R}
        targetStations={(selectorTargets.length ? selectorTargets : [selectorStation]).map(index => ({ index, radius: spec.airfoil_sections[index].r_over_R }))}
        onApply={(profile, options) => { void applyProfiles(selectorTargets.length ? selectorTargets : [selectorStation], profile, options.constantThickness) }}
        onCancel={() => { setSelectorStation(undefined); setSelectorTargets([]) }}
      />}
      {distributionImportSnapshot && <DistributionImportDialog
        snapshot={distributionImportSnapshot}
        onApply={commitCurveCandidate}
        onCancel={() => setDistributionImportSnapshot(undefined)}
      />}
      {stationSetupSnapshot && <AirfoilStationSetupDialog
        snapshot={stationSetupSnapshot}
        profileNames={profileNames}
        onApply={commitCurveCandidate}
        onCommitted={resetStationUi}
        onCancel={() => setStationSetupSnapshot(undefined)}
      />}
    </main>
  )
}
