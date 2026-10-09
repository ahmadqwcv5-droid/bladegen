import { expect, test } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

const example = JSON.parse(fs.readFileSync(path.resolve('../examples/custom_multi_airfoil_finite_te.json'), 'utf8'))

const validation = {
  solidification: {
    solid_after_reimport: { solids: 1, closed_shell: true, brepcheck_valid: true, free_edges: 0, volume_mm3: 1, volume_method: 'adaptive' },
    roundtrip: { one_solid: true, volume_delta_mm3: 0 },
  },
}

test('mocked failed Job B cannot relabel successful Result A', async ({ page }) => {
  const idA = 'a'.repeat(32)
  const idB = 'b'.repeat(32)
  let builds = 0
  await page.route('**/api/examples/custom_multi_airfoil_finite_te', route => route.fulfill({ json: example }))
  await page.route('**/api/validate', route => route.fulfill({ json: { valid: true } }))
  await page.route('**/api/build', route => {
    builds += 1
    const id = builds === 1 ? idA : idB
    return route.fulfill({ json: { job_id: id, status: 'queued', stage: 'queued', stage_label: 'Queued', progress_percent: 0, message: 'Waiting', elapsed_seconds: 0 } })
  })
  await page.route('**/api/jobs/*/artifacts', route => route.fulfill({ json: [
    { name: 'validation.json', size_bytes: 1, download_url: '/mock-validation.json' },
    { name: 'blade_solid.step', size_bytes: 1, download_url: '/mock.step' },
  ] }))
  await page.route('**/mock-validation.json', route => route.fulfill({ json: validation }))
  await page.route('**/api/jobs/*', route => {
    const id = route.request().url().includes(idA) ? idA : idB
    const failed = id === idB
    return route.fulfill({ json: {
      job_id: id,
      status: failed ? 'failed' : 'succeeded',
      stage: failed ? 'openvsp' : 'complete',
      stage_label: failed ? 'Generating blade surfaces' : 'Build complete',
      progress_percent: failed ? 18 : 100,
      message: failed ? 'OpenVSP operation failed' : 'Artifacts ready',
      elapsed_seconds: 2,
      error: failed ? 'mocked OpenVSP failure' : null,
    } })
  })

  await page.goto('/')
  await page.getByRole('button', { name: 'Generate Blade' }).click()
  await expect(page.getByText(/Preview from completed job aaaaaaaa/)).toBeVisible()
  await page.getByLabel('Name').fill('blade-b')
  await page.getByRole('button', { name: 'Generate Blade' }).click()
  await expect(page.getByText(/mocked OpenVSP failure/)).toBeVisible()
  await expect(page.getByText(/Preview from completed job aaaaaaaa/)).toBeVisible()
  await expect(page.getByText(/Preview from completed job bbbbbbbb/)).toHaveCount(0)
})
