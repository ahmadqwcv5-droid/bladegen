import { expect, test, type Locator, type Page } from '@playwright/test'
import path from 'node:path'
import { submitBuild, waitForExactResult } from './jobIdentity'

const evidence = (name: string) => path.resolve('../docs/screenshots/patch03a1', name)
const sparseFixture = path.resolve('../backend/tests/fixtures/airfoils/independent_cambered_finite_te.dat')
const acceptedFixture = path.resolve('../backend/tests/fixtures/airfoils/independent_analytic_finite_te.dat')

async function hoverAtSvgX(page: Page, chart: Locator, x: number) {
  await chart.scrollIntoViewIfNeeded()
  const point = await chart.evaluate((element, svgX) => {
    const svg = element as SVGSVGElement
    const source = svg.createSVGPoint()
    source.x = svgX
    source.y = 120
    const screen = source.matrixTransform(svg.getScreenCTM()!)
    return { x: screen.x, y: screen.y }
  }, x)
  await page.mouse.move(point.x, point.y)
}

async function verifyInspectorGeometry(plot: Locator) {
  const result = await plot.evaluate(element => {
    const svg = element as SVGSVGElement
    const upper = svg.querySelector<SVGPolylineElement>('.airfoil-upper')!
    const lower = svg.querySelector<SVGPolylineElement>('.airfoil-lower')!
    const matrix = svg.getScreenCTM()!
    return {
      upperStroke: Number.parseFloat(getComputedStyle(upper).strokeWidth),
      lowerStroke: Number.parseFloat(getComputedStyle(lower).strokeWidth),
      upperLength: upper.getTotalLength(),
      lowerLength: lower.getTotalLength(),
      scaleX: Math.hypot(matrix.a, matrix.b),
      scaleY: Math.hypot(matrix.c, matrix.d),
    }
  })
  expect(result.upperStroke).toBeGreaterThanOrEqual(1.5)
  expect(result.lowerStroke).toBeGreaterThanOrEqual(1.5)
  expect(result.upperLength).toBeGreaterThan(0)
  expect(result.lowerLength).toBeGreaterThan(0)
  expect(Math.abs(result.scaleX - result.scaleY)).toBeLessThan(1e-7)
}

