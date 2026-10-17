import { createHash } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { isDeepStrictEqual } from 'node:util'
import { expect, test, type Browser, type Page } from '@playwright/test'
import { submitBuild, waitForExactResult } from './jobIdentity'

const repositoryRoot = path.resolve('..')
const q01Path = path.join(repositoryRoot, 'qualification/fp02/cases/Q01.json')
const q06Path = path.join(repositoryRoot, 'qualification/fp02/cases/Q06.json')
const runId = process.env.FP02_EVIDENCE_RUN_ID ?? 'unlabelled-local-run'
const evidenceBase = process.env.FP02_EVIDENCE_ROOT
  ? path.resolve(process.env.FP02_EVIDENCE_ROOT)
  : path.join(repositoryRoot, 'qualification/fp02/evidence/browser', runId)
const evidenceRoot = path.join(evidenceBase, 'U1')

const distributionCsv = [
  'r_over_R,chord_over_R,twist_deg,rake_over_R,skew_over_R,thickness_ratio',
  '0.25,0.32,30,0,0,0.12',
  '0.625,0.23,18,0,0,0.12',
  '1,0.12,7,0,0,0.12',
].join('\n')

type JobStatus = Record<string, unknown> & {
  job_id: string
  status: string
  elapsed_seconds: number
  queue_wait_seconds: number
  worker_elapsed_seconds: number
}

const sha256 = (value: Buffer | string) => createHash('sha256').update(value).digest('hex')

async function currentSpec(page: Page): Promise<Record<string, unknown>> {
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export JSON' }).click()
  const download = await downloadPromise
  const downloadPath = await download.path()
  expect(downloadPath).not.toBeNull()
  return JSON.parse(await readFile(downloadPath!, 'utf8')) as Record<string, unknown>
}

function normalizedForComparison(value: Record<string, unknown>): Record<string, unknown> {
  const copy = structuredClone(value) as Record<string, unknown>
  const sections = copy.airfoil_sections as Array<Record<string, unknown>> | undefined
  for (const section of sections ?? []) {
    if (!Object.hasOwn(section, 'thickness_override_ratio')) section.thickness_override_ratio = null
  }
  return copy
}

async function setNumeric(page: Page, label: string, value: string) {
  const input = page.getByLabel(label, { exact: true })
  await input.fill(value)
  await input.blur()
}

async function waitForPreview(page: Page) {
  await expect(page.getByText(/Canonical design preview is current/)).toBeVisible({ timeout: 30_000 })
}

async function artifactMap(page: Page, jobId: string) {
  const response = await page.request.get(`/api/jobs/${jobId}/artifacts`)
  expect(response.ok()).toBe(true)
  const values = await response.json() as Array<{ name: string, size_bytes: number, download_url: string }>
  return new Map(values.map(value => [value.name, value]))
}

async function jsonArtifact(page: Page, jobId: string, name: string) {
  const response = await page.request.get(`/api/jobs/${jobId}/artifacts/${name}`)
  expect(response.ok()).toBe(true)
  return response.json() as Promise<Record<string, any>>
}

async function buildWithTiming(
  page: Page,
  button: 'Generate Blade' | 'Generate Propeller',
  endpoint: '/api/build' | '/api/propellers/build',
) {
  const started = performance.now()
  const jobId = await submitBuild(page, button, endpoint)
  const status = await waitForExactResult(page, jobId, 960_000) as JobStatus
  return { jobId, status, click_to_terminal_ms: performance.now() - started }
}

async function openInNewContext(browser: Browser, filename: string) {
  const context = await browser.newContext()
  const page = await context.newPage()
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Airfoil Stations (5)' })).toBeVisible({ timeout: 30_000 })
  await page.locator('input[type="file"][accept*="json"]').setInputFiles(filename)
  await expect(page.getByText(/Opened and validated/)).toBeVisible({ timeout: 30_000 })
  await waitForPreview(page)
  return { context, page }
}

