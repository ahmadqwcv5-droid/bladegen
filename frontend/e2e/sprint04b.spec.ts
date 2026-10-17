import { expect, test, type Browser, type Page } from '@playwright/test'
import path from 'node:path'
import { submitBuild, waitForExactResult } from './jobIdentity'

const evidenceRoot = (process.env.L1A_EVIDENCE_ROOT ? path.resolve(process.env.L1A_EVIDENCE_ROOT, "screenshots/sprint04b") : path.resolve('../docs/screenshots/sprint04b'))
const evidence = (name: string) => path.join(evidenceRoot, name)

const percentile = (values: number[], fraction: number) => {
  const sorted = [...values].sort((left, right) => left - right)
  const position = (sorted.length - 1) * fraction
  const lower = Math.floor(position)
  const upper = Math.ceil(position)
  return sorted[lower] + (sorted[upper] - sorted[lower]) * (position - lower)
}

const distributionText = (delimiter: ',' | '\t') => {
  const rows = Array.from({ length: 40 }, (_, index) => {
    const fraction = index / 39
    const radius = index === 39 ? 1 : .2 + .8 * fraction
    return [
      index + 1,
      radius,
      80 - 50 * fraction,
      30 - 25 * fraction,
      -2.5 + 4.25 * fraction,
      -1.25 + 3.75 * fraction,
    ].join(delimiter)
  })
  return `row${delimiter}r_over_R${delimiter}chord_mm${delimiter}twist_deg${delimiter}rake_mm${delimiter}skew_mm\n${rows.join('\n')}`
}

async function waitForPreview(page: Page) {
  await expect(page.getByText(/Canonical design preview is current/)).toBeVisible({ timeout: 30_000 })
}

async function exactJobArtifacts(page: Page, jobId: string, specName: string, stepName: string) {
  const response = await page.request.get(`/api/jobs/${jobId}/artifacts`)
  expect(response.ok()).toBe(true)
  const artifacts = await response.json() as Array<{ name: string; download_url: string }>
  const byName = new Map(artifacts.map(artifact => [artifact.name, artifact.download_url]))
  for (const name of [specName, stepName, 'validation.json']) {
    expect(byName.get(name)).toBe(`/api/jobs/${jobId}/artifacts/${name}`)
    await expect(page.getByRole('link', { name, exact: true })).toHaveAttribute('href', byName.get(name)!)
  }
  const validation = await page.request.get(byName.get('validation.json')!)
  expect(validation.ok()).toBe(true)
  const body = await validation.json()
  expect(body.status).toBe('PASS')
  return { artifacts, validation: body }
}

async function importDownloadedProject(browser: Browser, downloadPath: string) {
  const context = await browser.newContext()
  const page = await context.newPage()
  await page.goto('/')
  await expect(page.getByText('Airfoil Stations (5)')).toBeVisible({ timeout: 30_000 })
  await waitForPreview(page)
  await page.locator('input[type="file"][accept*="json"]').setInputFiles(downloadPath)
  await expect(page.getByText('Airfoil Stations (2)')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('Chord (40)')).toBeVisible()
  await expect(page.getByText('Twist (40)')).toBeVisible()
  await expect(page.getByText('Rake (40)')).toBeVisible()
  await expect(page.getByText('Skew (40)')).toBeVisible()
  await expect(page.getByText('Thickness (2)')).toBeVisible()
  await waitForPreview(page)
  await page.screenshot({ path: evidence('isolated_import.png'), fullPage: true })
  return { context, page }
}

