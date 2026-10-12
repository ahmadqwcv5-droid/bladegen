import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import example from '../../examples/custom_multi_airfoil_finite_te.json'
import App from './App'
import type { BladeSpec, DesignPreview, ProfileDiagnostics } from './types/bladespec'

const api = vi.hoisted(() => ({
  getExample: vi.fn(), validate: vi.fn(), build: vi.fn(), getJob: vi.fn(), getArtifacts: vi.fn(),
  getDesignPreview: vi.fn(), getPropellerCapabilities: vi.fn(), getAirfoilCatalog: vi.fn(), getAirfoilProfile: vi.fn(), importAirfoil: vi.fn(),
}))
vi.mock('./api/client', () => api)
vi.mock('./components/BladeViewer', () => ({ BladeViewer: () => <div data-testid="viewer" /> }))

const diagnostics: ProfileDiagnostics = {
  upper_point_count: 5, lower_point_count: 5, maximum_chordwise_spacing: .25,
  upper_leading_edge_point_count: 1, lower_leading_edge_point_count: 1,
  warning_codes: ['low_coordinate_density'], warnings: ['Sparse'], has_warning: true,
  advisory: 'Low coordinate density detected. OpenVSP surface reconstruction may deviate from the supplied polyline. Final STEP fidelity will be checked after generation.',
}

function warningPreview(spec: BladeSpec): DesignPreview {
  const metrics = { max_thickness_ratio: .12, max_thickness_x_over_c: .3, max_camber_ratio: 0, max_camber_x_over_c: 0, trailing_edge_gap_ratio: 0 }
  const contour = { upper: [[0, 0], [.5, .06], [1, 0]], lower: [[0, 0], [.5, -.06], [1, 0]], metrics }
  const distribution = (unit: string) => ({ interpolation: 'linear' as const, unit, samples: [[.2, 1], [.6, 2], [1, 3]], controls: [[.2, 1], [1, 3]] })
  return {
    schema_version: '1',
    stations: [{
      r_over_R: spec.airfoil_sections[0].r_over_R, name: 'Embedded coordinate profile', kind: 'coordinates',
      local_chord_mm: 60, nominal_thickness_ratio: .12, effective_thickness_ratio: .12,
      requested_trailing_edge_thickness_mm: .8, source: contour, resolved: contour,
      diagnostics, preview_status: 'canonical design definition; final CAD validation not yet performed',
    }],
    distributions: {
      chord: distribution('mm'), twist: distribution('deg'), rake: distribution('mm'),
      skew: distribution('mm'), thickness: distribution('% t/c'),
    },
  }
}

afterEach(() => cleanup())
beforeEach(() => {
  vi.clearAllMocks()
  api.getExample.mockResolvedValue(structuredClone(example))
  api.validate.mockResolvedValue({ valid: true })
  api.getDesignPreview.mockImplementation(async (spec: BladeSpec) => warningPreview(spec))
  let nextId = 0
  vi.stubGlobal('crypto', { randomUUID: vi.fn(() => "patch-03a1-" + ++nextId) })
})

it('surfaces embedded-coordinate warnings design-wide without modifying BladeSpec', async () => {
  const original = JSON.stringify(example)
  render(<App />)
  const summary = await screen.findByRole('status', { name: 'Design coordinate diagnostic summary' })
  expect(summary).toHaveTextContent('r/R 0.2000')
  expect(summary).toHaveTextContent('Final STEP fidelity will be checked after generation')
  expect(JSON.stringify(example)).toBe(original)
})
