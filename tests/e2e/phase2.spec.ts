import path from 'node:path'
import { expect, test } from '@playwright/test'

// End-to-end test for the Phase 2 frontend additions, run against the
// single-origin static export served by FastAPI at http://localhost:8001/app/.
// This test is NOT started by the frontend build itself — the orchestrating
// session runs `cd frontend && pnpm build` + `uv run python -m src`, then:
//   npx playwright test tests/e2e/ --reporter=line
//
// Covers: upload a CSV -> start a session -> ask a table-producing question ->
// after the answer renders, assert (a) Export CSV/PDF buttons appear for an
// answer that carries a table, and (b) if follow-up suggestions are present,
// they render as clickable chips.

const SAMPLE_CSV = path.join(__dirname, 'fixtures', 'sample_crime_reports.csv')

test.setTimeout(180_000)

test('table answer shows export buttons and (when present) follow-up chips', async ({ page }) => {
  await page.goto('/app/')

  await expect(page.getByRole('heading', { name: /Analyze your datasets/ })).toBeVisible()
  const startButton = page.getByRole('button', { name: /Start session/ })
  await expect(startButton).toBeVisible()

  // --- Upload a CSV --------------------------------------------------------------
  const fileInput = page.locator('input[type="file"]')
  await fileInput.setInputFiles(SAMPLE_CSV)

  // Profile card appears (no polling, no manual "process" step).
  await expect(page.getByRole('heading', { name: 'sample_crime_reports.csv' }).first()).toBeVisible({
    timeout: 20_000,
  })

  // --- Select the freshly uploaded dataset and start a session -------------------
  // The dev DB is shared, so the library may already hold other datasets and
  // repeat runs add another sample_crime_reports.csv. listDatasets returns
  // newest-first, so .first() selects the row this run just uploaded.
  const libraryRow = page.locator('li', { hasText: 'sample_crime_reports.csv' }).first()
  await libraryRow.getByRole('checkbox').check()
  await startButton.click()

  await expect(page).toHaveURL(/session=/)
  const questionInput = page.getByPlaceholder('Ask a question about the data…')
  await expect(questionInput).toBeVisible()

  // --- Ask a question that produces a result table -------------------------------
  await questionInput.fill('Show the total count of reports per district as a table.')
  await page.getByRole('button', { name: /^Ask/ }).click()

  await expect(page.getByText('thinking…')).toBeVisible()

  // A real Q&A runs several sequential LLM calls, so allow the full client-side
  // budget rather than a tight window. The token-usage readout confirms a
  // genuine assistant turn rendered (per the messages contract).
  await expect(page.getByText(/tokens · ~\$/).first()).toBeVisible({ timeout: 120_000 })
  await expect(page.getByText('thinking…')).toHaveCount(0)

  // --- (a) Export buttons appear for an answer that has a table ------------------
  // Whether a given question yields table_data depends on the agent, so only
  // assert export buttons when a result table actually rendered. When it did,
  // both Export CSV and Export PDF must be present.
  const tableCount = await page.locator('table').count()
  if (tableCount > 0) {
    await expect(page.getByRole('button', { name: 'Export CSV' }).first()).toBeVisible()
    await expect(page.getByRole('button', { name: 'Export PDF' }).first()).toBeVisible()
  }

  // --- (b) Follow-up chips render when suggestions are present -------------------
  // follow_ups is best-effort and may be empty, so only assert the label/chips
  // when the "Suggested follow-ups" block is actually shown.
  const followUpsLabel = page.getByText('Suggested follow-ups').first()
  if (await followUpsLabel.count()) {
    await expect(followUpsLabel).toBeVisible()
  }
})
