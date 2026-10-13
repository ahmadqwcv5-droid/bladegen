import { expect, test, type Locator, type Page } from '@playwright/test'
import path from 'node:path'
import { submitBuild, waitForExactResult } from './jobIdentity'

const evidenceRoot = path.resolve('../docs/screenshots/patch03c1')
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
  let previews = 0
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/api/build')) builds += 1
    if (request.method() === 'POST' && request.url().endsWith('/api/validate')) validations += 1
    if (request.method() === 'POST' && request.url().endsWith('/api/design-preview')) previews += 1
  })
  await page.goto('/')
  await expect(page.getByRole('img', { name: /Chord Distribution canonical/ })).toBeVisible({ timeout: 30_000 })
  await page.getByRole('slider', { name: /Chord Distribution control 3,/ }).focus()
  await page.screenshot({ path: evidence('selected_control.png'), fullPage: true })

  const chordMarker = page.getByRole('slider', { name: /Chord Distribution control 3,/ })
  for (const [index, target] of [64, 62, 66, 63, 64].entries()) {
    const beforeValidation = validations
    const beforePreview = previews
    await dragControlTo(page, chordMarker, target)
    await expect(page.getByText(/Draft · r\/R 0\.5000/)).toBeVisible()
    expect(validations).toBe(beforeValidation)
    expect(previews).toBe(beforePreview)
    expect(builds).toBe(0)
    if (index === 0) await page.locator('.distribution-visual').screenshot({ path: evidence('active_draft.png') })
    await page.mouse.up()
    await expect.poll(async () => Number(await page.getByLabel('Chord value 3').inputValue())).toBeCloseTo(target, 3)
    await expect(page.getByText('Ready', { exact: true })).toBeVisible()
    await expect(page.getByText(/Canonical design preview is current/)).toBeVisible({ timeout: 30_000 })
    expect(validations).toBe(beforeValidation + 1)
    expect(previews).toBe(beforePreview + 1)
  }
  await page.locator('.distribution-visual').screenshot({ path: evidence('five_consecutive_chord_edits.png') })

  await page.getByRole('button', { name: 'Undo curve edit' }).click()
  await expect(page.getByLabel('Chord value 3')).toHaveValue('63')
  await chordMarker.hover()
  const chordBox = await chordMarker.boundingBox()
  expect(chordBox).not.toBeNull()
  await page.mouse.move(chordBox!.x + chordBox!.width / 2, chordBox!.y + chordBox!.height / 2)
  await page.mouse.down(); await page.mouse.up()
  await page.getByLabel('Chord value 3').focus(); await page.getByLabel('Chord value 3').blur()
  await page.getByLabel('Chord value 3').fill('63.0'); await page.getByLabel('Chord value 3').blur()
  expect(validations).toBe(5)
  await expect(page.getByRole('button', { name: 'Redo curve edit' })).toBeEnabled()
  await page.getByRole('button', { name: 'Redo curve edit' }).click()
  await expect(page.getByLabel('Chord value 3')).toHaveValue('64')
  await expect(page.getByText(/Canonical design preview is current/)).toBeVisible({ timeout: 30_000 })
  await page.screenshot({ path: evidence('noop_preserves_redo.png'), fullPage: true })

  await page.setViewportSize({ width: 720, height: 900 })
  await page.getByRole('button', { name: 'Twist', exact: true }).click()
  const twistMarker = page.getByRole('slider', { name: /Twist Distribution control 4,/ })
  for (const target of [27, 30, 25, 28, 24, 27]) {
    const beforeValidation = validations
    const beforePreview = previews
    await dragControlTo(page, twistMarker, target)
    expect(validations).toBe(beforeValidation)
    expect(previews).toBe(beforePreview)
    await page.mouse.up()
    await expect.poll(async () => Number(await page.getByLabel('Twist value 4').inputValue())).toBeCloseTo(target, 3)
    await expect(page.getByText('Ready', { exact: true })).toBeVisible()
    await expect(page.getByText(/Canonical design preview is current/)).toBeVisible({ timeout: 30_000 })
    expect(validations).toBe(beforeValidation + 1)
    expect(previews).toBe(beforePreview + 1)
  }
  await page.locator('.distribution-visual').screenshot({ path: evidence('six_consecutive_twist_edits_narrow.png') })
  expect(validations).toBe(11)
  expect(builds).toBe(0)

  await page.getByRole('button', { name: 'Thickness', exact: true }).click()
  await page.getByRole('slider', { name: /Thickness Distribution control 2/ }).click({ force: true })
  await expect(page.getByText(/Enable its explicit thickness override first/).first()).toBeVisible()
  expect(validations).toBe(11)
  expect(builds).toBe(0)

  await page.setViewportSize({ width: 520, height: 900 })
  await expect(page.locator('.distribution-visual')).toBeVisible()
  await page.setViewportSize({ width: 1280, height: 900 })
  const jobId = await submitBuild(page, 'Generate Blade', '/api/build')
  const progress = page.getByRole('progressbar', { name: 'Blade generation progress' })
  await expect(page.getByText(/Active job .* · (queued|running|succeeded)/)).toBeVisible({ timeout: 30_000 })
  expect(builds).toBe(1)
  await waitForExactResult(page, jobId)
  await expect(page.getByText('Overall').locator('..')).toContainText('PASS')
  await expect(page.getByText('Solid / free edges').locator('..')).toContainText('1 / 0')
  const specArtifact = page.getByRole('link', { name: 'blade_spec.json', exact: true })
  const submitted = await page.request.get(await specArtifact.getAttribute('href') ?? '')
  const builtSpec = await submitted.json()
  expect(builtSpec.chord_distribution.points.find((point: { r_over_R: number }) => point.r_over_R === .5).chord_over_R * builtSpec.diameter_mm / 2).toBeCloseTo(64, 3)
  expect(builtSpec.twist_distribution.points.find((point: { r_over_R: number }) => point.r_over_R === .65).twist_deg).toBeCloseTo(27, 3)
  await page.screenshot({ path: evidence('final_cad.png'), fullPage: true })
})
