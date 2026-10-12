import { expect, test, type Locator, type Page } from '@playwright/test'
import path from 'node:path'

const evidenceRoot = path.resolve('../docs/screenshots/sprint03c')
const evidence = (name: string) => path.join(evidenceRoot, name)

async function dragControlTo(page: Page, marker: Locator, targetValue: number) {
  await marker.scrollIntoViewIfNeeded()
  await marker.hover()
  const svg = marker.locator('xpath=ancestor::*[name()="svg"]')
  const target = await svg.evaluate((element, requested) => {
    const labels = [...element.querySelectorAll('text[x="8"]')].map(node => Number(node.textContent))
    const svgY = 18 + (labels[0] - requested) / (labels[0] - labels[1]) * 200
    const point = new DOMPoint(320, svgY).matrixTransform(element.getScreenCTM()!)
    return { x: point.x, y: point.y }
  }, targetValue)
  const markerBox = await marker.boundingBox()
  expect(markerBox).not.toBeNull()
  await page.mouse.move(markerBox!.x + markerBox!.width / 2, markerBox!.y + markerBox!.height / 2)
  await page.mouse.down({ button: 'left' })
  await page.mouse.move(target.x, target.y, { steps: 12 })
}

test('visual curve editing is transactional and final CAD matches the committed design', async ({ page }) => {
  test.setTimeout(720_000)
  await page.setViewportSize({ width: 1280, height: 900 })
  let builds = 0
  let validations = 0
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/api/build')) builds += 1
    if (request.method() === 'POST' && request.url().endsWith('/api/validate')) validations += 1
  })
  await page.goto('/')
  await expect(page.getByRole('img', { name: /Chord Distribution canonical/ })).toBeVisible({ timeout: 30_000 })
  await page.getByRole('slider', { name: /Chord Distribution control 3,/ }).focus()
  await page.screenshot({ path: evidence('selected_control.png'), fullPage: true })

  const chordMarker = page.getByRole('slider', { name: /Chord Distribution control 3,/ })
  await dragControlTo(page, chordMarker, 64)
  await expect(page.getByText(/Draft · r\/R 0\.5000/)).toBeVisible()
  await page.locator('.distribution-visual').screenshot({ path: evidence('active_draft.png') })
  expect(builds).toBe(0)
  await page.mouse.up()
  await expect.poll(async () => Number(await page.getByLabel('Chord value 3').inputValue())).toBeCloseTo(64, 3)
  expect(validations).toBe(1)
  expect(builds).toBe(0)
  await page.locator('.distribution-visual').screenshot({ path: evidence('updated_curve_table.png') })

  await page.getByRole('button', { name: 'Undo curve edit' }).click()
  await expect(page.getByLabel('Chord value 3')).toHaveValue('60')
  await page.getByRole('button', { name: 'Redo curve edit' }).click()
  await expect.poll(async () => Number(await page.getByLabel('Chord value 3').inputValue())).toBeCloseTo(64, 3)
  await page.screenshot({ path: evidence('undo_redo.png'), fullPage: true })
  expect(validations).toBe(1)

  await page.setViewportSize({ width: 720, height: 900 })
  await page.getByRole('button', { name: 'Twist', exact: true }).click()
  const twistMarker = page.getByRole('slider', { name: /Twist Distribution control 4,/ })
  await dragControlTo(page, twistMarker, 27)
  await page.mouse.up()
  await expect.poll(async () => Number(await page.getByLabel('Twist value 4').inputValue())).toBeCloseTo(27, 3)
  expect(validations).toBe(2)
  expect(builds).toBe(0)

  await page.getByRole('button', { name: 'Thickness', exact: true }).click()
  await page.getByRole('slider', { name: /Thickness Distribution control 2/ }).click({ force: true })
  await expect(page.getByText(/Enable its explicit thickness override first/).first()).toBeVisible()
  await page.screenshot({ path: evidence('rejected_thickness.png'), fullPage: true })
  expect(validations).toBe(2)
  expect(builds).toBe(0)

  await page.setViewportSize({ width: 520, height: 900 })
  await expect(page.locator('.distribution-visual')).toBeVisible()
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.getByRole('button', { name: 'Generate Blade' }).click()
  const progress = page.getByRole('progressbar', { name: 'Blade generation progress' })
  await expect(page.getByText(/Active job .* · (queued|running|succeeded)/)).toBeVisible({ timeout: 30_000 })
  expect(builds).toBe(1)
  await expect(progress).toHaveAttribute('aria-valuenow', '100', { timeout: 360_000 })
  await expect(page.getByText('Overall').locator('..')).toContainText('PASS')
  await expect(page.getByText('Solid / free edges').locator('..')).toContainText('1 / 0')
  const specArtifact = page.getByRole('link', { name: 'blade_spec.json', exact: true })
  const submitted = await page.request.get(await specArtifact.getAttribute('href') ?? '')
  const builtSpec = await submitted.json()
  expect(builtSpec.chord_distribution.points.find((point: { r_over_R: number }) => point.r_over_R === .5).chord_over_R * builtSpec.diameter_mm / 2).toBeCloseTo(64, 3)
  expect(builtSpec.twist_distribution.points.find((point: { r_over_R: number }) => point.r_over_R === .65).twist_deg).toBeCloseTo(27, 3)
  await page.screenshot({ path: evidence('final_cad.png'), fullPage: true })
})