test('Patch 03A.1 visual accuracy, hover mapping, warnings, and real STEP', async ({ page }) => {
  test.setTimeout(720_000)
  await page.goto('/')
  await expect(page.getByText('Airfoil Stations (5)')).toBeVisible()

  for (const code of ['0012', '2412', '4412']) {
    await page.getByRole('button', { name: 'Choose from Library' }).nth(2).click()
    const dialog = page.getByRole('dialog', { name: 'Airfoil Library for station 3' })
    await dialog.getByLabel('Direct NACA code').fill(code)
    await dialog.getByRole('button', { name: 'Preview NACA' }).click()
    const sourcePlot = dialog.getByRole('img', { name: new RegExp(`NACA ${code} source airfoil coordinates`) })
    await expect(sourcePlot).toBeVisible({ timeout: 30_000 })
    await verifyInspectorGeometry(sourcePlot)
    await dialog.getByRole('button', { name: 'Apply to Station 3' }).click()
    const resolvedPlot = page.getByRole('img', { name: new RegExp(`NACA ${code}.*resolved airfoil coordinates`) })
    await expect(resolvedPlot).toBeVisible({ timeout: 30_000 })
    await verifyInspectorGeometry(resolvedPlot)
    await page.getByRole('button', { name: 'Source Profile' }).click()
    await expect(page.getByRole('img', { name: new RegExp(`NACA ${code}.*source airfoil coordinates`) })).toBeVisible()
    await page.getByRole('button', { name: 'Resolved Design Profile' }).click()
  }

  const inspector = page.getByLabel('2D Airfoil Inspector')
  await inspector.screenshot({ path: evidence('after_visible_naca_4412.png') })
  await page.setViewportSize({ width: 520, height: 850 })
  await verifyInspectorGeometry(page.getByRole('img', { name: /NACA 4412.*resolved airfoil coordinates/ }))
  await inspector.screenshot({ path: evidence('narrow_visible_inspector.png') })
  await page.setViewportSize({ width: 1280, height: 900 })

  const chart = page.getByRole('img', { name: /Chord Distribution canonical pchip distribution in mm/ })
  await expect(chart).toBeVisible()
  await hoverAtSvgX(page, chart, 58)
  await expect(page.locator('.chart-readout')).toContainText('r/R 0.2000')
  await hoverAtSvgX(page, chart, 340)
  await expect(page.locator('.chart-readout')).toContainText('r/R 0.6000')
  await hoverAtSvgX(page, chart, 622)
  await expect(page.locator('.chart-readout')).toContainText('r/R 1.0000')
  await page.locator('.distribution-visual').screenshot({ path: evidence('correct_hover_readout.png') })

  await page.getByLabel('Chord interpolation').selectOption('linear')
  const linearChart = page.getByRole('img', { name: /Chord Distribution canonical linear distribution in mm/ })
  await hoverAtSvgX(page, linearChart, 58)
  await expect(page.locator('.chart-readout')).toContainText('r/R 0.2000')
  await hoverAtSvgX(page, linearChart, 622)
  await expect(page.locator('.chart-readout')).toContainText('r/R 1.0000')
  await page.setViewportSize({ width: 520, height: 850 })
  await hoverAtSvgX(page, linearChart, 58)
  await expect(page.locator('.chart-readout')).toContainText('r/R 0.2000')
  await hoverAtSvgX(page, linearChart, 622)
  await expect(page.locator('.chart-readout')).toContainText('r/R 1.0000')
  await page.setViewportSize({ width: 1280, height: 900 })

  for (const [tab, unit] of [['Twist', 'deg'], ['Rake', 'mm'], ['Skew', 'mm'], ['Thickness', '% t/c']] as const) {
    await page.getByRole('button', { name: tab, exact: true }).click()
    const unitChart = page.getByRole('img', { name: new RegExp(`${tab} Distribution canonical .* distribution in ${unit.replace('%', '\\%')}`) })
    await hoverAtSvgX(page, unitChart, 340)
    await expect(page.locator('.chart-readout')).toContainText(unit)
  }

  await page.setViewportSize({ width: 1280, height: 900 })
  await page.getByRole('button', { name: 'Choose from Library' }).nth(2).click()
  let dialog = page.getByRole('dialog', { name: 'Airfoil Library for station 3' })
  await dialog.getByText('Import DAT or CSV').click()
  await dialog.getByLabel('Airfoil coordinate file').setInputFiles(sparseFixture)
  await dialog.getByLabel('Imported airfoil name').fill('Sparse five-point profile')
  await dialog.getByRole('button', { name: 'Import and Preview' }).click()
  const warning = dialog.getByRole('status', { name: 'Coordinate profile quality warning' })
  await expect(warning).toContainText('Upper surface5 points', { timeout: 30_000 })
  await expect(warning).toContainText('Maximum chordwise spacing0.2500 c')
  await dialog.screenshot({ path: evidence('sparse_profile_warning.png') })
  await dialog.getByRole('button', { name: 'Apply to Station 3' }).click()
  await expect(page.getByRole('status', { name: 'Coordinate profile quality warning' })).toBeVisible({ timeout: 30_000 })

  await page.getByRole('button', { name: 'Choose from Library' }).nth(2).click()
  dialog = page.getByRole('dialog', { name: 'Airfoil Library for station 3' })
  await dialog.getByText('Import DAT or CSV').click()
  await dialog.getByLabel('Airfoil coordinate file').setInputFiles(acceptedFixture)
  await dialog.getByLabel('Imported airfoil name').fill('Accepted 41-point analytic profile')
  await dialog.getByRole('button', { name: 'Import and Preview' }).click()
  await expect(dialog.getByText(/natural geometric t\/c/)).toBeVisible({ timeout: 30_000 })
  await expect(dialog.getByRole('status', { name: 'Coordinate profile quality warning' })).toHaveCount(0)
  await verifyInspectorGeometry(dialog.getByRole('img', { name: /Accepted 41-point analytic profile source airfoil coordinates/ }))
  await dialog.getByRole('button', { name: 'Apply to Station 3' }).click()
  await expect(page.getByRole('img', { name: /Imported coordinate profile.*resolved airfoil coordinates/ })).toBeVisible({ timeout: 30_000 })

  const jobId = await submitBuild(page, 'Generate Blade', '/api/build')
  await waitForExactResult(page, jobId)
  await expect(page.getByText('Overall').locator('..')).toContainText('PASS')
  await expect(page.getByText('Solid / free edges').locator('..')).toContainText('1 / 0')
  await expect(page.getByRole('link', { name: 'blade_solid.step' })).toBeVisible()
  await page.screenshot({ path: evidence('accepted_imported_step_pass.png'), fullPage: true })
})
