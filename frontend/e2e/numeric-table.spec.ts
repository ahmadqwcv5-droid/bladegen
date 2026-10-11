import { expect, test } from '@playwright/test'

test('distribution numbers remain readable and scroll locally on a narrow screen', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')

  const radius = page.getByLabel('Chord radius 1')
  await expect(radius).toHaveValue('0.2')
  await expect(radius).toBeVisible()

  const inputWidth = await radius.evaluate(element => element.getBoundingClientRect().width)
  expect(inputWidth).toBeGreaterThanOrEqual(104)

  const scroller = page.locator('.distribution-table-scroll').first()
  await expect(scroller).toBeVisible()
  const dimensions = await scroller.evaluate(element => ({
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth,
    overflowX: getComputedStyle(element).overflowX,
  }))
  expect(dimensions.overflowX).toBe('auto')
  expect(dimensions.scrollWidth).toBeGreaterThanOrEqual(dimensions.clientWidth)
})
