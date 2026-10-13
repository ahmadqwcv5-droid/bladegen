import { expect, test, type BrowserContext, type Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import path from 'node:path'

const evidenceRoot = path.resolve('../docs/screenshots/patch04a2')
const evidence = (name: string) => path.join(evidenceRoot, name)

type Artifact = { name: string; size_bytes: number; download_url: string }
type ExpectedAssembly = {
  name: string
  bladeName: string
  bladeCount: number
  hubDiameter: number
  hubLength: number
  boreDiameter: number
  initialAzimuth: number
}

async function setNumber(page: Page, label: string, value: number) {
  const input = page.getByLabel(label)
  await input.fill(String(value))
  await input.blur()
  await expect(input).toHaveValue(String(value))
}

async function waitForExactJob(page: Page, jobId: string) {
  const deadline = Date.now() + 360_000
  let last: Record<string, unknown> | undefined
  while (Date.now() < deadline) {
    const response = await page.request.get(`/api/jobs/${jobId}`)
    expect(response.ok()).toBe(true)
    last = await response.json()
    if (last.status === 'failed') {
      throw new Error(`Job ${jobId} failed at ${String(last.stage)}: ${String(last.error ?? last.message)}`)
    }
    if (last.status === 'succeeded') return last
    await page.waitForTimeout(500)
  }
  throw new Error(`Timed out waiting for exact job ${jobId}; last status: ${JSON.stringify(last)}`)
}

async function submitAndVerifyExactJob(page: Page, expected: ExpectedAssembly) {
  const acceptedResponse = page.waitForResponse(response => (
    response.request().method() === 'POST'
    && response.url().endsWith('/api/propellers/build')
  ))
  await page.getByRole('button', { name: 'Generate Propeller' }).click()
  const response = await acceptedResponse
  expect(response.status()).toBe(202)
  const accepted = await response.json()
  expect(accepted.status).toBe('queued')
  expect(accepted.job_id).toMatch(/^[0-9a-f]{32}$/)
  const jobId = accepted.job_id as string

  await waitForExactJob(page, jobId)
  await expect(page.locator(`[data-result-job-id="${jobId}"]`)).toBeVisible({ timeout: 30_000 })

  const artifactsResponse = await page.request.get(`/api/jobs/${jobId}/artifacts`)
  expect(artifactsResponse.ok()).toBe(true)
  const artifacts = await artifactsResponse.json() as Artifact[]
  const byName = new Map(artifacts.map(artifact => [artifact.name, artifact]))
  for (const name of ['propeller_solid.step', 'propeller_spec.json', 'validation.json']) {
    const artifact = byName.get(name)
    expect(artifact, `${name} for ${jobId}`).toBeDefined()
    expect(artifact!.download_url).toBe(`/api/jobs/${jobId}/artifacts/${name}`)
    await expect(page.getByRole('link', { name, exact: true })).toHaveAttribute(
      'href',
      artifact!.download_url,
    )
  }

  const specResponse = await page.request.get(byName.get('propeller_spec.json')!.download_url)
  const validationResponse = await page.request.get(byName.get('validation.json')!.download_url)
  expect(specResponse.ok()).toBe(true)
  expect(validationResponse.ok()).toBe(true)
  const builtSpec = await specResponse.json()
  const validation = await validationResponse.json()
  expect(builtSpec.name).toBe(expected.name)
  expect(builtSpec.blade_spec.name).toBe(expected.bladeName)
  expect(builtSpec.assembly).toEqual({
    blade_count: expected.bladeCount,
    hub_diameter_mm: expected.hubDiameter,
    hub_length_mm: expected.hubLength,
    shaft_bore_diameter_mm: expected.boreDiameter,
    initial_azimuth_deg: expected.initialAzimuth,
  })
  expect(validation.status).toBe('PASS')
  expect(validation.assembly_validation.passed).toBe(true)
  expect(validation.assembly_validation.actual_blade_placement_count).toBe(expected.bladeCount)
  expect(validation.assembly_validation.hub_diameter_mm).toBe(expected.hubDiameter)
  expect(validation.assembly_validation.hub_length_mm).toBe(expected.hubLength)
  expect(validation.assembly_validation.shaft_bore_diameter_mm).toBe(expected.boreDiameter)
  return { jobId, builtSpec, validation, artifacts }
}

function watchBuildRequests(context: BrowserContext, requests: string[]) {
  context.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/api/propellers/build')) {
      requests.push(request.url())
    }
  })
}

