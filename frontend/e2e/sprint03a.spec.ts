import { expect, test } from '@playwright/test'
import path from 'node:path'
import { submitBuild, waitForExactResult } from './jobIdentity'

const evidence = (name: string) => path.resolve('../docs/screenshots/sprint03a', name)
const fixture = path.resolve('../backend/tests/fixtures/airfoils/independent_analytic_finite_te.dat')

test('imported airfoil visual-design workflow produces a validated real STEP', async ({ page }) => {
  test.setTimeout(720_000)
  await page.goto('/')
  await expect(page.getByText('Airfoil Stations (5)')).toBeVisible()
  await expect(page.getByRole('img', { name: /canonical pchip distribution/ })).toBeVisible({ timeout: 30_000 })

  await page.getByRole('button', { name: 'Choose from Library' }).nth(2).click()
  const dialog = page.getByRole('dialog', { name: 'Airfoil Library for station 3' })
  await expect(dialog).toBeVisible()
  await dialog.screenshot({ path: evidence('airfoil_selector.png') })

  await dialog.getByLabel('Search airfoils').fill('NACA 2412')
  await dialog.getByRole('button', { name: /NACA 2412/ }).click()
  await expect(dialog.getByRole('img', { name: /NACA 2412 source airfoil coordinates/ })).toBeVisible()
  await dialog.screenshot({ path: evidence('naca_2412_inspector.png') })
  await dialog.getByRole('button', { name: 'Apply to Station 3' }).click()
  await expect(dialog).not.toBeVisible()
  await expect(page.getByRole('img', { name: /NACA 2412.*resolved airfoil coordinates/ })).toBeVisible({ timeout: 30_000 })

  const chordLine = page.locator('.chart-line')
  const originalChord = await chordLine.getAttribute('data-values')
  await page.getByLabel('Chord value 3').fill('62')
  await page.getByLabel('Chord value 3').blur()
  await expect.poll(() => chordLine.getAttribute('data-values')).not.toBe(originalChord)
  await page.locator('.distribution-visual').screenshot({ path: evidence('chord_distribution.png') })

  await page.getByRole('button', { name: 'Twist', exact: true }).click()
  await expect(page.getByRole('img', { name: /Twist Distribution canonical/ })).toBeVisible()
  const twistLine = page.locator('.chart-line')
  const originalTwist = await twistLine.getAttribute('data-values')
  await page.getByLabel('Twist value 3').fill('27')
  await page.getByLabel('Twist value 3').blur()
  await expect.poll(() => twistLine.getAttribute('data-values')).not.toBe(originalTwist)
  await page.locator('.distribution-visual').screenshot({ path: evidence('twist_distribution.png') })

  await page.getByRole('button', { name: 'Choose from Library' }).nth(2).click()
  await expect(dialog).toBeVisible()
  await dialog.getByText('Import DAT or CSV').click()
  await dialog.getByLabel('Airfoil coordinate file').setInputFiles(fixture)
  await dialog.getByLabel('Imported airfoil name').fill('Independent analytic profile')
  await dialog.getByLabel('Airfoil source').fill('BladeGen Sprint 03A explicit analytic fixture')
  await dialog.getByLabel('Airfoil license').fill('Test fixture; not third-party data')
  await dialog.getByRole('button', { name: 'Import and Preview' }).click()
  await expect(dialog.getByText(/natural geometric t\/c/)).toBeVisible({ timeout: 30_000 })
  await expect(dialog.getByText(/Coordinate SHA-256/)).toBeVisible()
  await dialog.screenshot({ path: evidence('imported_airfoil_inspector.png') })
  await dialog.getByRole('button', { name: 'Apply to Station 3' }).click()
  await expect(page.getByText('Independent analytic profile', { exact: true })).toBeVisible()
  await expect(page.getByRole('img', { name: /Imported coordinate profile.*resolved airfoil coordinates/ })).toBeVisible({ timeout: 30_000 })

  const exportDownload = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export JSON' }).click()
  const downloaded = await exportDownload
  const downloadPath = await downloaded.path()
  expect(downloadPath).not.toBeNull()
  await page.locator('input[accept="application/json,.json"]').setInputFiles(downloadPath!)
  await expect(page.getByText(/Opened and validated/)).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('Coordinate profile')).toBeVisible()

  const jobId = await submitBuild(page, 'Generate Blade', '/api/build')
  await waitForExactResult(page, jobId)
  await expect(page.getByText('Overall').locator('..')).toContainText('PASS')
  await expect(page.getByText('Solid / free edges').locator('..')).toContainText('1 / 0')
  await expect(page.getByRole('link', { name: 'blade_solid.step' })).toBeVisible()
  await page.screenshot({ path: evidence('imported_airfoil_validated_step.png'), fullPage: true })
})
