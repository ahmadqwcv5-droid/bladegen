import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { expect, test, type Page } from '@playwright/test'
import { submitBuild, waitForExactResult } from './jobIdentity'

const repositoryRoot = path.resolve('..')
const q02Path = path.join(repositoryRoot, 'qualification/fp02/cases/Q02.json')
const q04Path = path.join(repositoryRoot, 'qualification/fp02/cases/Q04.json')
const q04R1Path = path.join(repositoryRoot, 'qualification/fp02_c1/cases/Q04.R1.json')
const runId = process.env.FP02_EVIDENCE_RUN_ID ?? 'unlabelled-local-run'
const evidenceBase = process.env.FP02_EVIDENCE_ROOT
  ? path.resolve(process.env.FP02_EVIDENCE_ROOT)
  : path.join(repositoryRoot, 'qualification/fp02_c1/browser', runId)
const evidenceRoot = path.join(evidenceBase, 'focused_q02_q04')

async function openValidated(page: Page, file: string, name: string, stationCount: number) {
  await page.locator('input[type="file"][accept*="json"]').setInputFiles(file)
  await expect(page.getByText(`Opened and validated ${name}`)).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText(`Airfoil Stations (${stationCount})`)).toBeVisible()
  await expect(page.getByText(/Canonical design preview is current/)).toBeVisible({ timeout: 30_000 })
}

async function validationArtifact(page: Page, jobId: string) {
  const response = await page.request.get(`/api/jobs/${jobId}/artifacts/validation.json`)
  expect(response.ok()).toBe(true)
  return response.json() as Promise<Record<string, any>>
}

async function generatedSpec(page: Page, jobId: string) {
  const response = await page.request.get(`/api/jobs/${jobId}/artifacts/blade_spec.json`)
  expect(response.ok()).toBe(true)
  return response.json() as Promise<Record<string, any>>
}

test('FP02-C1 opens and generates Q02/Q04.R1 while original Q04 remains rejected', async ({ page }) => {
  test.setTimeout(1_200_000)
  await mkdir(evidenceRoot, { recursive: true })
  let buildRequests = 0
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/api/build')) buildRequests += 1
  })

  await page.goto('/')
  await expect(page.getByText(/Canonical design preview is current/)).toBeVisible({ timeout: 30_000 })

  await openValidated(page, q02Path, 'Q02.json', 5)
  const q02JobId = await submitBuild(page, 'Generate Blade', '/api/build')
  const q02Status = await waitForExactResult(page, q02JobId, 960_000)
  const q02Validation = await validationArtifact(page, q02JobId)
  expect(q02Validation.status).toBe('PASS')
  expect(q02Validation.geometry_validation).toMatchObject({ passed: true, station_count: 11 })
  expect(q02Validation.solidification.solid_after_reimport).toMatchObject({
    solids: 1, shells: 1, free_edges: 0, closed_shell: true, brepcheck_valid: true,
  })

  const requestsBeforeRejectedOpen = buildRequests
  await page.locator('input[type="file"][accept*="json"]').setInputFiles(q04Path)
  const rejection = page.locator('.project-import-errors')
  await expect(rejection).toContainText('Project import rejected. The current project was preserved.')
  await expect(rejection).toContainText('0.150000')
  await expect(rejection).toContainText('0.130553')
  expect(buildRequests).toBe(requestsBeforeRejectedOpen)
  await expect(page.getByLabel('Name', { exact: true })).toHaveValue('FP02_Q02_positive_rake_pchip')

  await openValidated(page, q04R1Path, 'Q04.R1.json', 8)
  await expect(page.locator('label').filter({ hasText: /^Rotation/ }).locator('select')).toHaveValue('reverse')
  const q04R1JobId = await submitBuild(page, 'Generate Blade', '/api/build')
  const q04R1Status = await waitForExactResult(page, q04R1JobId, 960_000)
  const q04R1Validation = await validationArtifact(page, q04R1JobId)
  const q04R1Generated = await generatedSpec(page, q04R1JobId)
  expect(q04R1Validation.status).toBe('PASS')
  expect(q04R1Validation.geometry_validation).toMatchObject({ passed: true, station_count: 26 })
  expect(q04R1Validation.solidification.solid_after_reimport).toMatchObject({
    solids: 1, shells: 1, free_edges: 0, closed_shell: true, brepcheck_valid: true,
  })
  expect(q04R1Generated.rotation_direction).toBe('reverse')
  expect(q04R1Generated.airfoil_sections).toHaveLength(8)
  expect(buildRequests).toBe(2)

  const summary = {
    schema: 'bladegen.fp02-c1.browser-focus.v1',
    evidence_run_id: runId,
    input_method: 'ordinary UI JSON file input and explicit Generate actions',
    injected_application_state: false,
    original_q04_rejected_without_build: true,
    q02: { job_id: q02JobId, status: q02Status, validation: q02Validation.geometry_validation },
    q04_r1: {
      job_id: q04R1JobId,
      status: q04R1Status,
      validation: q04R1Validation.geometry_validation,
      rotation_direction: q04R1Generated.rotation_direction,
      airfoil_station_count: q04R1Generated.airfoil_sections.length,
    },
    fixture_bytes: {
      q02: (await readFile(q02Path)).length,
      q04_original: (await readFile(q04Path)).length,
      q04_r1: (await readFile(q04R1Path)).length,
    },
  }
  await writeFile(path.join(evidenceRoot, 'summary.json'), `${JSON.stringify(summary, null, 2)}\n`)
})
