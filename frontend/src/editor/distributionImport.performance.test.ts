import { describe, expect, it } from 'vitest'
import example from '../../../examples/custom_multi_airfoil_finite_te.json'
import type { BladeSpec } from '../types/bladespec'
import {
  buildDistributionCandidate,
  parseDelimitedTable,
  suggestedImportPlan,
} from './distributionImport'

const percentile = (values: number[], fraction: number) => {
  const sorted = [...values].sort((left, right) => left - right)
  const position = (sorted.length - 1) * fraction
  const lower = Math.floor(position)
  const upper = Math.ceil(position)
  return sorted[lower] + (sorted[upper] - sorted[lower]) * (position - lower)
}

const input = (count: number) => {
  const rows = Array.from({ length: count }, (_, index) => {
    const fraction = index / (count - 1)
    const radius = .2 + .8 * fraction
    return [index + 1, radius, 80 - 50 * fraction, 30 - 25 * fraction, -2.5 + 4.25 * fraction, -1.25 + 3.75 * fraction].join('\t')
  })
  return `row\tr_over_R\tchord_mm\ttwist_deg\trake_mm\tskew_mm\n${rows.join('\n')}`
}

describe('Sprint 04B browser-side import performance', () => {
  it.each([40, 200])('parses and builds a %i-row review candidate over 20 repetitions', count => {
    const spec = structuredClone(example) as BladeSpec
    const source = input(count)
    const operation = () => {
      const table = parseDelimitedTable(source, `synthetic-${count}.tsv`)
      const plan = suggestedImportPlan(table, spec)
      buildDistributionCandidate(spec, table, plan)
    }
    const coldStarted = performance.now()
    operation()
    const cold = performance.now() - coldStarted
    const samples = Array.from({ length: 20 }, () => {
      const started = performance.now()
      operation()
      return performance.now() - started
    })
    const result = {
      rows: count,
      cold_first_ms: cold,
      warm_repetitions: 20,
      warm_median_ms: percentile(samples, .5),
      warm_p95_ms: percentile(samples, .95),
      warm_max_ms: Math.max(...samples),
    }
    console.info(`SPRINT04B_IMPORT_PERF ${JSON.stringify(result)}`)
    expect(result.warm_p95_ms).toBeLessThan(count === 40 ? 500 : 2000)
  })
})
