import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import example from '../../examples/custom_multi_airfoil_finite_te.json'
import App from './App'
import type { BladeSpec } from './types/bladespec'

const api = vi.hoisted(() => ({
  getExample: vi.fn(),
  validate: vi.fn(),
  build: vi.fn(),
  getJob: vi.fn(),
  getArtifacts: vi.fn(),
  getDesignPreview: vi.fn(),
}))
vi.mock('./api/client', () => api)
vi.mock('./components/BladeViewer', () => ({
  BladeViewer: () => <div data-testid="viewer" />,
}))

const source = () => structuredClone(example) as BladeSpec

afterEach(() => cleanup())

beforeEach(() => {
  vi.clearAllMocks()
  api.validate.mockResolvedValue({ valid: true })
  api.getDesignPreview.mockResolvedValue({ stations: [], distributions: {} })
  vi.stubGlobal('confirm', vi.fn(() => true))
  vi.stubGlobal('crypto', { randomUUID: vi.fn(() => Math.random().toString(36)) })
})

async function load(spec: BladeSpec) {
  api.getExample.mockResolvedValueOnce(spec)
  render(<App />)
  await screen.findByText(`Airfoil Stations (${spec.airfoil_sections.length})`)
}

describe('nullable thickness override UI semantics', () => {
  it('renders both null and omitted API fields as unchecked overrides', async () => {
    const spec = source()
    spec.airfoil_sections[0].thickness_override_ratio = null
    delete spec.airfoil_sections[1].thickness_override_ratio
    await load(spec)
    const checkboxes = screen.getAllByRole('checkbox', { name: 'explicit' })
    expect(checkboxes[0]).not.toBeChecked()
    expect(checkboxes[1]).not.toBeChecked()
    expect(screen.queryByLabelText('Thickness override 1')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Thickness override 2')).not.toBeInTheDocument()
  })

  it('renders a valid numeric override as checked', async () => {
    const spec = source()
    const index = spec.airfoil_sections.length - 1
    spec.airfoil_sections[index].thickness_override_ratio = .10
    await load(spec)
    expect(screen.getAllByRole('checkbox', { name: 'explicit' })[index]).toBeChecked()
    expect(screen.getByLabelText(`Thickness override ${index + 1}`)).toHaveValue(.10)
  })

  it('coordinates null-override NACA edits and enable/disable behavior before validation', async () => {
    const user = userEvent.setup()
    const spec = source()
    const index = spec.airfoil_sections.length - 1
    spec.airfoil_sections[index].thickness_override_ratio = null
    const originalTrailingEdge = spec.airfoil_sections[index].trailing_edge_thickness_mm
    await load(spec)

    const code = screen.getByLabelText(`NACA code ${index + 1}`)
    const row = code.closest('tr')!
    expect(within(row).getByText('0.1000')).toBeInTheDocument()
    await user.clear(code)
    await user.type(code, '0008')
    expect(within(row).getByText('0.0800')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Validate' }))
    await waitFor(() => expect(api.validate).toHaveBeenCalled())
    let submitted = api.validate.mock.calls.at(-1)?.[0] as BladeSpec
    expect(submitted.airfoil_sections[index].airfoil).toEqual({ type: 'naca4', code: '0008' })
    expect(submitted.airfoil_sections[index].thickness_override_ratio).toBeNull()
    expect(submitted.airfoil_sections[index].trailing_edge_thickness_mm).toBe(originalTrailingEdge)
    expect(submitted.thickness_distribution.points.at(-1)?.thickness_ratio).toBeCloseTo(.08)

    const explicit = screen.getAllByRole('checkbox', { name: 'explicit' })[index]
    await user.click(explicit)
    const override = screen.getByLabelText(`Thickness override ${index + 1}`)
    fireEvent.change(override, { target: { value: '.10' } })
    fireEvent.blur(override)
    expect(within(row).getByText('0.1000')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Validate' }))
    submitted = api.validate.mock.calls.at(-1)?.[0] as BladeSpec
    expect(submitted.airfoil_sections[index].thickness_override_ratio).toBeCloseTo(.10)
    expect(submitted.thickness_distribution.points.at(-1)?.thickness_ratio).toBeCloseTo(.10)

    await user.click(explicit)
    expect(screen.queryByLabelText(`Thickness override ${index + 1}`)).not.toBeInTheDocument()
    expect(within(row).getByText('0.0800')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Validate' }))
    submitted = api.validate.mock.calls.at(-1)?.[0] as BladeSpec
    expect(Object.hasOwn(submitted.airfoil_sections[index], 'thickness_override_ratio')).toBe(false)
    expect(submitted.thickness_distribution.points.at(-1)?.thickness_ratio).toBeCloseTo(.08)
    expect(submitted.airfoil_sections[index].trailing_edge_thickness_mm).toBe(originalTrailingEdge)
  })
})
