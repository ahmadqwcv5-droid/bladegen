import { expect, test } from '@playwright/test'
import path from 'node:path'

const evidenceRoot = path.resolve('../docs/screenshots/sprint03b')
const evidence = (name: string) => path.join(evidenceRoot, name)

test('real CAD station inspection and canonical comparison remain revision-safe', async ({ page }) => {
  test.setTimeout(720_000)
  let stlRequests = 0
  page.on('request', request => {
    if (/\/artifacts\/blade_preview\.stl$/.test(request.url())) stlRequests += 1
  })

  await page.goto('/')
  await expect(page.getByText('Airfoil Stations (5)')).toBeVisible()
  await expect(page.getByText(/Canonical design preview is current/)).toBeVisible({ timeout: 30_000 })

  await page.getByRole('button', { name: 'Inspect' }).nth(2).click()
  await expect(page.getByText(/Inspecting Station 3 · r\/R 0.6000/)).toBeVisible()
  await page.getByRole('button', { name: 'Generate Blade' }).click()
  const progress = page.getByRole('progressbar', { name: 'Blade generation progress' })
  await expect(progress).toHaveAttribute('aria-valuenow', '100', { timeout: 360_000 })
  await expect(page.getByText('OCP solid preview')).toBeVisible({ timeout: 30_000 })

  const shell = page.locator('.viewer-shell')
  const selectedGuide = page.getByRole('list', { name: 'Station guide legend' }).getByRole('listitem')
  await expect(shell).toHaveAttribute('data-guide-count', '1')
  await expect(selectedGuide).toHaveAttribute('data-world-y-mm', '120.000000')
  await expect(selectedGuide).toContainText('Station 3: r/R 0.6000 · Y 120.000 mm')
  await expect(page.locator('.viewer-host canvas')).toHaveCount(1)
  expect(stlRequests).toBe(1)
  await shell.screenshot({ path: evidence('single_station_3d.png') })

  await page.getByRole('button', { name: 'Blade Edge View' }).click()
  await expect(shell).toHaveAttribute('data-view', 'edge')
  await page.getByRole('button', { name: 'Isometric View' }).click()
  await expect(shell).toHaveAttribute('data-view', 'isometric')
  const canvas = page.locator('.viewer-host canvas')
  const box = await canvas.boundingBox()
  if (box) {
    await page.mouse.move(box.x + box.width * .45, box.y + box.height * .45)
    await page.mouse.down()
    await page.mouse.move(box.x + box.width * .62, box.y + box.height * .55, { steps: 8 })
    await page.mouse.up()
    await page.mouse.wheel(0, -180)
  }
  await page.getByRole('button', { name: 'Expand Viewer' }).click()
  await expect(page.getByRole('dialog', { name: 'Expanded blade viewer' })).toBeVisible()
  await page.setViewportSize({ width: 960, height: 720 })
  await page.getByRole('button', { name: 'Fit to Model' }).click()
  await expect(selectedGuide).toHaveAttribute('data-world-y-mm', '120.000000')
  await expect(page.locator('.viewer-host canvas')).toHaveCount(1)
  expect(stlRequests).toBe(1)
  await page.keyboard.press('Escape')
  await page.setViewportSize({ width: 1280, height: 720 })

  await page.getByRole('button', { name: 'Compare Stations' }).click()
  await page.getByLabel('Comparison Station A').selectOption({ label: 'Station 1 · r/R 0.2000' })
  await page.getByLabel('Comparison Station B').selectOption({ label: 'Station 4 · r/R 0.8000' })
  const guideItems = page.getByRole('list', { name: 'Station guide legend' }).getByRole('listitem')
  await expect(shell).toHaveAttribute('data-guide-count', '2')
  await expect(guideItems).toHaveCount(2)
  await expect(guideItems.nth(0)).toHaveAttribute('data-world-y-mm', '40.000000')
  await expect(guideItems.nth(1)).toHaveAttribute('data-world-y-mm', '160.000000')
  await expect(guideItems.nth(0)).toContainText('Station A')
  await expect(guideItems.nth(1)).toContainText('Station B')
  expect(stlRequests).toBe(1)
  await shell.screenshot({ path: evidence('two_comparison_stations_3d.png') })

  const comparison = page.getByRole('region', { name: 'Airfoil station comparison' })
  await expect(comparison.getByRole('img', { name: /source airfoil comparison/i })).toHaveAttribute('data-coordinate-scale', '1:1')
  await comparison.screenshot({ path: evidence('source_profile_comparison.png') })
  await comparison.getByRole('button', { name: 'Resolved Design Profiles' }).click()
  await expect(comparison.getByRole('img', { name: /resolved airfoil comparison/i })).toHaveAttribute('data-profile-mode', 'resolved')
  await comparison.screenshot({ path: evidence('resolved_profile_comparison.png') })

  const oldJobLabel = await page.locator('.preview-label').textContent()
  const oldJobId = oldJobLabel?.match(/job ([0-9a-f]{8})/i)?.[1]
  expect(oldJobId).toBeTruthy()
  await page.getByLabel('Chord value 3').fill('0.31')
  await page.getByLabel('Chord value 3').blur()
  await expect(page.getByText(/Inputs changed — regenerate/)).toBeVisible()
  await expect(shell).toHaveAttribute('data-guide-count', '0')
  await expect(page.getByText(/Station guides hidden: displayed CAD belongs to previous inputs/)).toBeVisible()
  await expect(comparison).toBeVisible({ timeout: 30_000 })
  await page.screenshot({ path: evidence('stale_cad_guides_hidden.png'), fullPage: true })

  await page.getByRole('button', { name: 'Generate Blade' }).click()
  await expect(page.getByText(/Active job .* · (queued|running)/)).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText(/Active job .* · succeeded/)).toBeVisible({ timeout: 360_000 })
  await expect(page.locator('.preview-label')).not.toContainText(oldJobId!, { timeout: 30_000 })
  await expect(progress).toHaveAttribute('aria-valuenow', '100')
  await expect(shell).toHaveAttribute('data-guide-count', '2')
  await expect(guideItems.nth(0)).toHaveAttribute('data-world-y-mm', '40.000000')
  await expect(guideItems.nth(1)).toHaveAttribute('data-world-y-mm', '160.000000')
  await expect(page.locator('.viewer-host canvas')).toHaveCount(1)
  expect(stlRequests).toBe(2)
  await page.screenshot({ path: evidence('matching_new_cad_guides_restored.png'), fullPage: true })
})
