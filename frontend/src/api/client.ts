import type {
  AirfoilCatalogItem,
  AirfoilProfile,
  Artifact,
  BladeSpec,
  DesignPreview,
  Job,
  PropellerCapabilities,
  PropellerSpec,
  PropellerValidationResponse,
  ValidationIssue,
} from '../types/bladespec'

export class ApiError extends Error {
  issues: ValidationIssue[]

  constructor(message: string, issues: ValidationIssue[] = []) {
    super(message)
    this.name = 'ApiError'
    this.issues = issues
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, options)
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    const detail = typeof body.detail === 'string'
      ? body.detail
      : typeof body.detail?.message === 'string'
        ? body.detail.message
        : response.statusText
    throw new ApiError(detail, Array.isArray(body.issues) ? body.issues : [])
  }
  return response.json()
}
export const getExample = (id = 'custom_multi_airfoil_finite_te') => request<BladeSpec>(`/examples/${id}`)
export const validate = (spec: BladeSpec, signal?: AbortSignal) => request<Record<string, unknown>>('/validate', {
  method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(spec), signal,
})
export const build = (spec: BladeSpec) => request<Job>('/build', {
  method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(spec),
})
export const getPropellerCapabilities = () => request<PropellerCapabilities>('/propellers/capabilities')
export const validatePropeller = (spec: PropellerSpec) => request<PropellerValidationResponse>('/propellers/validate', {
  method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(spec),
})
export const buildPropeller = (spec: PropellerSpec) => request<Job>('/propellers/build', {
  method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(spec),
})
export const getJob = (id: string) => request<Job>(`/jobs/${id}`)
export const getArtifacts = (id: string) => request<Artifact[]>(`/jobs/${id}/artifacts`)

export const getAirfoilCatalog = () => request<AirfoilCatalogItem[]>('/airfoils/catalog')
export const getAirfoilProfile = (id: string) => request<AirfoilProfile>(`/airfoils/${encodeURIComponent(id)}`)
export const importAirfoil = (
  file: File,
  metadata: {
    displayName: string
    source?: string
    license?: string
    notes?: string
    normalize?: boolean
  },
) => {
  const query = new URLSearchParams({
    filename: file.name,
    display_name: metadata.displayName,
    normalize: String(Boolean(metadata.normalize)),
  })
  if (metadata.source) query.set('source', metadata.source)
  if (metadata.license) query.set('license_info', metadata.license)
  if (metadata.notes) query.set('notes', metadata.notes)
  return request<AirfoilProfile>(`/airfoils/import?${query}`, {
    method: 'POST',
    headers: {'Content-Type': file.type || 'text/plain'},
    body: file,
  })
}
export const getDesignPreview = (spec: BladeSpec, signal?: AbortSignal) => request<DesignPreview>('/design-preview', {
  method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(spec), signal,
})