async function verifyImportedBlade(page: Page, blade: Record<string, any>) {
  await expect(page.getByLabel('Name', { exact: true })).toHaveValue(blade.name)
  await expect(page.getByLabel('Diameter', { exact: true })).toHaveValue(String(blade.diameter_mm))
  await expect(page.getByLabel('Root radius')).toHaveValue(String(blade.root_radius_ratio))
  const sections = blade.airfoil_sections as Array<Record<string, any>>
  await expect(page.getByText(`Airfoil Stations (${sections.length})`)).toBeVisible()
  for (const [index, section] of sections.entries()) {
    await expect(page.getByLabel(`Airfoil radius ${index + 1}`)).toHaveValue(String(section.r_over_R))
    if (section.airfoil.type === 'naca4') {
      await expect(page.getByLabel(`NACA code ${index + 1}`)).toHaveValue(section.airfoil.code)
    } else {
      const coordinateProfiles = page.locator('details').filter({ hasText: 'Embedded coordinates' })
      const coordinateIndex = sections.slice(0, index).filter(row => row.airfoil.type === 'coordinates').length
      await expect(coordinateProfiles.nth(coordinateIndex).locator('pre')).toContainText(
        JSON.stringify(section.airfoil.upper[0]),
      )
    }
  }

  const definitions = [
    ['Chord', 'chord_distribution', 'chord_over_R', (value: number) => value * blade.diameter_mm / 2],
    ['Twist', 'twist_distribution', 'twist_deg', (value: number) => value],
    ['Rake', 'rake_distribution', 'rake_over_R', (value: number) => value * blade.diameter_mm / 2],
    ['Skew', 'skew_distribution', 'skew_over_R', (value: number) => value * blade.diameter_mm / 2],
    ['Thickness', 'thickness_distribution', 'thickness_ratio', (value: number) => value * 100],
  ] as const
  for (const [title, key, valueKey, display] of definitions) {
    const distribution = blade[key]
    await expect(page.getByLabel(`${title} interpolation`)).toHaveValue(distribution.interpolation)
    await expect(page.getByRole('heading', { name: `${title} (${distribution.points.length})` })).toBeVisible()
    for (const [index, point] of distribution.points.entries()) {
      expect(Number(await page.getByLabel(`${title} radius ${index + 1}`).inputValue())).toBeCloseTo(point.r_over_R, 10)
      expect(Number(await page.getByLabel(`${title} value ${index + 1}`).inputValue())).toBeCloseTo(display(point[valueKey]), 8)
    }
  }
}

