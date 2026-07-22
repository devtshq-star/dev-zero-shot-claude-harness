// Types and fetch helpers for the UP Police Data Analyst Agent API.
// All calls use relative paths so they work same-origin behind FastAPI at /app/.

export interface DatasetColumn {
  name: string
  dtype: string
  null_count: number
  distinct_count?: number
  min?: string
  max?: string
}

export interface DatasetProfile {
  columns: DatasetColumn[]
  duplicate_row_count: number
}

export interface Dataset {
  id: string
  name: string
  row_count: number
  column_count: number
  profile?: DatasetProfile | null
  // Since Phase 2: short human-readable data-quality strings derived from the
  // profile (e.g. "column 'District_Notes' is 82% null"). Empty when clean.
  data_quality_flags?: string[]
  uploaded_at: string
}

export interface SessionSummary {
  id: string
  dataset_ids: string[]
  created_at: string
}

export interface TokenUsage {
  prompt_tokens: number
  completion_tokens: number
  estimated_cost_usd: number
}

export interface ChartSpec {
  type: string
  x_field: string
  y_field: string
  [key: string]: unknown
}

export type TableRow = Record<string, unknown>

export interface Turn {
  turn_id?: string
  id?: string
  role: 'user' | 'assistant'
  content: string
  table_data?: TableRow[] | null
  chart_spec?: ChartSpec | null
  needs_clarification?: boolean
  // Since Phase 2: 0–3 suggested next questions (best-effort; may be empty).
  // Carried on a fresh assistant turn and persisted in GET /api/sessions/{id}.
  follow_ups?: string[]
  token_usage?: TokenUsage | null
  created_at?: string
}

export interface SessionDetail extends SessionSummary {
  turns: Turn[]
}

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function parseJson(res: Response): Promise<unknown> {
  try {
    return await res.json()
  } catch {
    return null
  }
}

function extractErrorMessage(body: unknown, status: number): string {
  if (body && typeof body === 'object') {
    const b = body as Record<string, unknown>
    if (typeof b.error === 'string' && b.error) return b.error
    if (typeof b.detail === 'string' && b.detail) return b.detail
    if (Array.isArray(b.detail)) {
      const msgs = b.detail
        .map(d => (d && typeof d === 'object' && 'msg' in d ? String((d as Record<string, unknown>).msg) : null))
        .filter(Boolean)
      if (msgs.length) return msgs.join('; ')
    }
  }
  return `Request failed (${status})`
}

// Status 0 = the request never got a valid HTTP response (timeout, aborted
// connection, or the server going away). Callers can special-case it to offer
// a retry rather than treating it like a real server error.
const TIMED_OUT = 0

async function request<T>(path: string, options?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const { timeoutMs, ...fetchOptions } = options ?? {}
  const controller = new AbortController()
  const timer = timeoutMs ? setTimeout(() => controller.abort(), timeoutMs) : null

  let res: Response
  try {
    res = await fetch(path, { ...fetchOptions, signal: controller.signal })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiError(
        'The request timed out — the server may be busy or the connection was interrupted. Please retry.',
        TIMED_OUT,
      )
    }
    throw new ApiError('Network error — is the server running?', TIMED_OUT)
  } finally {
    if (timer) clearTimeout(timer)
  }

  const body = await parseJson(res)
  if (!res.ok) {
    throw new ApiError(extractErrorMessage(body, res.status), res.status)
  }
  const data = body && typeof body === 'object' ? (body as Record<string, unknown>).data : undefined
  return data as T
}

export function uploadDataset(file: File): Promise<Dataset> {
  const form = new FormData()
  form.append('files', file)
  return request<Dataset[]>('/api/datasets', { method: 'POST', body: form }).then(arr => arr[0])
}

export function listDatasets(): Promise<Dataset[]> {
  return request<Dataset[]>('/api/datasets')
}

export function listSessions(): Promise<SessionSummary[]> {
  return request<SessionSummary[]>('/api/sessions')
}

export function createSession(datasetIds: string[]): Promise<SessionSummary> {
  return request<SessionSummary>('/api/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataset_ids: datasetIds }),
  })
}

export function getSession(id: string): Promise<SessionDetail> {
  return request<SessionDetail>(`/api/sessions/${id}`)
}

// The analysis pipeline can run several LLM calls plus a bounded retry loop, so
// allow generous headroom — but cap it so a dead/hung server surfaces as a
// retryable timeout instead of an indefinite "thinking…" spinner.
const MESSAGE_TIMEOUT_MS = 120_000

// Build the same-origin URL for the turn-export endpoint. It returns a raw file
// attachment (no JSON envelope), so callers trigger a browser download against
// this URL rather than going through `request()`.
export function exportTurnUrl(sessionId: string, turnId: string, format: 'csv' | 'pdf'): string {
  return `/api/sessions/${sessionId}/turns/${turnId}/export?format=${format}`
}

// `language` is the UI language ('en' | 'hi'); the agent uses it to pick the
// response language (falling back to whatever language the question is in).
export function postMessage(sessionId: string, question: string, language = 'en'): Promise<Turn> {
  return request<Turn>(`/api/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, language }),
    timeoutMs: MESSAGE_TIMEOUT_MS,
  })
}
