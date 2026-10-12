import { expect, test } from '@playwright/test'
import path from 'node:path'

const evidenceRoot = path.resolve('../docs/screenshots/patch03b1')
const evidence = (name: string) => path.join(evidenceRoot, name)

test('real CAD station inspection and canonical comparison remain revision-safe', async ({ page }) => {
  test.setTimeout(720_000)
  await page.setViewportSize({ width: 1440, height: 900 })
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
  const canvas = page.locator('.viewer-host canvas')
  const verifyFittedVisibility = async (label: string) => {
    await expect(shell).toHaveAttribute('data-camera-framing', 'fitted')
    await expect(shell).toHaveAttribute('data-frustum-contained', 'true')
    const canvasBox = await canvas.boundingBox()
    expect(canvasBox, `${label} canvas bounds`).not.toBeNull()
    const measuredAspect = Number(await shell.getAttribute('data-camera-aspect'))
    expect(measuredAspect).toBeCloseTo(canvasBox!.width / canvasBox!.height, 3)
    return {
      label,
      viewport: page.viewportSize(),
      canvas: { width: canvasBox!.width, height: canvasBox!.height },
      cameraAspect: measuredAspect,
      direction: await shell.getAttribute('data-camera-direction'),
    }
  }
  const selectedGuide = page.getByRole('list', { name: 'Station guide legend' }).getByRole('listitem')
  await expect(shell).toHaveAttribute('data-guide-count', '1')
  await expect(selectedGuide).toHaveAttribute('data-world-y-mm', '120.000000')
  await expect(selectedGuide).toContainText('Station 3: r/R 0.6000 · Y 120.000 mm')
  await expect(canvas).toHaveCount(1)
  await expect(shell).toHaveAttribute('data-renderer-builds', '1')
  expect(stlRequests).toBe(1)
  await canvas.evaluate(element => {
    (window as unknown as { patch03b1Canvas?: Element }).patch03b1Canvas = element
  })

  await page.getByRole('button', { name: 'Blade Edge View' }).click()
  await expect(shell).toHaveAttribute('data-view', 'edge')
  await page.getByRole('button', { name: 'Isometric View' }).click()
  await expect(shell).toHaveAttribute('data-view', 'isometric')
  await page.getByRole('button', { name: 'Fit to Model' }).click()
  const wide = await verifyFittedVisibility('wide')
  await shell.screenshot({ path: evidence('wide_viewport_full_blade.png') })

  await page.getByRole('button', { name: 'Expand Viewer' }).click()
  await expect(page.getByRole('dialog', { name: 'Expanded blade viewer' })).toBeVisible()
  const expanded = await verifyFittedVisibility('expanded')
  expect(expanded.direction).toBe(wide.direction)
  await shell.screenshot({ path: evidence('expanded_viewer.png') })
  await page.getByRole('button', { name: 'Restore Viewer' }).click()
  const restored = await verifyFittedVisibility('restored')
  expect(restored.direction).toBe(wide.direction)
  await shell.screenshot({ path: evidence('restored_viewer.png') })

  await page.setViewportSize({ width: 720, height: 900 })
  const narrow = await verifyFittedVisibility('narrow')
  expect(narrow.direction).toBe(wide.direction)
  expect(narrow.viewport?.width).toBeLessThan(wide.viewport?.width ?? Number.POSITIVE_INFINITY)
  await shell.screenshot({ path: evidence('narrow_viewport_full_blade.png') })

  const box = await canvas.boundingBox()
  if (box) {
    await page.mouse.move(box.x + box.width * .45, box.y + box.height * .45)
    await page.mouse.down()
    await page.mouse.move(box.x + box.width * .62, box.y + box.height * .55, { steps: 8 })
    await page.mouse.up()
    await page.mouse.wheel(0, -180)
  }
  await expect(shell).toHaveAttribute('data-camera-framing', 'manual')
  await page.waitForTimeout(750)
  await canvas.click({ position: { x: 12, y: 12 } })
  const manualDirection = await shell.getAttribute('data-camera-direction')
  await page.setViewportSize({ width: 640, height: 900 })
  await expect(shell).toHaveAttribute('data-camera-framing', 'manual')
  const resizedManualDirection = await shell.getAttribute('data-camera-direction')
  const before = manualDirection!.split(',').map(Number)
  const after = resizedManualDirection!.split(',').map(Number)
  const dot = before.reduce((sum, value, index) => sum + value * after[index], 0)
  const beforeLength = Math.hypot(...before)
  const afterLength = Math.hypot(...after)
  expect(dot / (beforeLength * afterLength)).toBeGreaterThan(.999)
  await expect(shell).toHaveAttribute('data-view', 'isometric')
  await page.getByRole('button', { name: 'Fit to Model' }).click()
  await verifyFittedVisibility('manual-refit')
  await expect(selectedGuide).toHaveAttribute('data-world-y-mm', '120.000000')
  await expect(canvas).toHaveCount(1)
  expect(stlRequests).toBe(1)
  await page.setViewportSize({ width: 1280, height: 720 })

  for (const index of [3, 1, 2]) {
    await page.getByRole('button', { name: 'Inspect' }).nth(index).click()
  }
  await expect(canvas).toHaveCount(1)
  expect(await canvas.evaluate(element => element === (window as unknown as { patch03b1Canvas?: Element }).patch03b1Canvas)).toBe(true)
  await expect(shell).toHaveAttribute('data-renderer-builds', '1')
  expect(stlRequests).toBe(1)

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
  await shell.screenshot({ path: evidence('two_selected_station_guides.png') })

  const comparison = page.getByRole('region', { name: 'Airfoil station comparison' })
  await expect(comparison.getByRole('img', { name: /source airfoil comparison/i })).toHaveAttribute('data-coordinate-scale', '1:1')
  await comparison.getByRole('button', { name: 'Resolved Design Profiles' }).click()
  await expect(comparison.getByRole('img', { name: /resolved airfoil comparison/i })).toHaveAttribute('data-profile-mode', 'resolved')

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
  await expect(canvas).toHaveCount(1)
  await expect(shell).toHaveAttribute('data-renderer-builds', '2')
  expect(stlRequests).toBe(2)
  await page.screenshot({ path: evidence('new_successful_cad_guides_restored.png'), fullPage: true })
  console.log('Patch 03B.1 framing results', JSON.stringify([wide, expanded, restored, narrow]))
})
