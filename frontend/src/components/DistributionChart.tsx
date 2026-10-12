import { useEffect, useMemo, useRef, useState } from 'react'
import type { DistributionPreview } from '../types/bladespec'

export const CHART_WIDTH = 640
export const CHART_HEIGHT = 260
export const CHART_MARGIN = { left: 58, right: 18, top: 18, bottom: 42 } as const

export type SvgPoint = { x: number; y: number }
export type EditableControl = { radius: number; value: number; lockedReason?: string }
export type ChartInteraction = 'idle' | 'drafting' | 'validating'

export function clientPointToSvg(svg: SVGSVGElement, clientX: number, clientY: number): SvgPoint {
  const matrix = typeof svg.getScreenCTM === 'function' ? svg.getScreenCTM() : null
  if (matrix && typeof svg.createSVGPoint === 'function') {
    const point = svg.createSVGPoint()
    point.x = clientX
    point.y = clientY
    const transformed = point.matrixTransform(matrix.inverse())
    return { x: transformed.x, y: transformed.y }
  }
  const bounds = svg.getBoundingClientRect()
  const scale = Math.min(bounds.width / CHART_WIDTH, bounds.height / CHART_HEIGHT)
  const renderedWidth = CHART_WIDTH * scale
  const renderedHeight = CHART_HEIGHT * scale
  const left = bounds.left + (bounds.width - renderedWidth) / 2
  const top = bounds.top + (bounds.height - renderedHeight) / 2
  return { x: (clientX - left) / scale, y: (clientY - top) / scale }
}

export function svgXFromClient(svg: SVGSVGElement, clientX: number, clientY: number): number {
  return clientPointToSvg(svg, clientX, clientY).x
}

export function valueFromSvgY(svgY: number, minimum: number, maximum: number): number {
  const plotHeight = CHART_HEIGHT - CHART_MARGIN.top - CHART_MARGIN.bottom
  const fraction = (svgY - CHART_MARGIN.top) / plotHeight
  return maximum - fraction * (maximum - minimum)
}

export function nearestSampleIndex(samples: number[][], radius: number): number {
  let nearest = 0
  for (let index = 1; index < samples.length; index += 1) {
    if (Math.abs(samples[index][0] - radius) < Math.abs(samples[nearest][0] - radius)) nearest = index
  }
  return nearest
}

type Props = {
  title: string
  data?: DistributionPreview
  controls?: EditableControl[]
  unit?: string
  step?: number
  stale?: boolean
  onCommit?: (pointIndex: number, value: number) => Promise<boolean>
  onInteractionChange?: (state: ChartInteraction) => void
  onError?: (message: string) => void
}

