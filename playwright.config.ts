import { defineConfig, devices } from '@playwright/test'

// The frontend is a Next.js static export served by the FastAPI backend at
// http://localhost:8001/app/ (single-origin run path — see
// harness/patterns/tech-stack.md "Frontend Static-Export & Styling Rule").
// This config does NOT start any server: the orchestrating session is
// responsible for running `cd frontend && pnpm build` and
// `uv run python -m src` before these tests are executed.
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: 'line',
  use: {
    baseURL: 'http://localhost:8001',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
