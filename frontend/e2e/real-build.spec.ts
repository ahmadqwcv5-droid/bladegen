import { expect, test } from '@playwright/test'
import path from 'node:path'

const evidence = (name: string) => path.resolve('../docs/screenshots', name)

test('real backend build reports progress and supports expanded CAD inspection', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Airfoil Stations (5)')).toBeVisible()
  await page.getByLabel('Name').fill('browser_acceptance_blade')
  await page.getByRole('button', { name: 'Generate Blade' }).click()

  const progress = page.getByRole('progressbar', { name: 'Blade generation progress' })
  await expect(progress).toBeVisible()
  await expect.poll(async () => Number(await progress.getAttribute('aria-valuenow')), {
    timeout: 60_000,
    message: 'backend progress should advance beyond the queue',
  }).toBeGreaterThan(0)
  await page.screenshot({ path: evidence('sprint02_1_progress.png'), fullPage: true })

  await expect(progress).toHaveAttribute('aria-valuenow', '100', { timeout: 240_000 })
  await expect(page.getByText(/Preview from completed job/)).toBeVisible()
  await expect(page.getByText('OCP solid preview')).toBeVisible({ timeout: 30_000 })
  await page.screenshot({ path: evidence('sprint02_1_success.png'), fullPage: true })
  await page.locator('.viewer-shell').screenshot({ path: evidence('sprint02_1_viewer_normal.png') })

  await page.getByRole('button', { name: 'Expand Viewer' }).click()
  await expect(page.getByRole('dialog', { name: 'Expanded blade viewer' })).toBeVisible()
  await page.getByRole('button', { name: 'Isometric' }).click()
  const canvas = page.locator('.viewer-host canvas')
  const box = await canvas.boundingBox()
  if (box) {
    await page.mouse.move(box.x + box.width * 0.45, box.y + box.height * 0.45)
    await page.mouse.down()
    await page.mouse.move(box.x + box.width * 0.62, box.y + box.height * 0.52, { steps: 8 })
    await page.mouse.up()
    await page.mouse.wheel(0, -240)
  }
  await page.getByRole('button', { name: 'Fit to Model' }).click()
  await page.screenshot({ path: evidence('sprint02_1_viewer_expanded.png') })
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: 'Expand Viewer' })).toBeVisible()

  const download = page.waitForEvent('download')
  await page.getByRole('link', { name: 'blade_solid.step' }).click()
  expect((await download).suggestedFilename()).toBe('blade_solid.step')

  await page.getByLabel('Name').fill('browser_acceptance_blade_changed')
  await expect(page.getByText(/Inputs changed — regenerate/)).toBeVisible()
})