export function DistributionChart({
  title,
  data,
  controls = [],
  unit = data?.unit ?? '',
  step = 1,
  stale = false,
  onCommit,
  onInteractionChange,
  onError,
}: Props) {
  const [hover, setHover] = useState<number>()
  const [draft, setDraft] = useState<{ index: number; value: number }>()
  const draftRef = useRef<{ index: number; value: number } | undefined>(undefined)
  const [validating, setValidating] = useState(false)
  const drag = useRef<{ pointerId: number; index: number; minimum: number; maximum: number } | undefined>(undefined)
  const mounted = useRef(true)
  useEffect(() => () => { mounted.current = false; onInteractionChange?.('idle') }, [onInteractionChange])
  const editableControls: EditableControl[] = controls.length ? controls : (data?.controls ?? []).map(([radius, value]) => ({ radius, value }))

  const chart = useMemo(() => {
    const points = [...(data?.samples ?? []), ...editableControls.map(control => [control.radius, control.value])]
    if (!points.length) return undefined
    const values = points.map(point => point[1])
    let minimum = Math.min(...values)
    let maximum = Math.max(...values)
    if (maximum - minimum < 1e-9) { minimum -= 1; maximum += 1 }
    const padding = (maximum - minimum) * .12
    minimum -= padding
    maximum += padding
    const radii = points.map(point => point[0])
    const x0 = Math.min(...radii)
    const x1 = Math.max(...radii)
    const plotWidth = CHART_WIDTH - CHART_MARGIN.left - CHART_MARGIN.right
    const x = (value: number) => CHART_MARGIN.left + (value - x0) / (x1 - x0) * plotWidth
    const y = (value: number) => CHART_MARGIN.top + (maximum - value) / (maximum - minimum) * (CHART_HEIGHT - CHART_MARGIN.top - CHART_MARGIN.bottom)
    return { minimum, maximum, x0, x1, x, y, plotWidth }
  }, [editableControls, data])

  const finish = async (index: number, value: number) => {
    draftRef.current = undefined
    setDraft(undefined)
    setValidating(true)
    onInteractionChange?.('validating')
    const accepted = await onCommit?.(index, value) ?? false
    if (!mounted.current) return
    setValidating(false)
    onInteractionChange?.('idle')
    if (!accepted) setDraft(undefined)
  }
  const cancel = (message = 'Curve edit cancelled') => {
    drag.current = undefined
    draftRef.current = undefined
    setDraft(undefined)
    setValidating(false)
    onInteractionChange?.('idle')
    onError?.(message)
  }
  useEffect(() => {
    if (!draft) return
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); cancel() }
    }
    window.addEventListener('keydown', keydown)
    return () => window.removeEventListener('keydown', keydown)
  }, [Boolean(draft)])

  if (!data || !chart) return <div className="chart-loading">Canonical preview loading…</div>
  const hovered = hover === undefined ? undefined : data.samples[hover]
  const readout = draft
    ? `Draft · r/R ${editableControls[draft.index].radius.toFixed(4)} · ${draft.value.toFixed(4)} ${unit}`
    : validating
      ? 'Validating full BladeSpec candidate…'
      : hovered
        ? `r/R ${hovered[0].toFixed(4)} · ${hovered[1].toFixed(4)} ${data.unit}`
        : 'Hover for canonical values · drag or use arrow keys on a marker'
  return (
    <div className={`distribution-chart ${stale ? 'canonical-stale' : ''}`}>
      <div className="section-title"><h3>{title}</h3><span>{data.interpolation.toUpperCase()} · {unit}{stale ? ' · previous committed curve' : ''}</span></div>
      <svg
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        preserveAspectRatio="xMidYMid meet"
        data-plot-left={CHART_MARGIN.left}
        data-plot-right={CHART_WIDTH - CHART_MARGIN.right}
        role="img"
        aria-label={`${title} canonical ${data.interpolation} distribution in ${unit}`}
        onMouseMove={event => {
          if (drag.current) return
          const svgX = svgXFromClient(event.currentTarget, event.clientX, event.clientY)
          const fraction = Math.max(0, Math.min(1, (svgX - CHART_MARGIN.left) / chart.plotWidth))
          setHover(nearestSampleIndex(data.samples, chart.x0 + fraction * (chart.x1 - chart.x0)))
        }}
        onPointerLeave={() => { if (!drag.current) setHover(undefined) }}
        onPointerMove={event => {
          if (drag.current && event.pointerId === drag.current.pointerId) {
            const value = valueFromSvgY(clientPointToSvg(event.currentTarget, event.clientX, event.clientY).y, drag.current.minimum, drag.current.maximum)
            draftRef.current = { index: drag.current.index, value }
            setDraft(draftRef.current)
            return
          }
          const svgX = svgXFromClient(event.currentTarget, event.clientX, event.clientY)
          const fraction = Math.max(0, Math.min(1, (svgX - CHART_MARGIN.left) / chart.plotWidth))
          setHover(nearestSampleIndex(data.samples, chart.x0 + fraction * (chart.x1 - chart.x0)))
        }}
        onPointerUp={event => {
          const pending = draftRef.current
          if (!drag.current || event.pointerId !== drag.current.pointerId || !pending) return
          try { event.currentTarget.releasePointerCapture?.(event.pointerId) } catch { /* capture may belong to the marker group */ }
          drag.current = undefined
          void finish(pending.index, pending.value)
        }}
        onPointerCancel={() => cancel()}
        onKeyDown={event => { if (event.key === 'Escape' && drag.current) cancel() }}
      >
        <line className="chart-axis" x1={CHART_MARGIN.left} y1={CHART_HEIGHT - CHART_MARGIN.bottom} x2={CHART_WIDTH - CHART_MARGIN.right} y2={CHART_HEIGHT - CHART_MARGIN.bottom} />
        <line className="chart-axis" x1={CHART_MARGIN.left} y1={CHART_MARGIN.top} x2={CHART_MARGIN.left} y2={CHART_HEIGHT - CHART_MARGIN.bottom} />
        <text x={CHART_MARGIN.left} y={CHART_HEIGHT - 14}>r/R {chart.x0.toFixed(2)}</text>
        <text textAnchor="end" x={CHART_WIDTH - CHART_MARGIN.right} y={CHART_HEIGHT - 14}>{chart.x1.toFixed(2)}</text>
        <text x="8" y={CHART_MARGIN.top + 8}>{chart.maximum.toFixed(3)}</text>
        <text x="8" y={CHART_HEIGHT - CHART_MARGIN.bottom}>{chart.minimum.toFixed(3)}</text>
        <polyline className="chart-line" data-values={JSON.stringify(data.samples)} points={data.samples.map(([radius, value]) => `${chart.x(radius)},${chart.y(value)}`).join(' ')} />
        {editableControls.map((control, index) => {
          const value = draft?.index === index ? draft.value : control.value
          const label = `${title} control ${index + 1}, r/R ${control.radius.toFixed(4)}, ${value.toFixed(4)} ${unit}${control.lockedReason ? `. ${control.lockedReason}` : ''}`
          return <g
            key={`${control.radius}-${index}`}
            className={`chart-marker ${control.lockedReason ? 'locked' : ''}`}
            onPointerDown={event => {
              if (validating) return
              if (control.lockedReason) { onError?.(control.lockedReason); return }
              event.preventDefault()
              drag.current = { pointerId: event.pointerId, index, minimum: chart.minimum, maximum: chart.maximum }
              draftRef.current = { index, value: control.value }
              setDraft(draftRef.current)
              onInteractionChange?.('drafting')
              onError?.('')
              try { event.currentTarget.setPointerCapture?.(event.pointerId) } catch { /* pointer flow still works inside the SVG */ }
            }}
          >
            <circle className="chart-hit-target" cx={chart.x(control.radius)} cy={chart.y(value)} r="14" />
            <circle
              className={`chart-control ${draft?.index === index ? 'draft' : ''}`}
              cx={chart.x(control.radius)} cy={chart.y(value)} r="5"
              role="slider" tabIndex={control.lockedReason ? -1 : 0}
              aria-label={label} aria-valuenow={value} aria-valuetext={`${value.toFixed(4)} ${unit}`}
              onKeyDown={event => {
                if (validating || !['ArrowUp', 'ArrowDown'].includes(event.key)) return
                event.preventDefault()
                const direction = event.key === 'ArrowUp' ? 1 : -1
                const value = control.value + direction * step * (event.shiftKey ? 10 : 1)
                void finish(index, value)
              }}
            />
            {control.lockedReason && <title>{control.lockedReason}</title>}
          </g>
        })}
        {hovered && !draft && <g className="chart-hover">
          <line x1={chart.x(hovered[0])} y1={CHART_MARGIN.top} x2={chart.x(hovered[0])} y2={CHART_HEIGHT - CHART_MARGIN.bottom} />
          <circle cx={chart.x(hovered[0])} cy={chart.y(hovered[1])} r="4" />
        </g>}
      </svg>
      <p className="chart-readout" aria-live="polite">{readout} · markers are user controls</p>
    </div>
  )
}
