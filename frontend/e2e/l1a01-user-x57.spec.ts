import { createHash } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { isDeepStrictEqual } from 'node:util'
import { expect, test } from '@playwright/test'
import { submitBuild, waitForExactResult } from './jobIdentity'

const root = path.resolve('..')
const referenceJobId = '3970dc6383f1425b9726d5a9a00f4202'
const referencePath = path.join(root, 'fixtures/reference_user_x57/blade_spec_X57.json')
const referenceJob = path.join(root, 'output/runs', referenceJobId)
const evidenceRoot = path.resolve(process.env.L1A_EVIDENCE_ROOT ?? '../qualification/l1a_01/evidence/unlabelled')
const runRoot = path.join(evidenceRoot, 'same_blade')
const sha256 = (value: Buffer) => createHash('sha256').update(value).digest('hex')

test('L1A-01 reopens the exact user X-57 JSON and generates the same blade', async ({ browser }) => {
  test.setTimeout(1_200_000)
  await mkdir(runRoot, { recursive: true })
  const context = await browser.newContext({ acceptDownloads: true })
  const page = await context.newPage()
  const suppliedBytes = await readFile(referencePath)
  const supplied = JSON.parse(suppliedBytes.toString('utf8'))
  expect(sha256(suppliedBytes)).toBe('3e63667eb208cfa1a2f60c8eec43ad4d0900ace0a351d2dc9a2c6cfffa81252a')
  const oldInput = JSON.parse(await readFile(path.join(referenceJob, 'blade_spec_input.json'), 'utf8'))
  expect(isDeepStrictEqual(supplied, oldInput)).toBe(true)
  let jobId: string | undefined
  try {
    await page.goto('/')
    await expect(page.getByText(/Canonical design preview is current/)).toBeVisible({ timeout: 30_000 })
    const fileChooser = page.waitForEvent('filechooser')
    await page.getByRole('button', { name: 'Open JSON' }).click()
    await (await fileChooser).setFiles(referencePath)
    await expect(page.getByText('Opened and validated blade_spec_X57.json')).toBeVisible({ timeout: 30_000 })
    await expect(page.getByText('Airfoil Stations (2)')).toBeVisible()
    await expect(page.getByLabel('Name', { exact: true })).toHaveValue('X57_HLP_manual_test')
    await expect(page.getByRole('button', { name: 'Single Blade' })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByText(/Canonical design preview is current/)).toBeVisible({ timeout: 30_000 })
    for (const curve of ['Chord', 'Twist', 'Rake', 'Skew']) {
      await expect(page.getByText(`${curve} (40)`)).toBeVisible()
    }
    await expect(page.getByText('Thickness (2)')).toBeVisible()
    const exportEvent = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Export JSON' }).click()
    await (await exportEvent).saveAs(path.join(runRoot, 'ui_export_before_generate.json'))
    const exported = JSON.parse(await readFile(path.join(runRoot, 'ui_export_before_generate.json'), 'utf8'))
    expect(isDeepStrictEqual(exported, supplied)).toBe(true)
    await page.screenshot({ path: path.join(runRoot, 'x57_opened_before_generate.png'), fullPage: true })

    jobId = await submitBuild(page, 'Generate Blade', '/api/build')
    expect(jobId).not.toBe(referenceJobId)
    await writeFile(path.join(runRoot, 'job_id.txt'), `${jobId}\n`)
    const status = await waitForExactResult(page, jobId, 960_000)
    expect(status.status).toBe('succeeded')
    const listedResponse = await page.request.get(`/api/jobs/${jobId}/artifacts`)
    expect(listedResponse.ok()).toBe(true)
    const listed = await listedResponse.json() as Array<{ name: string, download_url: string }>
    const required = ['blade_solid.step', 'blade_preview.stl', 'blade_spec.json', 'validation.json', 'engine_manifest.json']
    for (const name of required) {
      expect(listed.find(item => item.name === name)?.download_url).toBe(`/api/jobs/${jobId}/artifacts/${name}`)
      const link = page.getByRole('link', { name, exact: true })
      await expect(link).toHaveAttribute('href', `/api/jobs/${jobId}/artifacts/${name}`)
      const downloadEvent = page.waitForEvent('download')
      await link.click()
      await (await downloadEvent).saveAs(path.join(runRoot, name))
    }
    const validation = JSON.parse(await readFile(path.join(runRoot, 'validation.json'), 'utf8'))
    const generated = JSON.parse(await readFile(path.join(runRoot, 'blade_spec.json'), 'utf8'))
    expect(isDeepStrictEqual(generated, supplied)).toBe(true)
    expect(validation.status).toBe('PASS')
    expect(validation.geometry_validation).toMatchObject({ passed: true, station_count: 41 })
    expect(validation.geometry_validation.stations).toHaveLength(41)
    for (const station of validation.geometry_validation.stations) {
      for (const flag of ['wire_count_pass', 'wire_valid_pass', 'wire_closed_pass', 'chord_pass', 'twist_pass', 'reference_axis_pass', 'contour_rms_pass', 'contour_p95_pass', 'contour_max_pass', 'te_pass']) {
        expect(station[flag], `${flag} at r/R ${station.requested_r_over_R}`).toBe(true)
      }
      if (station.imported_profile_acceptance !== null) {
        expect(station.imported_profile_acceptance.passed).toBe(true)
      }
    }
    expect(validation.solidification.solid_after_reimport).toMatchObject({ solids: 1, shells: 1, free_edges: 0, closed_shell: true, brepcheck_valid: true })
    const manifest = JSON.parse(await readFile(path.join(runRoot, 'engine_manifest.json'), 'utf8'))
    const oldManifest = JSON.parse(await readFile(path.join(referenceJob, 'engine_manifest.json'), 'utf8'))
    expect(manifest.actually_loaded_runtime.fingerprint).toBe(oldManifest.actually_loaded_runtime.fingerprint)
    expect(manifest.implementation.source_set.aggregate_sha256).toBe(oldManifest.implementation.source_set.aggregate_sha256)
    await page.screenshot({ path: path.join(runRoot, 'x57_qualified_after_cleanup.png'), fullPage: true })
    await writeFile(path.join(runRoot, 'browser_result.json'), `${JSON.stringify({ reference_job_id: referenceJobId, job_id: jobId, input_sha256: sha256(suppliedBytes), status, required_downloads: required }, null, 2)}\n`)
  } finally {
    await context.close()
  }
})
