import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { NumericInput } from './NumericInput'

afterEach(cleanup)

describe('NumericInput no-op identity', () => {
  it('skips focus/blur, equivalent text, and clear/restore no-ops', async () => {
    const commit = vi.fn()
    render(<NumericInput label="Engineering value" value={60} onCommit={commit} />)
    const input = screen.getByLabelText('Engineering value')
    fireEvent.focus(input); fireEvent.blur(input)
    fireEvent.change(input, { target: { value: '60.0' } }); fireEvent.blur(input)
    fireEvent.change(input, { target: { value: '' } })
    fireEvent.change(input, { target: { value: '60' } }); fireEvent.blur(input)
    await new Promise(resolve => setTimeout(resolve, 0))
    expect(commit).not.toHaveBeenCalled()
    expect(input).toHaveValue(60)
  })

  it('preserves a precise source behind formatted text but commits a real precise edit', async () => {
    const commit = vi.fn(async () => true)
    render(<NumericInput label="Precise value" value={64.00000198364258} formatValue={value => value.toFixed(3).replace(/0+$/, '').replace(/\.$/, '')} onCommit={commit} />)
    const input = screen.getByLabelText('Precise value')
    expect(input).toHaveValue(64)
    fireEvent.focus(input)
    expect(input).toHaveValue(64.00000198364258)
    fireEvent.blur(input)
    expect(input).toHaveValue(64)
    fireEvent.change(input, { target: { value: '64.000' } }); fireEvent.blur(input)
    expect(commit).not.toHaveBeenCalled()
    fireEvent.change(input, { target: { value: '64.0002' } }); fireEvent.blur(input)
    await waitFor(() => expect(commit).toHaveBeenCalledWith(64.0002))
  })
})
