import { expect, test, type Page } from '@playwright/test'
import path from 'node:path'

const evidenceRoot = path.resolve('../docs/screenshots/patch02_1_1')
const exampleRoot = path.resolve('../examples')

const cases = [
  {
    id: 'three_section',
    file: 'sprint02_case_a_three_section.json',
    stations: 3,
  },
  {
    id: 'five_section',
    file: 'custom_multi_airfoil_finite_te.json',
    stations: 5,
  },
  {
    id: 'eight_section',
    file: 'sprint02_case_c_eight_section.json',
    stations: 8,
  },
]

async function loadSpec(page: Page, filename: string, stations: number) {
  await page.locator('input[type=file]').setInputFiles(path.join(exampleRoot, filename))
  await expect(page.getByText(`Airfoil Stations (${stations})`)).toBeVisible()
  await expect(page.getByText(/Opened and validated/)).toBeVisible()
}

test('Face/Edge camera and adaptive framing work on 3, 5, and 8-section real blades', async ({ page }) => {
  test.setTimeout(720_000)
  const prematureCompletion: string[] = []
  page.on('response', async response => {
    if (!/\/api\/jobs\/[0-9a-f]{32}$/.test(response.url())) return
    try {
      const payload = await response.json() as { status: string; progress_percent: number }
      if (payload.status !== 'succeeded' && payload.progress_percent >= 100) {
        prematureCompletion.push(`${payload.status}:${payload.progress_percent}`)
      }
    } catch {
      // A navigation or cancelled poll is not a progress assertion failure.
    }
  })

  await page.goto('/')
  await expect(page.getByText('Airfoil Stations (5)')).toBeVisible()

  for (const blade of cases) {
    await loadSpec(page, blade.file, blade.stations)
    await page.getByRole('button', { name: 'Generate Blade' }).click()
    await expect(page.getByText(/Active job .* · (queued|running)/)).toBeVisible({ timeout: 30_000 })

    const progress = page.getByRole('progressbar', { name: 'Blade generation progress' })
    await expect(progress).toBeVisible()
    await expect.poll(async () => Number(await progress.getAttribute('aria-valuenow')), {
      timeout: 90_000,
    }).toBeGreaterThan(0)
    expect(Number(await progress.getAttribute('aria-valuenow'))).toBeLessThan(100)
    await expect(progress).toHaveAttribute('aria-valuenow', '100', { timeout: 300_000 })
    await expect(page.getByText('OCP solid preview')).toBeVisible({ timeout: 30_000 })

    const shell = page.locator('.viewer-shell')
    await expect(shell).toHaveAttribute('data-view', 'face')
    await expect(page.getByRole('button', { name: 'Blade Face View' })).toHaveAttribute('aria-pressed', 'true')
    const faceImage = await shell.screenshot({
      path: path.join(evidenceRoot, `${blade.id}_normal_face.png`),
    })

    await page.getByRole('button', { name: 'Blade Edge View' }).click()
    await expect(shell).toHaveAttribute('data-view', 'edge')
    const edgeImage = await shell.screenshot()
    expect(edgeImage.equals(faceImage)).toBe(false)

    await page.getByRole('button', { name: 'Isometric View' }).click()
    await expect(shell).toHaveAttribute('data-view', 'isometric')
    const isometricImage = await shell.screenshot()
    expect(isometricImage.equals(edgeImage)).toBe(false)

    await page.getByRole('button', { name: 'Blade Face View' }).click()
    await page.getByRole('button', { name: 'Expand Viewer' }).click()
    await expect(page.getByRole('dialog', { name: 'Expanded blade viewer' })).toBeVisible()
    await page.setViewportSize({ width: 960, height: 720 })
    await page.getByRole('button', { name: 'Fit to Model' }).click()

    const hostBox = await page.locator('.viewer-host').boundingBox()
    const canvasBox = await page.locator('.viewer-host canvas').boundingBox()
    expect(hostBox).not.toBeNull()
    expect(canvasBox).not.toBeNull()
    expect(Math.abs((hostBox?.width ?? 0) - (canvasBox?.width ?? 0))).toBeLessThanOrEqual(1)
    expect(Math.abs((hostBox?.height ?? 0) - (canvasBox?.height ?? 0))).toBeLessThanOrEqual(1)
    await page.screenshot({
      path: path.join(evidenceRoot, `${blade.id}_expanded_face.png`),
    })

    await page.keyboard.press('Escape')
    await expect(page.getByRole('button', { name: 'Expand Viewer' })).toBeVisible()
    await page.setViewportSize({ width: 1280, height: 720 })
  }

  expect(prematureCompletion).toEqual([])
})
