import type { Artifact, BladeSpec, Job } from '../types/bladespec'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, options)
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail))
  }
  return response.json()
}
export const getExample = (id = 'custom_multi_airfoil_finite_te') => request<BladeSpec>(`/examples/${id}`)
export const validate = (spec: BladeSpec) => request<Record<string, unknown>>('/validate', {
  method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(spec),
})
export const build = (spec: BladeSpec) => request<Job>('/build', {
  method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(spec),
})
export const getJob = (id: string) => request<Job>(`/jobs/${id}`)
export const getArtifacts = (id: string) => request<Artifact[]>(`/jobs/${id}/artifacts`)
