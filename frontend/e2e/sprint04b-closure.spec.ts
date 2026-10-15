import { expect, test, type Page, type Route } from '@playwright/test'
import { readFile } from 'node:fs/promises'

const importedRows = [
  'row\tr_over_R\tchord_mm\ttwist_deg\trake_mm\tskew_mm',
  '1\t.2\t80\t30\t-2.5\t-1.25',
  '2\t.6\t62.5\t18.25\t-0.001\t0',
  '3\t1\t30\t5\t1.75\t2.5',
].join('\n')

type ValidationGate = {
  seen: Promise<void>
  release: () => void
  settled: Promise<'fulfilled' | 'cancelled'>
}

async function installValidationGate(page: Page) {
  let active: {
    seen: () => void
    released: Promise<void>
    settle: (disposition: 'fulfilled' | 'cancelled') => void
  } | undefined
  await page.route('**/api/validate', async (route: Route) => {
    if (route.request().method() !== 'POST' || !active) {
      await route.continue()
      return
    }
    const operation = active
    active = undefined
    operation.seen()
    await operation.released
    try {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{"valid":true}' })
      operation.settle('fulfilled')
    } catch {
      operation.settle('cancelled')
    }
  })
  return (): ValidationGate => {
    let seen!: () => void
    let release!: () => void
    let settle!: (disposition: 'fulfilled' | 'cancelled') => void
    const gate = {
      seen: new Promise<void>(resolve => { seen = resolve }),
      released: new Promise<void>(resolve => { release = resolve }),
      settled: new Promise<'fulfilled' | 'cancelled'>(resolve => { settle = resolve }),
    }
    active = { seen, released: gate.released, settle }
    return { seen: gate.seen, release, settled: gate.settled }
  }
}

async function exportCurrentSpec(page: Page): Promise<Record<string, unknown>> {
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export JSON' }).click()
  const download = await downloadPromise
  const downloadPath = await download.path()
  expect(downloadPath).not.toBeNull()
  return JSON.parse(await readFile(downloadPath!, 'utf8')) as Record<string, unknown>
}

test('Cancel owns pending bulk Apply and ignores successful late validation', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Airfoil Stations (5)')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText(/Canonical design preview is current/)).toBeVisible({ timeout: 30_000 })
  const holdNextValidation = await installValidationGate(page)
  const baseline = await exportCurrentSpec(page)

  const distributionValidation = holdNextValidation()
  await page.getByRole('button', { name: 'Import Distributions' }).click()
  let dialog = page.getByRole('dialog', { name: 'Import Distributions' })
  await dialog.getByLabel('Distribution pasted data').fill(importedRows)
  await dialog.getByRole('button', { name: 'Review Pasted Data' }).click()
  await expect(dialog.getByText('3 rows', { exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: 'Apply Once' }).click()
  await distributionValidation.seen
  await expect(dialog.getByRole('button', { name: 'Validating candidate…' })).toBeVisible()
  await dialog.getByRole('button', { name: 'Cancel' }).first().click()
  await expect(dialog).not.toBeVisible()
  distributionValidation.release()
  expect(['fulfilled', 'cancelled']).toContain(await distributionValidation.settled)
  await expect(page.locator('.curve-edit-state')).toHaveText('Ready')
  expect(await exportCurrentSpec(page)).toEqual(baseline)
  await expect(page.getByText('Chord (6)')).toBeVisible()
  await expect(page.getByText('Twist (6)')).toBeVisible()
  await expect(page.getByText('Rake (6)')).toBeVisible()
  await expect(page.getByText('Skew (6)')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Undo curve edit' })).toBeDisabled()
  await expect(page.getByLabel('Chord value 1', { exact: true })).toBeEnabled()

  const stationValidation = holdNextValidation()
  await page.getByRole('button', { name: 'Set Up Airfoil Stations' }).click()
  dialog = page.getByRole('dialog', { name: 'Set Up Airfoil Stations' })
  await dialog.getByLabel('Total airfoil stations').fill('3')
  await dialog.getByRole('button', { name: 'Apply Once' }).click()
  await stationValidation.seen
  await expect(dialog.getByRole('button', { name: 'Validating candidate…' })).toBeVisible()
  await dialog.getByRole('button', { name: 'Cancel' }).first().click()
  await expect(dialog).not.toBeVisible()
  stationValidation.release()
  expect(['fulfilled', 'cancelled']).toContain(await stationValidation.settled)
  await expect(page.locator('.curve-edit-state')).toHaveText('Ready')
  expect(await exportCurrentSpec(page)).toEqual(baseline)
  await expect(page.getByText('Airfoil Stations (5)')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Undo curve edit' })).toBeDisabled()
  await expect(page.getByLabel('Chord value 1', { exact: true })).toBeEnabled()

  await page.getByRole('button', { name: 'Import Distributions' }).click()
  await expect(page.getByRole('dialog', { name: 'Import Distributions' })).toBeVisible()
})