test('bulk engineering input is reviewed once, remains editable, and explicitly builds qualified CAD', async ({ page, context, browser }) => {
  test.setTimeout(900_000)
  await page.setViewportSize({ width: 1440, height: 1000 })
  const requestCounts = { validate: 0, preview: 0, bladeBuild: 0, propellerBuild: 0 }
  page.on('request', request => {
    if (request.method() !== 'POST') return
    if (request.url().endsWith('/api/validate')) requestCounts.validate += 1
    else if (request.url().endsWith('/api/design-preview')) requestCounts.preview += 1
    else if (request.url().endsWith('/api/build')) requestCounts.bladeBuild += 1
    else if (request.url().endsWith('/api/propellers/build')) requestCounts.propellerBuild += 1
  })
  await page.goto('/')
  await expect(page.getByText('Airfoil Stations (5)')).toBeVisible({ timeout: 30_000 })
  await waitForPreview(page)

  const acknowledgement: number[] = []
  for (let index = 0; index < 21; index += 1) {
    const started = performance.now()
    await page.getByRole('button', { name: 'Import Distributions' }).click()
    const dialog = page.getByRole('dialog', { name: 'Import Distributions' })
    await expect(dialog).toBeVisible()
    const elapsed = performance.now() - started
    if (index > 0) acknowledgement.push(elapsed)
    await dialog.getByRole('button', { name: 'Cancel' }).first().click()
  }
  const acknowledgementResult = {
    repetitions: 20,
    median_ms: percentile(acknowledgement, .5),
    p95_ms: percentile(acknowledgement, .95),
    max_ms: Math.max(...acknowledgement),
  }
  console.log(`SPRINT04B_DIALOG_ACK ${JSON.stringify(acknowledgementResult)}`)
  expect(acknowledgementResult.p95_ms).toBeLessThanOrEqual(100)

  await page.getByRole('button', { name: 'Set Up Airfoil Stations' }).click()
  const setup = page.getByRole('dialog', { name: 'Set Up Airfoil Stations' })
  await setup.getByLabel('Total airfoil stations').fill('2')
  await setup.getByLabel(/Replace Thickness with a reviewed two-point constant/).check()
  await setup.getByRole('button', { name: 'Apply Once' }).click()
  await expect(page.getByText('Airfoil Stations (2)')).toBeVisible()
  await expect(page.getByText('Thickness (2)')).toBeVisible()
  await waitForPreview(page)

  await page.getByLabel('Select airfoil station 1').check()
  await page.getByLabel('Select airfoil station 2').check()
  await page.getByRole('button', { name: 'Apply Profile to Selected Stations' }).click()
  const selector = page.getByRole('dialog', { name: 'Airfoil Library for 2 selected stations' })
  await selector.getByRole('button', { name: /NACA 0012/ }).click()
  await selector.getByLabel('Use constant thickness for selected common profile').check()
  await selector.getByRole('button', { name: 'Apply to 2 Selected Stations' }).click()
  await expect(page.getByText('Thickness (2)')).toBeVisible()
  await waitForPreview(page)

  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: new URL(page.url()).origin })
  await page.getByRole('button', { name: 'Import Distributions' }).click()
  let dialog = page.getByRole('dialog', { name: 'Import Distributions' })
  await page.evaluate(text => navigator.clipboard.writeText(text), distributionText('\t'))
  await dialog.getByLabel('Distribution pasted data').focus()
  await page.keyboard.press('Control+V')
  await expect(dialog.getByLabel('Distribution pasted data')).toHaveValue(distributionText('\t'))
  await dialog.getByRole('button', { name: 'Review Pasted Data' }).click()
  await expect(dialog.getByText('40 rows', { exact: true })).toBeVisible()
  await expect(dialog.getByText(/row is not mapped to BladeSpec/)).toBeVisible()
  await expect(dialog.getByText(/Thickness unchanged/)).toBeVisible()
  await page.screenshot({ path: evidence('paste_review.png'), fullPage: true })
  await dialog.getByRole('button', { name: 'Cancel' }).first().click()

  await page.getByRole('button', { name: 'Import Distributions' }).click()
  dialog = page.getByRole('dialog', { name: 'Import Distributions' })
  await dialog.getByLabel('Distribution CSV file').setInputFiles({
    name: 'synthetic_40_row_engineering_input.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(distributionText(',')),
  })
  await expect(dialog.getByText('40 rows', { exact: true })).toBeVisible()
  for (const curve of ['Chord', 'Twist', 'Rake', 'Skew']) {
    await expect(dialog.getByLabel(`${curve} import interpolation`)).toHaveValue('pchip')
  }
  const beforeApply = { ...requestCounts }
  const validationResponse = page.waitForResponse(response => response.request().method() === 'POST' && response.url().endsWith('/api/validate'))
  const previewResponse = page.waitForResponse(response => response.request().method() === 'POST' && response.url().endsWith('/api/design-preview'))
  await dialog.getByRole('button', { name: 'Apply Once' }).click()
  expect((await validationResponse).ok()).toBe(true)
  expect((await previewResponse).ok()).toBe(true)
  await waitForPreview(page)
  expect(requestCounts.validate - beforeApply.validate).toBe(1)
  expect(requestCounts.preview - beforeApply.preview).toBe(1)
  expect(requestCounts.bladeBuild - beforeApply.bladeBuild).toBe(0)
  expect(requestCounts.propellerBuild - beforeApply.propellerBuild).toBe(0)
  for (const curve of ['Chord', 'Twist', 'Rake', 'Skew']) await expect(page.getByText(`${curve} (40)`)).toBeVisible()
  await expect(page.getByText('Airfoil Stations (2)')).toBeVisible()
  await expect(page.getByText('Thickness (2)')).toBeVisible()
  await page.getByLabel('Chord value 1', { exact: true }).focus()
  await expect(page.getByLabel('Chord value 1', { exact: true })).toHaveValue('80')
  await page.screenshot({ path: evidence('forty_row_applied.png'), fullPage: true })

  await page.getByRole('button', { name: 'Undo curve edit' }).click()
  await expect(page.getByText('Chord (6)')).toBeVisible()
  await page.getByRole('button', { name: 'Redo curve edit' }).click()
  await expect(page.getByText('Chord (40)')).toBeVisible()
  await page.getByLabel('Chord value 2', { exact: true }).fill('78.7654321')
  await page.getByLabel('Chord value 2', { exact: true }).blur()
  await waitForPreview(page)

  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export JSON' }).click()
  const download = await downloadPromise
  const downloadPath = await download.path()
  expect(downloadPath).toBeTruthy()
  const imported = await importDownloadedProject(browser, downloadPath!)
  await imported.context.close()

  const bladeJob = await submitBuild(page, 'Generate Blade', '/api/build')
  await waitForExactResult(page, bladeJob)
  const bladeEvidence = await exactJobArtifacts(page, bladeJob, 'blade_spec.json', 'blade_solid.step')
  expect(bladeEvidence.validation.solidification.solid_after_reimport).toMatchObject({
    solids: 1, closed_shell: true, brepcheck_valid: true, free_edges: 0,
  })
  await page.screenshot({ path: evidence('qualified_blade.png'), fullPage: true })

  await page.getByRole('button', { name: 'Full Propeller' }).click()
  const propellerJob = await submitBuild(page, 'Generate Propeller', '/api/propellers/build')
  await waitForExactResult(page, propellerJob)
  const propellerEvidence = await exactJobArtifacts(page, propellerJob, 'propeller_spec.json', 'propeller_solid.step')
  expect(propellerEvidence.validation.assembly_validation.final_after_reimport).toMatchObject({
    solids: 1, closed_shell: true, brepcheck_valid: true, free_edges: 0,
  })
  await page.screenshot({ path: evidence('qualified_propeller.png'), fullPage: true })
})
