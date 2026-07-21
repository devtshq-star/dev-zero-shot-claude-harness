import path from 'node:path'
import { expect, test } from '@playwright/test'

// End-to-end smoke test for the Phase 1 primary journey, run against the
// single-origin static export served by FastAPI at http://localhost:8001/app/
// (see harness/patterns/tech-stack.md). This test is NOT started by the
// frontend build itself — the orchestrating session runs
// `cd frontend && pnpm build` + `uv run python -m src`, then:
//   npx playwright test tests/e2e/ --reporter=line
//
// Covers: page loads and is styled -> upload a CSV -> profile appears ->
// ask a question -> a real computed answer renders.

const SAMPLE_CSV = path.join(__dirname, 'fixtures', 'sample_crime_reports.csv')

test.setTimeout(90_000)

test('upload a CSV, see its profile, start a session, and get a real answer', async ({ page }) => {
  await page.goto('/app/')

  // --- Page loads and is styled -------------------------------------------------
  await expect(page.getByRole('heading', { name: 'UP Police Data Analyst Agent' })).toBeVisible()
  const startButton = page.getByRole('button', { name: /Start session/ })
  await expect(startButton).toBeVisible()
  // Tailwind's bg-blue-600 should be compiled into a real color (Tailwind v4
  // emits oklch(), not rgb()) — not left as an unstyled utility class name.
  const backgroundColor = await startButton.evaluate(el => getComputedStyle(el).backgroundColor)
  expect(backgroundColor).not.toBe('rgba(0, 0, 0, 0)')
  expect(backgroundColor).toMatch(/^(rgb|oklch)/)

  // --- Upload a CSV --------------------------------------------------------------
  const fileInput = page.locator('input[type="file"]')
  await fileInput.setInputFiles(SAMPLE_CSV)

  // --- Profile card appears (no polling, no manual "process" step) --------------
  await expect(page.getByRole('heading', { name: 'sample_crime_reports.csv' }).first()).toBeVisible({ timeout: 20_000 })
  await expect(page.getByText(/rows.*columns/).first()).toBeVisible()
  // Scope to a profile-table CELL (not a loose page-wide text match) so the
  // assertion is robust to other datasets in the shared library whose names
  // happen to contain "district".
  await expect(page.getByRole('cell', { name: 'district', exact: true }).first()).toBeVisible()

  // --- Select the dataset in the library and start a session ---------------------
  // The dev DB is shared, so the library may already hold other datasets (and
  // repeat runs add another sample_crime_reports.csv). listDatasets returns
  // newest-first, so .first() selects the row this run just uploaded.
  const libraryRow = page.locator('li', { hasText: 'sample_crime_reports.csv' }).first()
  await libraryRow.getByRole('checkbox').check()
  await startButton.click()

  // --- Navigated into the Chat screen for the new session ------------------------
  await expect(page).toHaveURL(/session=/)
  const questionInput = page.getByPlaceholder('Ask a question about the data…')
  await expect(questionInput).toBeVisible()

  // --- Ask a question and see a real, computed answer -----------------------------
  await questionInput.fill('How many rows are there in total?')
  await page.getByRole('button', { name: /^Ask/ }).click()

  await expect(page.getByText('thinking…')).toBeVisible()

  // A real assistant turn always carries a token-usage readout (per
  // POST /api/sessions/{id}/messages contract) once the pipeline finishes —
  // this both confirms the "thinking" indicator clears and that a genuine
  // answer (not a crash, not a stub) rendered.
  // A real Q&A runs several sequential LLM calls (classify -> generate ->
  // execute -> finalize), so allow the full client-side budget (see
  // MESSAGE_TIMEOUT_MS in lib/api.ts) rather than a tight window.
  await expect(page.getByText(/tokens · ~\$/).first()).toBeVisible({ timeout: 120_000 })
  await expect(page.getByText('thinking…')).toHaveCount(0)
})
