import { useMemo, useState } from 'react'
import type { DistributionPreview } from '../types/bladespec'

export const CHART_WIDTH = 640
export const CHART_HEIGHT = 260
export const CHART_MARGIN = { left: 58, right: 18, top: 18, bottom: 42 } as const

export function svgXFromClient(svg: SVGSVGElement, clientX: number, clientY: number): number {
  const matrix = typeof svg.getScreenCTM === 'function' ? svg.getScreenCTM() : null
  if (matrix && typeof svg.createSVGPoint === 'function') {
    const point = svg.createSVGPoint()
    point.x = clientX
    point.y = clientY
    return point.matrixTransform(matrix.inverse()).x
  }
  const bounds = svg.getBoundingClientRect()
  const scale = Math.min(bounds.width / CHART_WIDTH, bounds.height / CHART_HEIGHT)
  const renderedWidth = CHART_WIDTH * scale
  const contentLeft = bounds.left + (bounds.width - renderedWidth) / 2
  return (clientX - contentLeft) / scale
}

export function nearestSampleIndex(samples: number[][], radius: number): number {
  let nearest = 0
  for (let index = 1; index < samples.length; index += 1) {
    if (Math.abs(samples[index][0] - radius) < Math.abs(samples[nearest][0] - radius)) {
      nearest = index
    }
  }
  return nearest
}

export function DistributionChart({ title, data }: { title: string; data?: DistributionPreview }) {
  const [hover, setHover] = useState<number>()
  const chart = useMemo(() => {
    if (!data?.samples.length) return undefined
    const values = data.samples.map(point => point[1])
    let minimum = Math.min(...values)
    let maximum = Math.max(...values)
    if (maximum - minimum < 1e-9) { minimum -= 1; maximum += 1 }
    const padding = (maximum - minimum) * .1
    minimum -= padding
    maximum += padding
    const x0 = data.samples[0][0]
    const x1 = data.samples.at(-1)![0]
    const plotWidth = CHART_WIDTH - CHART_MARGIN.left - CHART_MARGIN.right
    const x = (value: number) => CHART_MARGIN.left + (value - x0) / (x1 - x0) * plotWidth
    const y = (value: number) => CHART_MARGIN.top + (maximum - value) / (maximum - minimum) * (CHART_HEIGHT - CHART_MARGIN.top - CHART_MARGIN.bottom)
    return { minimum, maximum, x0, x1, x, y, plotWidth }
  }, [data])
  if (!data || !chart) return <div className="chart-loading">Canonical preview loading…</div>
  const hovered = hover === undefined ? undefined : data.samples[hover]
  return (
    <div className="distribution-chart">
      <div className="section-title"><h3>{title}</h3><span>{data.interpolation.toUpperCase()} · {data.unit}</span></div>
      <svg
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        preserveAspectRatio="xMidYMid meet"
        data-plot-left={CHART_MARGIN.left}
        data-plot-right={CHART_WIDTH - CHART_MARGIN.right}
        role="img"
        aria-label={`${title} canonical ${data.interpolation} distribution in ${data.unit}`}
        onMouseLeave={() => setHover(undefined)}
        onMouseMove={event => {
          const svgX = svgXFromClient(event.currentTarget, event.clientX, event.clientY)
          const fraction = Math.max(0, Math.min(1, (svgX - CHART_MARGIN.left) / chart.plotWidth))
          const radius = chart.x0 + fraction * (chart.x1 - chart.x0)
          setHover(nearestSampleIndex(data.samples, radius))
        }}
      >
        <line className="chart-axis" x1={CHART_MARGIN.left} y1={CHART_HEIGHT - CHART_MARGIN.bottom} x2={CHART_WIDTH - CHART_MARGIN.right} y2={CHART_HEIGHT - CHART_MARGIN.bottom} />
        <line className="chart-axis" x1={CHART_MARGIN.left} y1={CHART_MARGIN.top} x2={CHART_MARGIN.left} y2={CHART_HEIGHT - CHART_MARGIN.bottom} />
        <text x={CHART_MARGIN.left} y={CHART_HEIGHT - 14}>r/R {chart.x0.toFixed(2)}</text>
        <text textAnchor="end" x={CHART_WIDTH - CHART_MARGIN.right} y={CHART_HEIGHT - 14}>{chart.x1.toFixed(2)}</text>
        <text x="8" y={CHART_MARGIN.top + 8}>{chart.maximum.toFixed(3)}</text>
        <text x="8" y={CHART_HEIGHT - CHART_MARGIN.bottom}>{chart.minimum.toFixed(3)}</text>
        <polyline className="chart-line" data-values={JSON.stringify(data.samples)} points={data.samples.map(([radius, value]) => `${chart.x(radius)},${chart.y(value)}`).join(' ')} />
        {data.controls.map(([radius, value], index) => <circle key={`${radius}-${index}`} className="chart-control" cx={chart.x(radius)} cy={chart.y(value)} r="5" />)}
        {hovered && <g className="chart-hover">
          <line x1={chart.x(hovered[0])} y1={CHART_MARGIN.top} x2={chart.x(hovered[0])} y2={CHART_HEIGHT - CHART_MARGIN.bottom} />
          <circle cx={chart.x(hovered[0])} cy={chart.y(hovered[1])} r="4" />
        </g>}
      </svg>
      <p className="chart-readout" aria-live="polite">{hovered ? `r/R ${hovered[0].toFixed(4)} · ${hovered[1].toFixed(4)} ${data.unit}` : 'Hover for canonical interpolated values'} · markers are user controls</p>
    </div>
  )
}