test('90×30 project verifies exact jobs A/B/C and rebuilds in an isolated browser context', async ({ page, context, browser }) => {
  test.setTimeout(900_000)
  await page.setViewportSize({ width: 1440, height: 1000 })
  const buildRequests: string[] = []
  watchBuildRequests(context, buildRequests)

  await page.goto('/')
  await expect(page.getByText('Airfoil Stations (5)')).toBeVisible({ timeout: 30_000 })
  await page.getByRole('button', { name: 'Load Example' }).click()
  await page.getByRole('button', { name: 'Full Propeller' }).click()
  await page.getByLabel('Propeller Name').fill('two_blade_propeller_hub_90x30')
  await page.getByLabel('Number of Blades').selectOption('2')
  await setNumber(page, 'Hub Diameter', 90)
  await setNumber(page, 'Hub Length', 30)
  await setNumber(page, 'Shaft Bore Diameter', 12)
  await setNumber(page, 'Initial Azimuth', 0)
  const expected = {
    name: 'two_blade_propeller_hub_90x30',
    bladeName: 'custom_blade_multi_airfoil',
    bladeCount: 2,
    hubDiameter: 90,
    hubLength: 30,
    boreDiameter: 12,
    initialAzimuth: 0,
  }

  const resultA = await submitAndVerifyExactJob(page, expected)
  expect(buildRequests).toHaveLength(1)
  await page.screenshot({ path: evidence('assembly_a_90x30_success.png'), fullPage: true })

  await setNumber(page, 'Hub Diameter', 60)
  await expect(page.getByText('Hub diameter is too small for the current blade root.')).toBeVisible()
  await expect(page.getByText('greater than 80 mm')).toBeVisible()
  await page.getByRole('button', { name: 'Generate Propeller' }).click()
  await expect(page.getByText('Current inputs are invalid. No new CAD build was started.', { exact: true })).toBeVisible()
  await expect(page.locator(`[data-result-job-id="${resultA.jobId}"]`)).toBeVisible()
  expect(buildRequests).toHaveLength(1)
  await page.screenshot({ path: evidence('invalid_60x30_historical_result.png'), fullPage: true })

  await setNumber(page, 'Hub Diameter', 90)
  const resultB = await submitAndVerifyExactJob(page, expected)
  expect(resultB.jobId).not.toBe(resultA.jobId)
  expect(buildRequests).toHaveLength(2)
  await page.screenshot({ path: evidence('assembly_b_90x30_success.png'), fullPage: true })

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Export JSON' }).click(),
  ])
  const downloadPath = await download.path()
  expect(downloadPath).not.toBeNull()
  const exported = JSON.parse(await readFile(downloadPath!, 'utf8'))
  expect(exported).toEqual(resultB.builtSpec)

  const freshContext = await browser.newContext()
  watchBuildRequests(freshContext, buildRequests)
  try {
    const fresh = await freshContext.newPage()
    await fresh.goto('http://127.0.0.1:5174/')
    await expect(fresh.getByText('Airfoil Stations (5)')).toBeVisible({ timeout: 30_000 })
    await fresh.locator('input[type="file"]').setInputFiles(downloadPath!)
    await expect(fresh.getByRole('button', { name: 'Full Propeller' })).toHaveAttribute('aria-pressed', 'true')
    await expect(fresh.getByLabel('Propeller Name')).toHaveValue(expected.name)
    await expect(fresh.getByLabel('Number of Blades')).toHaveValue('2')
    await expect(fresh.getByLabel('Hub Diameter')).toHaveValue('90')
    await expect(fresh.getByLabel('Hub Length')).toHaveValue('30')
    await expect(fresh.getByLabel('Shaft Bore Diameter')).toHaveValue('12')
    await expect(fresh.getByLabel('Initial Azimuth')).toHaveValue('0')
    await verifyImportedBlade(fresh, exported.blade_spec)
    expect(buildRequests).toHaveLength(2)

    const resultC = await submitAndVerifyExactJob(fresh, expected)
    expect(resultC.jobId).not.toBe(resultA.jobId)
    expect(resultC.jobId).not.toBe(resultB.jobId)
    expect(buildRequests).toHaveLength(3)
    await fresh.screenshot({ path: evidence('isolated_session_import_rebuild.png'), fullPage: true })
  } finally {
    await freshContext.close()
  }
})

test('semantic-invalid propeller is rejected by API and atomic import without a CAD job', async ({ page, context }) => {
  const buildRequests: string[] = []
  watchBuildRequests(context, buildRequests)
  const bladeResponse = await page.request.get('/api/examples/custom_multi_airfoil_finite_te')
  expect(bladeResponse.ok()).toBe(true)
  const blade = await bladeResponse.json()
  blade.airfoil_sections[1].airfoil = { type: 'naca4', code: '4412' }
  delete blade.airfoil_sections[1].thickness_override_ratio
  blade.thickness_distribution.points[1].thickness_ratio = 0.20
  const invalid = {
    schema_version: '0.1',
    name: 'semantic_invalid_must_not_load',
    units: 'mm',
    blade_spec: blade,
    assembly: {
      blade_count: 2,
      hub_diameter_mm: 90,
      hub_length_mm: 30,
      shaft_bore_diameter_mm: 12,
      initial_azimuth_deg: 0,
    },
  }
  const validateResponse = await page.request.post('/api/propellers/validate', { data: invalid })
  const buildResponse = await page.request.post('/api/propellers/build', { data: invalid })
  expect(validateResponse.status()).toBe(422)
  expect(buildResponse.status()).toBe(422)
  expect((await validateResponse.json()).issues[0].code).toBe('invalid_blade_spec')
  expect((await buildResponse.json()).issues[0].field).toBe('blade_spec.thickness_distribution')

  await page.goto('/')
  await expect(page.getByText('Airfoil Stations (5)')).toBeVisible({ timeout: 30_000 })
  const originalName = await page.getByLabel('Name').inputValue()
  await page.locator('input[type="file"]').setInputFiles({
    name: 'semantic-invalid-propeller.json',
    mimeType: 'application/json',
    buffer: Buffer.from(JSON.stringify(invalid)),
  })
  await expect(page.getByText('Project import rejected. The current project was preserved.')).toBeVisible()
  await expect(page.getByText(/Thickness distribution at r\/R=0.4/)).toBeVisible()
  await expect(page.getByLabel('Name')).toHaveValue(originalName)
  // APIRequestContext is intentionally separate from browser-page traffic. The
  // rejected direct /build returned no job ID, and atomic UI import emitted no
  // browser build request.
  expect(buildRequests).toHaveLength(0)
})
