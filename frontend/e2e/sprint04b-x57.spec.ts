import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { copyFile, mkdir, readFile, stat, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { isDeepStrictEqual } from 'node:util'
import { expect, test, type Page, type Request, type Response } from '@playwright/test'
import { submitBuild } from './jobIdentity'
import type { BladeSpec } from '../src/types/bladespec'
import {
  X57_FIXTURE_DIR,
  loadX57FixtureData,
  percentile,
  verifyX57ExportedCandidate,
} from './x57Evidence'

const evidenceRoot = path.resolve('../docs/evidence/sprint04b/x57')
const runRoot = path.resolve('../output/runs')
const airfoilPath = path.join(X57_FIXTURE_DIR, 'x57_hlp_airfoil.csv')
const distributionPath = path.join(X57_FIXTURE_DIR, 'x57_hlp_control_points_mm.csv')

type JsonObject = Record<string, unknown>
type JobStatus = JsonObject & {
  job_id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  stage?: string
  error?: string | null
  elapsed_seconds?: number
}

type OperationRequestCounts = {
  validate: number
  preview: number
  build: number
}

type ApplyMeasurement = {
  latency_ms: number
  request_counts: OperationRequestCounts
}

const asObject = (value: unknown): JsonObject | undefined => (
  typeof value === 'object' && value !== null && !Array.isArray(value)
    ? value as JsonObject
    : undefined
)

const asArray = (value: unknown): unknown[] => Array.isArray(value) ? value : []

const requestJson = (response: Response): unknown => {
  try { return response.request().postDataJSON() }
  catch { return undefined }
}

const hasX57Globals = (value: unknown): boolean => {
  const spec = asObject(value)
  return Boolean(
    spec
    && spec.name === 'X57_HLP_manual_test'
    && spec.diameter_mm === 575.9200184294399
    && spec.root_radius_ratio === 0.20238
    && spec.reference_axis_x_over_c === 0.5
    && spec.rotation_direction === 'normal',
  )
}

const hasX57Profile = (value: unknown): boolean => {
  if (!hasX57Globals(value)) return false
  const spec = asObject(value)!
  const sections = asArray(spec.airfoil_sections).map(asObject)
  const thickness = asObject(spec.thickness_distribution)
  const thicknessPoints = asArray(thickness?.points).map(asObject)
  return Boolean(
    sections.length === 2
    && sections[0]?.r_over_R === 0.20238
    && sections[1]?.r_over_R === 1
    && sections.every(section => {
      const airfoil = asObject(section?.airfoil)
      return section?.trailing_edge_thickness_mm === 0
        && airfoil?.type === 'coordinates'
        && asArray(airfoil.upper).length === 74
        && asArray(airfoil.lower).length === 67
    })
    && thickness?.interpolation === 'linear'
    && thicknessPoints.length === 2
    && thicknessPoints[0]?.thickness_ratio === 0.1305533776828919
    && thicknessPoints[1]?.thickness_ratio === 0.1305533776828919,
  )
}

const hasX57Distributions = (value: unknown): boolean => {
  if (!hasX57Profile(value)) return false
  const spec = asObject(value)!
  for (const key of [
    'chord_distribution',
    'twist_distribution',
    'rake_distribution',
    'skew_distribution',
  ]) {
    const distribution = asObject(spec[key])
    const points = asArray(distribution?.points).map(asObject)
    if (distribution?.interpolation !== 'pchip' || points.length !== 40) return false
    if (points[0]?.r_over_R !== 0.20238 || points[39]?.r_over_R !== 1) return false
  }
  return true
}

const matchesPost = (
  response: Response,
  endpoint: '/api/validate' | '/api/design-preview',
  predicate: (value: unknown) => boolean,
): boolean => response.request().method() === 'POST'
  && response.url().endsWith(endpoint)
  && predicate(requestJson(response))

async function waitForCurrentPreview(page: Page) {
  await expect(page.getByText(/Canonical design preview is current/)).toBeVisible({ timeout: 30_000 })
}

async function commitThroughBackend(
  page: Page,
  action: () => Promise<void>,
  predicate: (value: unknown) => boolean,
) {
  const validationPromise = page.waitForResponse(response => matchesPost(response, '/api/validate', predicate))
  const previewPromise = page.waitForResponse(response => matchesPost(response, '/api/design-preview', predicate))
  await action()
  const validation = await validationPromise
  expect(validation.ok()).toBe(true)
  const preview = await previewPromise
  expect(preview.ok()).toBe(true)
  await waitForCurrentPreview(page)
  return { validation, preview }
}

async function setNumeric(page: Page, label: string, value: string) {
  const input = page.getByLabel(label, { exact: true })
  await input.fill(value)
  await input.blur()
}

async function reviewX57Distributions(page: Page, assertFullReview = false) {
  await page.getByRole('button', { name: 'Import Distributions' }).click()
  const dialog = page.getByRole('dialog', { name: 'Import Distributions' })
  await dialog.getByLabel('Distribution CSV file').setInputFiles(distributionPath)
  await expect(dialog.getByText('x57_hlp_control_points_mm.csv', { exact: true })).toBeVisible()
  await expect(dialog.getByText('40 rows', { exact: true })).toBeVisible()
  await expect(dialog.getByText(/Diameter snapshot: 575\.9200184294399 mm/)).toBeVisible()
  if (assertFullReview) {
    await expect(dialog.getByLabel('Radial column')).toHaveValue('r_over_R')
    const expected = {
      Chord: ['chord_mm', 'mm'],
      Twist: ['twist_deg', 'deg'],
      Rake: ['rake_mm', 'mm'],
      Skew: ['skew_mm', 'mm'],
    } as const
    for (const [curve, [column, unit]] of Object.entries(expected)) {
      await expect(dialog.getByLabel(`${curve} source column`)).toHaveValue(column)
      await expect(dialog.getByLabel(`${curve} import units`)).toHaveValue(unit)
      await expect(dialog.getByLabel(`${curve} import interpolation`)).toHaveValue('pchip')
    }
    await expect(dialog.getByLabel('Thickness source column')).toHaveValue('')
    await expect(dialog.getByText(/row is not mapped to BladeSpec/)).toBeVisible()
    await expect(dialog.getByText(/radial domain 0\.20238 to 1/)).toBeVisible()
    await expect(dialog.getByText(/airfoil stations remain 2/)).toBeVisible()
    await expect(dialog.getByText(/Thickness unchanged/)).toBeVisible()
  }
  return dialog
}

const countEngineeringRequest = (counts: OperationRequestCounts, request: Request) => {
  if (request.method() !== 'POST') return
  if (request.url().endsWith('/api/validate')) counts.validate += 1
  else if (request.url().endsWith('/api/design-preview')) counts.preview += 1
  else if (request.url().endsWith('/api/build')) counts.build += 1
}

async function applyReviewedDistributions(page: Page, assertFullReview = false): Promise<ApplyMeasurement> {
  const dialog = await reviewX57Distributions(page, assertFullReview)
  const validationPromise = page.waitForResponse(response => (
    matchesPost(response, '/api/validate', hasX57Distributions)
  ))
  const previewPromise = page.waitForResponse(response => (
    matchesPost(response, '/api/design-preview', hasX57Distributions)
  ))
  const counts: OperationRequestCounts = { validate: 0, preview: 0, build: 0 }
  const countRequest = (request: Request) => countEngineeringRequest(counts, request)
  page.on('request', countRequest)
  const apply = dialog.getByRole('button', { name: 'Apply Once' })
  await apply.evaluate(button => {
    const timedWindow = window as typeof window & { __x57ApplyClickAt?: number }
    delete timedWindow.__x57ApplyClickAt
    button.addEventListener('click', () => { timedWindow.__x57ApplyClickAt = performance.now() }, {
      capture: true,
      once: true,
    })
  })
  try {
    await apply.click()
    const validation = await validationPromise
    expect(validation.ok()).toBe(true)
    const preview = await previewPromise
    expect(preview.ok()).toBe(true)
    await waitForCurrentPreview(page)
    const latency = await page.evaluate(() => {
      const timedWindow = window as typeof window & { __x57ApplyClickAt?: number }
      if (timedWindow.__x57ApplyClickAt === undefined) throw new Error('Apply click timestamp was not captured')
      return performance.now() - timedWindow.__x57ApplyClickAt
    })
    return { latency_ms: latency, request_counts: counts }
  } finally {
    page.off('request', countRequest)
  }
}

async function undoDistributionApply(page: Page): Promise<OperationRequestCounts> {
  const previewPromise = page.waitForResponse(response => (
    matchesPost(response, '/api/design-preview', value => {
      if (!hasX57Profile(value) || hasX57Distributions(value)) return false
      const spec = asObject(value)!
      return asArray(asObject(spec.chord_distribution)?.points).length === 6
    })
  ))
  const counts: OperationRequestCounts = { validate: 0, preview: 0, build: 0 }
  const countRequest = (request: Request) => countEngineeringRequest(counts, request)
  page.on('request', countRequest)
  try {
    await page.getByRole('button', { name: 'Undo curve edit' }).click()
    expect((await previewPromise).ok()).toBe(true)
    await expect(page.getByText('Chord (6)')).toBeVisible()
    await waitForCurrentPreview(page)
    return counts
  } finally {
    page.off('request', countRequest)
  }
}

async function waitForTerminalJob(page: Page, jobId: string): Promise<JobStatus> {
  const deadline = Date.now() + 600_000
  let last: JobStatus | undefined
  while (Date.now() < deadline) {
    const response = await page.request.get(`/api/jobs/${jobId}`)
    expect(response.ok()).toBe(true)
    last = await response.json() as JobStatus
    expect(last.job_id).toBe(jobId)
    if (last.status === 'succeeded' || last.status === 'failed') return last
    await page.waitForTimeout(500)
  }
  throw new Error(`Timed out waiting for X-57 job ${jobId}; last state ${JSON.stringify(last)}`)
}

async function copyIfPresent(source: string, destination: string): Promise<string | undefined> {
  try {
    await stat(source)
    await copyFile(source, destination)
    return path.basename(destination)
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return undefined
    throw error
  }
}

const sha256 = async (filename: string): Promise<string> => (
  createHash('sha256').update(await readFile(filename)).digest('hex')
)

test('real X-57 fixtures flow through reviewed UI input, export, and explicit blade generation', async ({ page }) => {
  test.setTimeout(900_000)
  const fixture = await loadX57FixtureData()
  await mkdir(evidenceRoot, { recursive: true })
  await page.setViewportSize({ width: 1440, height: 1000 })
  let buildRequests = 0
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/api/build')) buildRequests += 1
  })

  await page.goto('/')
  await expect(page.getByText('Airfoil Stations (5)')).toBeVisible({ timeout: 30_000 })
  await waitForCurrentPreview(page)
  await expect(page.getByRole('button', { name: 'Single Blade' })).toHaveAttribute('aria-pressed', 'true')

  await page.getByLabel('Name', { exact: true }).fill('X57_HLP_manual_test')
  await setNumeric(page, 'Diameter', '575.9200184294399')
  await setNumeric(page, 'Root radius', '0.20238')
  const globalPreview = page.waitForResponse(response => (
    matchesPost(response, '/api/design-preview', hasX57Globals)
  ))
  await setNumeric(page, 'Reference axis', '0.5')
  await page.locator('label').filter({ hasText: /^Rotation/ }).locator('select').selectOption('normal')
  expect((await globalPreview).ok()).toBe(true)
  await waitForCurrentPreview(page)

  await page.getByRole('button', { name: 'Set Up Airfoil Stations' }).click()
  const setup = page.getByRole('dialog', { name: 'Set Up Airfoil Stations' })
  await setup.getByLabel('Total airfoil stations').fill('2')
  await setup.getByLabel('Common station trailing edge').fill('0')
  await expect(setup.getByLabel(/Preserve complete assignments/)).not.toBeChecked()
  await expect(setup.getByLabel(/Replace Thickness with a reviewed two-point constant/)).not.toBeChecked()
  await commitThroughBackend(page, async () => {
    await setup.getByRole('button', { name: 'Apply Once' }).click()
  }, value => {
    if (!hasX57Globals(value)) return false
    const sections = asArray(asObject(value)?.airfoil_sections).map(asObject)
    return sections.length === 2
      && sections[0]?.r_over_R === 0.20238
      && sections[1]?.r_over_R === 1
      && sections.every(section => section?.trailing_edge_thickness_mm === 0)
  })
  await expect(page.getByText('Airfoil Stations (2)')).toBeVisible()

  await page.getByLabel('Select airfoil station 1').check()
  await page.getByLabel('Select airfoil station 2').check()
  await page.getByRole('button', { name: 'Apply Profile to Selected Stations' }).click()
  const selector = page.getByRole('dialog', { name: 'Airfoil Library for 2 selected stations' })
  await selector.locator('summary', { hasText: 'Import DAT or CSV' }).click()
  await selector.getByLabel('Airfoil coordinate file').setInputFiles(airfoilPath)
  await selector.getByLabel('Imported airfoil name').fill('X-57 HLP source profile')
  await selector.getByLabel('Airfoil source').fill('Official NASA X-57 Maxwell CRM v4.4.1 source extraction; see fixture manifest')
  await selector.getByLabel('Airfoil notes').fill('Sprint 04B real-fixture UI qualification; source coordinates preserved')
  await expect(selector.getByLabel(/Explicitly normalize using LE and mean TE chord/)).not.toBeChecked()
  const importResponsePromise = page.waitForResponse(response => (
    response.request().method() === 'POST' && response.url().includes('/api/airfoils/import?')
  ))
  await selector.getByRole('button', { name: 'Import and Preview' }).click()
  const importResponse = await importResponsePromise
  expect(importResponse.status()).toBe(201)
  const canonicalCoordinateSha = '68e77ce5d0623afe72de6cc14ab9de7f17002c93efcdb6ca1efa2e9f30ea8cb2'
  await expect(selector.getByText(canonicalCoordinateSha)).toBeVisible()
  const importedProfileResponse = await page.request.get(
    '/api/airfoils/imported-ae38d1a5283c-68e77ce5',
  )
  expect(importedProfileResponse.ok()).toBe(true)
  const importedProfile = await importedProfileResponse.json() as JsonObject
  expect(importedProfile).toMatchObject({
    profile_id: 'imported-ae38d1a5283c-68e77ce5',
    original_sha256: 'ae38d1a5283c9bb61bcda9ef53c1a62c0f05eb32dd6b32609ef7c7d44db26238',
    canonical_coordinate_sha256: '68e77ce5d0623afe72de6cc14ab9de7f17002c93efcdb6ca1efa2e9f30ea8cb2',
    point_counts: { upper: 74, lower: 67 },
    normalization: 'preserved normalized source coordinates',
  })
  expect(asObject(importedProfile.metrics)?.max_thickness_ratio).toBe(0.1305533776828919)
  expect(importedProfile.canonical_coordinate_sha256).toBe(canonicalCoordinateSha)
  await selector.getByLabel('Use constant thickness for selected common profile').check()
  await commitThroughBackend(page, async () => {
    await selector.getByRole('button', { name: 'Apply to 2 Selected Stations' }).click()
  }, hasX57Profile)
  await expect(page.getByText('Thickness (2)')).toBeVisible()
  await expect(page.getByRole('status', { name: 'Design coordinate diagnostic summary' })).toHaveCount(0)

  const buildRequestsBeforeApplyQualification = buildRequests
  const cold = await applyReviewedDistributions(page, true)
  const warm: ApplyMeasurement[] = []
  const undoRequestCounts: OperationRequestCounts[] = []
  for (let repetition = 0; repetition < 20; repetition += 1) {
    undoRequestCounts.push(await undoDistributionApply(page))
    warm.push(await applyReviewedDistributions(page))
  }
  expect(warm).toHaveLength(20)
  const warmMs = warm.map(measurement => measurement.latency_ms)
  expect(buildRequests).toBe(buildRequestsBeforeApplyQualification)
  for (const curve of ['Chord', 'Twist', 'Rake', 'Skew']) {
    await expect(page.getByText(`${curve} (40)`)).toBeVisible()
  }
  await expect(page.getByText('Thickness (2)')).toBeVisible()
  await page.screenshot({ path: path.join(evidenceRoot, 'x57_candidate_current.png'), fullPage: true })

  const exportDownload = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export JSON' }).click()
  const download = await exportDownload
  expect(download.suggestedFilename()).toBe('X57_HLP_manual_test.json')
  const exportedCandidatePath = path.join(evidenceRoot, 'exported_candidate.json')
  await download.saveAs(exportedCandidatePath)
  const exportedCandidate = JSON.parse(await readFile(exportedCandidatePath, 'utf8')) as BladeSpec
  const inputFidelity = verifyX57ExportedCandidate(exportedCandidate, fixture)

  const jobId = await submitBuild(page, 'Generate Blade', '/api/build')
  expect(buildRequests).toBe(buildRequestsBeforeApplyQualification + 1)
  const terminalJob = await waitForTerminalJob(page, jobId)
  const jobEvidenceRoot = path.join(evidenceRoot, 'job')
  await mkdir(jobEvidenceRoot, { recursive: true })
  const sourceJobRoot = path.join(runRoot, jobId)
  const retained = (await Promise.all([
    copyIfPresent(path.join(sourceJobRoot, 'blade_spec_input.json'), path.join(jobEvidenceRoot, 'submitted_blade_spec.json')),
    copyIfPresent(path.join(sourceJobRoot, 'blade_spec.json'), path.join(jobEvidenceRoot, 'blade_spec.json')),
    copyIfPresent(path.join(sourceJobRoot, 'validation.json'), path.join(jobEvidenceRoot, 'validation.json')),
    copyIfPresent(path.join(sourceJobRoot, 'blade_solid.step'), path.join(jobEvidenceRoot, 'blade_solid.step')),
    copyIfPresent(path.join(sourceJobRoot, 'progress.json'), path.join(jobEvidenceRoot, 'progress.json')),
    copyIfPresent(path.join(sourceJobRoot, 'build_stdout.log'), path.join(jobEvidenceRoot, 'build_stdout.log')),
    copyIfPresent(path.join(sourceJobRoot, 'build_stderr.log'), path.join(jobEvidenceRoot, 'build_stderr.log')),
  ])).filter((name): name is string => Boolean(name))

  let validation: JsonObject | undefined
  let artifactNames: string[] = []
  let artifactsApiOk = false
  let requiredArtifactsPresent = false
  let requiredArtifactDownloadsOk = false
  let submittedSpecMatchesExport = false
  let generatedSpecMatchesExport = false
  let resultIdentityVisible = false
  if (retained.includes('submitted_blade_spec.json')) {
    const submitted = JSON.parse(await readFile(path.join(jobEvidenceRoot, 'submitted_blade_spec.json'), 'utf8'))
    submittedSpecMatchesExport = isDeepStrictEqual(submitted, exportedCandidate)
  }
  if (retained.includes('blade_spec.json')) {
    const generatedSpec = JSON.parse(await readFile(path.join(jobEvidenceRoot, 'blade_spec.json'), 'utf8'))
    generatedSpecMatchesExport = isDeepStrictEqual(generatedSpec, exportedCandidate)
  }
  if (retained.includes('validation.json')) {
    validation = JSON.parse(await readFile(path.join(jobEvidenceRoot, 'validation.json'), 'utf8')) as JsonObject
  }
  if (terminalJob.status === 'succeeded') {
    const artifactsResponse = await page.request.get(`/api/jobs/${jobId}/artifacts`)
    artifactsApiOk = artifactsResponse.ok()
    const artifacts = artifactsApiOk
      ? await artifactsResponse.json() as Array<{ name: string; download_url: string }>
      : []
    artifactNames = artifacts.map(artifact => artifact.name)
    const requiredArtifactNames = ['blade_spec.json', 'validation.json', 'blade_solid.step']
    requiredArtifactsPresent = requiredArtifactNames.every(name => artifactNames.includes(name))
    const downloadChecks: boolean[] = []
    for (const artifact of artifacts.filter(item => requiredArtifactNames.includes(item.name))) {
      const expectedUrl = `/api/jobs/${jobId}/artifacts/${artifact.name}`
      downloadChecks.push(
        artifact.download_url === expectedUrl
        && (await page.request.get(artifact.download_url)).ok(),
      )
    }
    requiredArtifactDownloadsOk = downloadChecks.length === requiredArtifactNames.length
      && downloadChecks.every(Boolean)
    resultIdentityVisible = await page.locator(`[data-result-job-id="${jobId}"]`)
      .waitFor({ state: 'visible', timeout: 30_000 })
      .then(() => true, () => false)
    if (resultIdentityVisible) {
      await page.screenshot({ path: path.join(evidenceRoot, 'x57_qualified_blade.png'), fullPage: true })
    }
  }

  const warmP95 = percentile(warmMs, 0.95)
  const latencyTargetMs = 1000
  const latencyPassed = warmP95 <= latencyTargetMs
  const applyMeasurements = [cold, ...warm]
  const applyRequestContractPassed = applyMeasurements.every(measurement => (
    measurement.request_counts.validate === 1
    && measurement.request_counts.preview === 1
    && measurement.request_counts.build === 0
  ))
  const undoRequestContractPassed = undoRequestCounts.every(counts => (
    counts.validate === 0 && counts.preview === 1 && counts.build === 0
  ))
  const solid = asObject(asObject(validation?.solidification)?.solid_after_reimport)
  const topologyPassed = solid?.solids === 1
    && solid.closed_shell === true
    && solid.brepcheck_valid === true
    && solid.free_edges === 0
  const internalValidationPassed = validation?.status === 'PASS'
    && topologyPassed
    && asObject(validation.geometry_validation)?.passed === true
  const repositoryRoot = path.resolve('..')
  const baseCommit = execFileSync('git', ['rev-parse', 'HEAD'], {
    cwd: repositoryRoot,
    encoding: 'utf8',
  }).trim()
  const workingTreeStatus = execFileSync('git', ['status', '--short'], {
    cwd: repositoryRoot,
    encoding: 'utf8',
  }).trimEnd()
  const trackedPatch = execFileSync('git', ['diff', '--binary', 'HEAD', '--'], {
    cwd: repositoryRoot,
    encoding: 'utf8',
    maxBuffer: 20 * 1024 * 1024,
  })
  const summary = {
    evidence_schema: 'bladegen.sprint04b.x57-closure.v1',
    tested_source_identity: {
      base_commit: baseCommit,
      worktree_clean: workingTreeStatus.length === 0,
      git_status_porcelain: workingTreeStatus,
      tracked_patch_sha256: createHash('sha256').update(trackedPatch).digest('hex'),
      x57_test_source_sha256: await sha256(path.resolve('e2e/sprint04b-x57.spec.ts')),
      x57_evidence_helper_sha256: await sha256(path.resolve('e2e/x57Evidence.ts')),
    },
    generated_at_utc: new Date().toISOString(),
    workflow: {
      input_method: 'real UI controls and supplied CSV file inputs',
      prepared_bladespec_injected: false,
      explicit_generate_count: buildRequests,
    },
    apply_to_current_preview_latency_ms: {
      definition: 'Actual browser Apply Once click event through matching successful /api/validate and /api/design-preview responses and current-preview UI state',
      target_ms: latencyTargetMs,
      acceptance_criterion: 'warm p95 <= target_ms',
      passed: latencyPassed,
      cold,
      warm_repetitions: warmMs.length,
      warm_operations: warm,
      warm_median: percentile(warmMs, 0.5),
      warm_p95: warmP95,
      warm_max: Math.max(...warmMs),
      apply_request_contract: {
        expected_per_operation: { validate: 1, preview: 1, build: 0 },
        passed: applyRequestContractPassed,
      },
      undo_cycles: {
        count: undoRequestCounts.length,
        request_counts: undoRequestCounts,
        expected_per_operation: { validate: 0, preview: 1, build: 0 },
        passed: undoRequestContractPassed,
      },
    },
    input_fidelity: inputFidelity,
    thickness_representation: {
      source_ratio: 0.1305067267946498,
      product_coordinate_measurement_ratio: 0.1305533776828919,
      ratio_delta: 0.000046650888242100175,
      percentage_point_delta: 0.0046650888242100175,
      status: 'DOCUMENTED_REPRESENTATION_DIFFERENCE',
    },
    generation: {
      job_id: jobId,
      status: terminalJob.status,
      stage: terminalJob.stage,
      error: terminalJob.error ?? null,
      elapsed_seconds: terminalJob.elapsed_seconds,
      api_artifacts: artifactNames,
      artifacts_api_ok: artifactsApiOk,
      required_artifacts_present: requiredArtifactsPresent,
      required_artifact_downloads_ok: requiredArtifactDownloadsOk,
      retained_files: retained,
      submitted_spec_matches_exported_candidate: submittedSpecMatchesExport,
      generated_blade_spec_matches_exported_candidate: generatedSpecMatchesExport,
      exact_result_identity_visible: resultIdentityVisible,
      submitted_spec_sha256: retained.includes('submitted_blade_spec.json')
        ? await sha256(path.join(jobEvidenceRoot, 'submitted_blade_spec.json'))
        : null,
      step_sha256: retained.includes('blade_solid.step')
        ? await sha256(path.join(jobEvidenceRoot, 'blade_solid.step'))
        : null,
      internal_validation: validation ?? null,
    },
    external_nasa_geometry_fidelity: {
      status: 'UNVERIFIED',
      reason: 'The supplied fixture bundle contains source-derived inputs and a recorded official-model URL/hash, but no official NASA VSP3/STEP geometry for an external surface comparison.',
    },
  }
  await writeFile(path.join(evidenceRoot, 'evidence_summary.json'), `${JSON.stringify(summary, null, 2)}\n`, 'utf8')

  expect(latencyPassed, `Warm Apply-to-current-preview p95 ${warmP95} ms exceeded ${latencyTargetMs} ms`).toBe(true)
  expect(applyRequestContractPassed, 'Each Apply must issue exactly one validation, one preview, and zero builds').toBe(true)
  expect(undoRequestContractPassed, 'Each Undo must issue one preview and no validation/build request').toBe(true)
  expect(
    terminalJob.status,
    `X-57 CAD job ${jobId} genuinely failed; retained evidence: ${JSON.stringify({ stage: terminalJob.stage, error: terminalJob.error, retained })}`,
  ).toBe('succeeded')
  expect(artifactsApiOk).toBe(true)
  expect(requiredArtifactsPresent).toBe(true)
  expect(requiredArtifactDownloadsOk).toBe(true)
  expect(submittedSpecMatchesExport).toBe(true)
  expect(generatedSpecMatchesExport).toBe(true)
  expect(internalValidationPassed).toBe(true)
  expect(resultIdentityVisible).toBe(true)
})
