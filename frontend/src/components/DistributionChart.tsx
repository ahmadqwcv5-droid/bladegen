import { useMemo, useState } from 'react'
import type { DistributionPreview } from '../types/bladespec'

const WIDTH = 640
const HEIGHT = 260
const MARGIN = { left: 58, right: 18, top: 18, bottom: 42 }

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
    const x = (value: number) => MARGIN.left + (value - x0) / (x1 - x0) * (WIDTH - MARGIN.left - MARGIN.right)
    const y = (value: number) => MARGIN.top + (maximum - value) / (maximum - minimum) * (HEIGHT - MARGIN.top - MARGIN.bottom)
    return { minimum, maximum, x0, x1, x, y }
  }, [data])
  if (!data || !chart) return <div className="chart-loading">Canonical preview loading…</div>
  const hovered = hover === undefined ? undefined : data.samples[hover]
  return (
    <div className="distribution-chart">
      <div className="section-title"><h3>{title}</h3><span>{data.interpolation.toUpperCase()} · {data.unit}</span></div>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={`${title} canonical ${data.interpolation} distribution in ${data.unit}`}
        onMouseLeave={() => setHover(undefined)}
        onMouseMove={event => {
          const bounds = event.currentTarget.getBoundingClientRect()
          const fraction = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width))
          const radius = chart.x0 + fraction * (chart.x1 - chart.x0)
          let nearest = 0
          for (let index = 1; index < data.samples.length; index += 1) {
            if (Math.abs(data.samples[index][0] - radius) < Math.abs(data.samples[nearest][0] - radius)) nearest = index
          }
          setHover(nearest)
        }}
      >
        <line className="chart-axis" x1={MARGIN.left} y1={HEIGHT - MARGIN.bottom} x2={WIDTH - MARGIN.right} y2={HEIGHT - MARGIN.bottom} />
        <line className="chart-axis" x1={MARGIN.left} y1={MARGIN.top} x2={MARGIN.left} y2={HEIGHT - MARGIN.bottom} />
        <text x={MARGIN.left} y={HEIGHT - 14}>r/R {chart.x0.toFixed(2)}</text>
        <text textAnchor="end" x={WIDTH - MARGIN.right} y={HEIGHT - 14}>{chart.x1.toFixed(2)}</text>
        <text x="8" y={MARGIN.top + 8}>{chart.maximum.toFixed(3)}</text>
        <text x="8" y={HEIGHT - MARGIN.bottom}>{chart.minimum.toFixed(3)}</text>
        <polyline className="chart-line" data-values={JSON.stringify(data.samples)} points={data.samples.map(([radius, value]) => `${chart.x(radius)},${chart.y(value)}`).join(' ')} />
        {data.controls.map(([radius, value], index) => <circle key={`${radius}-${index}`} className="chart-control" cx={chart.x(radius)} cy={chart.y(value)} r="5" />)}
        {hovered && <g className="chart-hover">
          <line x1={chart.x(hovered[0])} y1={MARGIN.top} x2={chart.x(hovered[0])} y2={HEIGHT - MARGIN.bottom} />
          <circle cx={chart.x(hovered[0])} cy={chart.y(hovered[1])} r="4" />
        </g>}
      </svg>
      <p className="chart-readout">{hovered ? `r/R ${hovered[0].toFixed(4)} · ${hovered[1].toFixed(4)} ${data.unit}` : 'Hover for canonical interpolated values'} · markers are user controls</p>
    </div>
  )
}
