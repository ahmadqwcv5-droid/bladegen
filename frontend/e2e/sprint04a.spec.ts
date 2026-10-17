import { expect, test, type Page } from '@playwright/test'
import path from 'node:path'
import { submitBuild, waitForExactResult } from './jobIdentity'

const evidenceRoot = (process.env.L1A_EVIDENCE_ROOT ? path.resolve(process.env.L1A_EVIDENCE_ROOT, "screenshots/sprint04a") : path.resolve('../docs/screenshots/sprint04a'))
const evidence = (name: string) => path.join(evidenceRoot, name)

async function setBladeCount(page: Page, count: number) {
  const input = page.getByLabel('Number of Blades')
  await input.selectOption(String(count))
  await expect(input).toHaveValue(String(count))
}

async function generate(page: Page, count: number) {
  await setBladeCount(page, count)
  const jobId = await submitBuild(page, 'Generate Propeller', '/api/propellers/build')
  await waitForExactResult(page, jobId)
  await expect(page.getByText('Assembly validation')).toBeVisible({ timeout: 360_000 })
  await expect(page.getByText('Overall').locator('..')).toContainText('PASS')
  await expect(page.getByText('Solid / free edges').locator('..')).toContainText('1 / 0')
  await expect(page.getByRole('link', { name: 'propeller_solid.step', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'blade_solid.step', exact: true })).toBeVisible()
  return jobId
}

test('real full-propeller workflow builds qualified 2/3/4 blade solids and preserves identity', async ({ page }) => {
  test.setTimeout(1_200_000)
  await page.setViewportSize({ width: 1440, height: 1000 })
  let propellerBuilds = 0
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/api/propellers/build')) {
      propellerBuilds += 1
    }
  })
  await page.goto('/')
  await expect(page.getByText('Airfoil Stations (5)')).toBeVisible({ timeout: 30_000 })
  await page.getByRole('button', { name: 'Full Propeller' }).click()
  await expect(page.getByRole('heading', { name: 'Propeller Assembly' })).toBeVisible()
  await page.screenshot({ path: evidence('assembly_controls.png'), fullPage: true })

  await setBladeCount(page, 2)
  await page.getByRole('button', { name: 'Validate Assembly' }).click()
  await expect(page.getByText(/Input validation passed; final geometric qualification has not yet run/)).toBeVisible()
  expect(propellerBuilds).toBe(0)
  await generate(page, 2)
  expect(propellerBuilds).toBe(1)
  await page.getByRole('button', { name: 'Propeller Front View' }).click()
  await page.screenshot({ path: evidence('two_blade_assembly.png'), fullPage: true })
  await page.screenshot({ path: evidence('hub_bore_front_detail.png'), fullPage: true })

  await setBladeCount(page, 3)
  await expect(page.getByText(/Inputs changed — regenerate/)).toBeVisible()
  expect(propellerBuilds).toBe(1)
  await generate(page, 3)
  expect(propellerBuilds).toBe(2)
  await page.getByRole('button', { name: 'Propeller Side View' }).click()
  await page.getByRole('button', { name: 'Isometric View' }).click()
  await page.screenshot({ path: evidence('three_blade_assembly.png'), fullPage: true })

  await setBladeCount(page, 4)
  await expect(page.getByText(/Inputs changed — regenerate/)).toBeVisible()
  const fourBladeJobId = await generate(page, 4)
  expect(propellerBuilds).toBe(3)
  await page.getByRole('button', { name: 'Propeller Front View' }).click()
  await page.screenshot({ path: evidence('four_blade_assembly.png'), fullPage: true })
  await page.getByRole('button', { name: 'Expand Viewer' }).click()
  await expect(page.getByRole('dialog', { name: 'Expanded propeller viewer' })).toBeVisible()
  await page.screenshot({ path: evidence('expanded_propeller_viewer.png'), fullPage: true })
  await page.getByRole('button', { name: 'Restore Viewer' }).click()
  await page.screenshot({ path: evidence('assembly_validation_results.png'), fullPage: true })

  const specLink = page.getByRole('link', { name: 'propeller_spec.json', exact: true })
  await expect(page.locator(`[data-result-job-id="${fourBladeJobId}"]`)).toBeVisible()
  await expect(specLink).toHaveAttribute(
    'href',
    `/api/jobs/${fourBladeJobId}/artifacts/propeller_spec.json`,
  )
  const submitted = await page.request.get(await specLink.getAttribute('href') ?? '')
  expect(submitted.ok()).toBe(true)
  const builtSpec = await submitted.json()
  expect(builtSpec.assembly.blade_count).toBe(4)
  expect(builtSpec.blade_spec.airfoil_sections).toHaveLength(5)
  const stepLink = page.getByRole('link', { name: 'propeller_solid.step', exact: true })
  const step = await page.request.get(await stepLink.getAttribute('href') ?? '')
  expect(step.ok()).toBe(true)
  expect((await step.body()).byteLength).toBeGreaterThan(100_000)
})
