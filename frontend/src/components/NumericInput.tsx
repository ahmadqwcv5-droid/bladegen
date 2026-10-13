import { useEffect, useRef, useState } from 'react'

type Props = {
  value: number
  onCommit: (value: number) => void | Promise<boolean | void>
  label: string
  step?: string
  disabled?: boolean
  formatValue?: (value: number) => string
}

const defaultFormat = (value: number) => String(value)

export function NumericInput({ value, onCommit, label, step = 'any', disabled = false, formatValue = defaultFormat }: Props) {
  const formatted = formatValue(value)
  const [draft, setDraft] = useState(formatted)
  const [error, setError] = useState('')
  const edited = useRef(false)

  useEffect(() => {
    setDraft(formatted)
    edited.current = false
  }, [value, formatted])

  const commit = async () => {
    const parsed = Number(draft)
    if (draft.trim() === '' || !Number.isFinite(parsed)) {
      setError(`${label} must be a finite number`)
      return
    }
    // No typing, the same number, and an equivalent rendering (for example
    // 60.0 versus 60) preserve the exact source value and skip engineering work.
    if (!edited.current || Object.is(parsed, value) || Object.is(parsed, Number(formatted))) {
      setDraft(formatted)
      setError('')
      edited.current = false
      return
    }
    try {
      const accepted = await onCommit(parsed)
      if (accepted === false) setDraft(formatted)
      setError('')
    } catch (caught) {
      setDraft(formatted)
      setError(caught instanceof Error ? caught.message : String(caught))
    } finally {
      edited.current = false
    }
  }

  return <span className="numeric"><input
    aria-label={label}
    type="number"
    step={step}
    value={draft}
    disabled={disabled}
    onChange={event => { edited.current = true; setDraft(event.target.value) }}
    onFocus={() => { if (!edited.current) setDraft(String(value)) }}
    onBlur={() => { void commit() }}
  />{error && <small className="field-error">{error}</small>}</span>
}
