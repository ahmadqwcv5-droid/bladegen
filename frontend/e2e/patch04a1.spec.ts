import { expect, test, type Page } from '@playwright/test'
import path from 'node:path'

const evidenceRoot = path.resolve('../docs/screenshots/patch04a1')
const evidence = (name: string) => path.join(evidenceRoot, name)

async function setNumber(page: Page, label: string, value: number) {
  const input = page.getByLabel(label)
  await input.fill(String(value))
  await input.blur()
  await expect(input).toHaveValue(String(value))
}

async function waitForQualifiedResult(page: Page) {
  await expect(page.getByText('Assembly validation')).toBeVisible({ timeout: 360_000 })
  await expect(page.getByText('Overall').locator('..')).toContainText('PASS')
  await expect(page.getByText('Solid / free edges').locator('..')).toContainText('1 / 0')
  await expect(page.getByRole('link', { name: 'propeller_solid.step', exact: true })).toBeVisible()
}

test('90×30 project survives validation history, export/open, and a fresh-session rebuild', async ({ page, context }) => {
  test.setTimeout(900_000)
  await page.setViewportSize({ width: 1440, height: 1000 })
  let builds = 0
  context.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/api/propellers/build')) builds += 1
  })

  await page.goto('/')
  await expect(page.getByText('Airfoil Stations (5)')).toBeVisible({ timeout: 30_000 })
  await page.getByRole('button', { name: 'Load Example' }).click()
  await page.getByRole('button', { name: 'Full Propeller' }).click()
  await page.getByLabel('Propeller Name').fill('two_blade_propeller_hub_90x30')
  await page.getByLabel('Number of Blades').selectOption('2')
  await setNumber(page, 'Hub Diameter', 90)
  await setNumber(page, 'Hub Length', 30)
  await setNumber(page, 'Shaft Bore Diameter', 12)

  await page.getByRole('button', { name: 'Generate Propeller' }).click()
  await waitForQualifiedResult(page)
  expect(builds).toBe(1)
  await page.screenshot({ path: evidence('assembly_a_90x30_success.png'), fullPage: true })

  await setNumber(page, 'Hub Diameter', 60)
  await expect(page.getByText('Hub diameter is too small for the current blade root.')).toBeVisible()
  await expect(page.getByText('greater than 80 mm')).toBeVisible()
  await page.getByRole('button', { name: 'Generate Propeller' }).click()
  await expect(page.getByText('Current inputs are invalid. No new CAD build was started.', { exact: true })).toBeVisible()
  await expect(page.getByText(/Last successful build — previous inputs/)).toBeVisible()
  expect(builds).toBe(1)
  await page.screenshot({ path: evidence('invalid_60x30_historical_result.png'), fullPage: true })

  await setNumber(page, 'Hub Diameter', 90)
  await page.getByRole('button', { name: 'Generate Propeller' }).click()
  await waitForQualifiedResult(page)
  await expect(page.getByText(/Last successful build — current inputs/)).toBeVisible()
  expect(builds).toBe(2)
  await page.screenshot({ path: evidence('assembly_b_90x30_success.png'), fullPage: true })

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Export JSON' }).click(),
  ])
  const downloadPath = await download.path()
  expect(downloadPath).not.toBeNull()

  const fresh = await context.newPage()
  await fresh.goto('/')
  await expect(fresh.getByText('Airfoil Stations (5)')).toBeVisible({ timeout: 30_000 })
  await fresh.locator('input[type="file"]').setInputFiles(downloadPath!)
  await expect(fresh.getByRole('button', { name: 'Full Propeller' })).toHaveAttribute('aria-pressed', 'true')
  await expect(fresh.getByLabel('Propeller Name')).toHaveValue('two_blade_propeller_hub_90x30')
  await expect(fresh.getByLabel('Number of Blades')).toHaveValue('2')
  await expect(fresh.getByLabel('Hub Diameter')).toHaveValue('90')
  await expect(fresh.getByLabel('Hub Length')).toHaveValue('30')
  await expect(fresh.getByLabel('Shaft Bore Diameter')).toHaveValue('12')
  expect(builds).toBe(2)

  await fresh.getByRole('button', { name: 'Generate Propeller' }).click()
  await waitForQualifiedResult(fresh)
  expect(builds).toBe(3)
  await fresh.screenshot({ path: evidence('fresh_session_import_rebuild.png'), fullPage: true })
})
