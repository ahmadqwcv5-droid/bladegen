import { expect, type Page } from '@playwright/test'

export async function submitBuild(
  page: Page,
  buttonName: 'Generate Blade' | 'Generate Propeller',
  endpoint: '/api/build' | '/api/propellers/build',
): Promise<string> {
  const acceptedResponse = page.waitForResponse(response => (
    response.request().method() === 'POST' && response.url().endsWith(endpoint)
  ))
  await page.getByRole('button', { name: buttonName }).click()
  const response = await acceptedResponse
  expect(response.status()).toBe(202)
  const accepted = await response.json()
  expect(accepted.status).toBe('queued')
  expect(accepted.job_id).toMatch(/^[0-9a-f]{32}$/)
  return accepted.job_id as string
}

export async function waitForExactResult(
  page: Page,
  jobId: string,
  timeoutMs = 360_000,
): Promise<Record<string, unknown>> {
  const deadline = Date.now() + timeoutMs
  let last: Record<string, unknown> | undefined
  while (Date.now() < deadline) {
    const response = await page.request.get(`/api/jobs/${jobId}`)
    expect(response.ok()).toBe(true)
    last = await response.json()
    if (last.status === 'failed') {
      throw new Error(
        `Job ${jobId} failed at ${String(last.stage)}: ${String(last.error ?? last.message)}`,
      )
    }
    if (last.status === 'succeeded') {
      await expect(page.locator(`[data-result-job-id="${jobId}"]`)).toBeVisible({ timeout: 30_000 })
      return last
    }
    await page.waitForTimeout(500)
  }
  throw new Error(`Timed out waiting for exact job ${jobId}; last status: ${JSON.stringify(last)}`)
}