test('FP02 U1 visibly authors Q01, saves/opens, edits/regenerates, and builds Q06', async ({ page, browser }) => {
  test.setTimeout(3_000_000)
  await mkdir(evidenceRoot, { recursive: true })
  const expectedQ01 = JSON.parse(await readFile(q01Path, 'utf8')) as Record<string, unknown>
  await page.setViewportSize({ width: 1440, height: 1000 })
  let bladeBuildRequests = 0
  let propellerBuildRequests = 0
  page.on('request', request => {
    if (request.method() !== 'POST') return
    if (request.url().endsWith('/api/build')) bladeBuildRequests += 1
    if (request.url().endsWith('/api/propellers/build')) propellerBuildRequests += 1
  })

  await page.goto('/')
  await expect(page.getByText('Airfoil Stations (5)')).toBeVisible({ timeout: 30_000 })
  page.once('dialog', dialog => dialog.accept())
  await page.getByRole('button', { name: 'New', exact: true }).click()
  await page.getByLabel('Name', { exact: true }).fill('FP02_Q01_simple_three_station')
  await setNumeric(page, 'Diameter', '400')
  await setNumeric(page, 'Root radius', '0.25')
  await setNumeric(page, 'Reference axis', '0.25')
  await page.locator('label').filter({ hasText: /^Rotation/ }).locator('select').selectOption('normal')

  await page.getByRole('button', { name: 'Set Up Airfoil Stations' }).click()
  const setup = page.getByRole('dialog', { name: 'Set Up Airfoil Stations' })
  await setup.getByLabel('Total airfoil stations').fill('3')
  await setup.getByLabel('Common station trailing edge').fill('0')
  await setup.getByRole('button', { name: 'Apply Once' }).click()
  await expect(page.getByText('Airfoil Stations (3)')).toBeVisible()

  for (let index = 1; index <= 3; index += 1) {
    await page.getByLabel(`Select airfoil station ${index}`).check()
  }
  await page.getByRole('button', { name: 'Apply Profile to Selected Stations' }).click()
  const selector = page.getByRole('dialog', { name: 'Airfoil Library for 3 selected stations' })
  await selector.getByRole('button', { name: /NACA 0012/ }).click()
  await selector.getByLabel('Use constant thickness for selected common profile').check()
  await selector.getByRole('button', { name: 'Apply to 3 Selected Stations' }).click()

  await page.getByRole('button', { name: 'Import Distributions' }).click()
  const distribution = page.getByRole('dialog', { name: 'Import Distributions' })
  await distribution.getByLabel('Distribution CSV file').setInputFiles({
    name: 'FP02_Q01_distributions.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(distributionCsv),
  })
  await expect(distribution.getByText('3 rows', { exact: true })).toBeVisible()
  for (const curve of ['Chord', 'Twist', 'Rake', 'Skew', 'Thickness']) {
    await distribution.getByLabel(`${curve} import interpolation`).selectOption('linear')
  }
  await distribution.getByRole('button', { name: 'Apply Once' }).click()
  await waitForPreview(page)
  expect(bladeBuildRequests).toBe(0)
  expect(propellerBuildRequests).toBe(0)

  const authored = normalizedForComparison(await currentSpec(page))
  expect(isDeepStrictEqual(authored, normalizedForComparison(expectedQ01))).toBe(true)
  const first = await buildWithTiming(page, 'Generate Blade', '/api/build')
  expect(bladeBuildRequests).toBe(1)
  const firstArtifacts = await artifactMap(page, first.jobId)
  for (const name of ['blade_solid.step', 'blade_spec.json', 'validation.json', 'engine_manifest.json']) {
    expect(firstArtifacts.get(name)?.download_url).toBe(`/api/jobs/${first.jobId}/artifacts/${name}`)
    await expect(page.getByRole('link', { name, exact: true })).toHaveAttribute(
      'href', `/api/jobs/${first.jobId}/artifacts/${name}`,
    )
  }
  const firstValidation = await jsonArtifact(page, first.jobId, 'validation.json')
  expect(firstValidation.status).toBe('PASS')
  expect(firstValidation.geometry_validation.station_count).toBe(5)

  const savedDownloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export JSON' }).click()
  const savedDownload = await savedDownloadPromise
  const savedPath = await savedDownload.path()
  expect(savedPath).not.toBeNull()
  const reopened = await openInNewContext(browser, savedPath!)
  const reopenedSpec = normalizedForComparison(await currentSpec(reopened.page))
  expect(isDeepStrictEqual(reopenedSpec, normalizedForComparison(expectedQ01))).toBe(true)

  await reopened.context.close()

  await page.getByLabel('Twist value 2', { exact: true }).fill('21')
  await page.getByLabel('Twist value 2', { exact: true }).blur()
  await waitForPreview(page)
  await expect(page.getByText(/Inputs changed — regenerate/)).toBeVisible()
  await expect(page.getByText(/Last successful build — previous inputs/)).toBeVisible()
  const requestsBeforeRegeneration = bladeBuildRequests
  const second = await buildWithTiming(page, 'Generate Blade', '/api/build')
  expect(second.jobId).not.toBe(first.jobId)
  expect(bladeBuildRequests).toBe(requestsBeforeRegeneration + 1)
  const secondValidation = await jsonArtifact(page, second.jobId, 'validation.json')
  const firstInterior = firstValidation.geometry_validation.stations.find(
    (station: Record<string, number>) => station.requested_r_over_R === 0.625,
  )
  const secondInterior = secondValidation.geometry_validation.stations.find(
    (station: Record<string, number>) => station.requested_r_over_R === 0.625,
  )
  expect(firstInterior.actual_twist_deg).toBeCloseTo(18, 1)
  expect(secondInterior.actual_twist_deg).toBeCloseTo(21, 1)
  expect(secondInterior.twist_pass).toBe(true)
  expect(secondInterior.actual_twist_deg - firstInterior.actual_twist_deg).toBeCloseTo(3, 1)
  await page.locator('input[type="file"][accept*="json"]').setInputFiles(q06Path)
  await expect(page.getByText(/Opened and validated Q06.json/)).toBeVisible({ timeout: 30_000 })
  await expect(page.getByRole('button', { name: 'Full Propeller' })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByLabel('Number of Blades')).toHaveValue('2')
  const propeller = await buildWithTiming(page, 'Generate Propeller', '/api/propellers/build')
  expect(propellerBuildRequests).toBe(1)
  const propellerValidation = await jsonArtifact(page, propeller.jobId, 'validation.json')
  expect(propellerValidation.status).toBe('PASS')
  expect(propellerValidation.assembly_validation).toMatchObject({
    requested_blade_count: 2,
    actual_blade_placement_count: 2,
    passed: true,
  })
  expect(propellerValidation.assembly_validation.final_after_reimport).toMatchObject({
    solids: 1, shells: 1, free_edges: 0, closed_shell: true, brepcheck_valid: true,
  })

  const summary = {
    schema: 'bladegen.fp02.u1-evidence.v1',
    evidence_run_id: runId,
    input_method: 'visible controls, ordinary file input, and explicit Generate actions',
    injected_application_state: false,
    q01_definition_sha256: sha256(await readFile(q01Path)),
    save_open_definition_equivalent: true,
    edit: { r_over_R: 0.625, before_twist_deg: 18, after_twist_deg: 21 },
    jobs: {
      q01_initial: first,
      q01_twist_edit: second,
      q06_propeller: propeller,
    },
    measured_twist: {
      initial_actual_deg: firstInterior.actual_twist_deg,
      edited_actual_deg: secondInterior.actual_twist_deg,
      delta_deg: secondInterior.actual_twist_deg - firstInterior.actual_twist_deg,
    },
  }
  await writeFile(path.join(evidenceRoot, 'summary.json'), `${JSON.stringify(summary, null, 2)}\n`)
})
