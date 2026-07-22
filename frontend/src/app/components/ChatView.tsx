'use client'

import { useEffect, useRef, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { ApiError, ChartSpec, TableRow, Turn, exportTurnUrl, getSession, postMessage } from '../lib/api'
import {
  ArrowLeftIcon,
  CopyIcon,
  DownloadIcon,
  SendIcon,
  SparklesIcon,
  TableIcon,
} from './icons'
import { Alert, Badge, Button, Skeleton, ThemeToggle, Toast } from './ui'

// Trigger a same-origin browser download for a raw file response. The export
// endpoint sets Content-Disposition, so a plain anchor click downloads the file.
function triggerDownload(url: string) {
  const a = document.createElement('a')
  a.href = url
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  a.remove()
}

function DataTable({ rows }: { rows: TableRow[] }) {
  if (rows.length === 0) return null
  const columns = Object.keys(rows[0])
  return (
    <div className="mt-3 overflow-x-auto rounded-xl border border-line">
      <table className="w-full text-left text-xs">
        <thead className="sticky top-0 bg-surface-2 text-muted">
          <tr>
            {columns.map(col => (
              <th key={col} className="whitespace-nowrap px-3 py-2 font-semibold">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t border-line/70 odd:bg-surface even:bg-surface-2/40 transition-colors hover:bg-primary-soft/40">
              {columns.map(col => {
                const v = row[col]
                const empty = v === null || v === undefined || v === ''
                return (
                  <td key={col} className={`whitespace-nowrap px-3 py-2 ${empty ? 'text-faint' : 'text-foreground'}`}>
                    {empty ? '—' : String(v)}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// Chart colors are CSS vars so they follow the active theme automatically.
const AXIS = { fontSize: 11, fill: 'var(--muted)' }

function Chart({ spec, data }: { spec: ChartSpec; data: TableRow[] }) {
  const isLine = spec.type === 'line'
  return (
    <div className="mt-3 h-64 w-full rounded-xl border border-line bg-surface p-3">
      <ResponsiveContainer width="100%" height="100%">
        {isLine ? (
          <LineChart data={data} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
            <XAxis dataKey={spec.x_field} tick={AXIS} tickLine={false} axisLine={{ stroke: 'var(--line)' }} />
            <YAxis tick={AXIS} tickLine={false} axisLine={{ stroke: 'var(--line)' }} />
            <Tooltip contentStyle={TOOLTIP} cursor={{ stroke: 'var(--line-strong)' }} />
            <Line type="monotone" dataKey={spec.y_field} stroke="var(--primary)" strokeWidth={2.5} dot={false} />
          </LineChart>
        ) : (
          <BarChart data={data} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" vertical={false} />
            <XAxis dataKey={spec.x_field} tick={AXIS} tickLine={false} axisLine={{ stroke: 'var(--line)' }} />
            <YAxis tick={AXIS} tickLine={false} axisLine={{ stroke: 'var(--line)' }} />
            <Tooltip contentStyle={TOOLTIP} cursor={{ fill: 'var(--primary-soft)' }} />
            <Bar dataKey={spec.y_field} fill="var(--primary)" radius={[4, 4, 0, 0]} />
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  )
}

const TOOLTIP = {
  backgroundColor: 'var(--surface)',
  border: '1px solid var(--line)',
  borderRadius: 10,
  color: 'var(--foreground)',
  fontSize: 12,
  boxShadow: 'var(--shadow-md)',
} as const

function formatCost(usd: number): string {
  if (usd === 0) return '$0'
  if (usd < 0.01) return `$${usd.toFixed(4)}`
  return `$${usd.toFixed(2)}`
}

function TurnBubble({
  turn,
  sessionId,
  sending,
  onAsk,
}: {
  turn: Turn
  sessionId: string
  sending: boolean
  onAsk: (question: string) => void
}) {
  const isUser = turn.role === 'user'
  const hasTable = !isUser && !!turn.table_data && turn.table_data.length > 0
  // Assistant turns from postMessage carry `turn_id`; turns from GET /api/sessions/{id}
  // carry `id`. Export needs a real persisted id — optimistic turns have neither yet.
  const turnId = turn.turn_id ?? turn.id
  const followUps = !isUser && !sending ? (turn.follow_ups ?? []).filter(q => q.trim().length > 0) : []

  if (isUser) {
    return (
      <div className="animate-rise-in flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm text-primary-fg shadow-[var(--shadow-sm)]">
          <p className="whitespace-pre-wrap">{turn.content}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="animate-rise-in flex justify-start gap-2.5">
      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary-soft-fg">
        <SparklesIcon className="h-4 w-4" />
      </span>
      <div className="min-w-0 max-w-[85%] rounded-2xl rounded-tl-md border border-line bg-surface px-4 py-3 text-sm text-foreground shadow-[var(--shadow-sm)]">
        <p className="whitespace-pre-wrap">{turn.content}</p>
        {turn.needs_clarification && (
          <div className="mt-2">
            <Badge tone="warning">Clarification needed</Badge>
          </div>
        )}
        {hasTable && <DataTable rows={turn.table_data!} />}
        {turn.chart_spec && turn.table_data && <Chart spec={turn.chart_spec} data={turn.table_data} />}
        {hasTable && turnId && (
          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              variant="secondary"
              size="sm"
              aria-label="Export CSV"
              leftIcon={<DownloadIcon className="h-3.5 w-3.5" />}
              onClick={() => triggerDownload(exportTurnUrl(sessionId, turnId, 'csv'))}
            >
              CSV
            </Button>
            <Button
              variant="secondary"
              size="sm"
              aria-label="Export PDF"
              leftIcon={<DownloadIcon className="h-3.5 w-3.5" />}
              onClick={() => triggerDownload(exportTurnUrl(sessionId, turnId, 'pdf'))}
            >
              PDF
            </Button>
          </div>
        )}
        {turn.token_usage && (
          <p className="mt-2.5 flex items-center gap-1.5 text-xs text-faint">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-success" />
            {turn.token_usage.prompt_tokens + turn.token_usage.completion_tokens} tokens · ~
            {formatCost(turn.token_usage.estimated_cost_usd)}
          </p>
        )}
        {followUps.length > 0 && (
          <div className="mt-3 border-t border-line pt-3">
            <p className="mb-2 text-xs font-medium text-muted">Suggested follow-ups</p>
            <div className="flex flex-wrap gap-2">
              {followUps.map((q, i) => (
                <button
                  key={i}
                  onClick={() => onAsk(q)}
                  disabled={sending}
                  className="rounded-full border border-primary/25 bg-primary-soft px-3 py-1 text-xs font-medium text-primary-soft-fg transition-colors hover:bg-primary hover:text-primary-fg disabled:opacity-50"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function ThinkingBubble() {
  return (
    <div className="animate-fade-in flex justify-start gap-2.5">
      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary-soft-fg">
        <SparklesIcon className="h-4 w-4" />
      </span>
      <div
        className="flex items-center gap-1.5 rounded-2xl rounded-tl-md border border-line bg-surface px-4 py-3.5 shadow-[var(--shadow-sm)]"
        role="status"
        aria-live="polite"
      >
        <span className="sr-only">thinking…</span>
        <span className="typing-dot h-2 w-2 rounded-full bg-faint" style={{ animationDelay: '0ms' }} />
        <span className="typing-dot h-2 w-2 rounded-full bg-faint" style={{ animationDelay: '150ms' }} />
        <span className="typing-dot h-2 w-2 rounded-full bg-faint" style={{ animationDelay: '300ms' }} />
      </div>
    </div>
  )
}

export default function ChatView({ sessionId, onBack }: { sessionId: string; onBack: () => void }) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [sendError, setSendError] = useState<string | null>(null)
  const [retryQuestion, setRetryQuestion] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    let cancelled = false
    setLoadingHistory(true)
    getSession(sessionId)
      .then(detail => {
        if (!cancelled) {
          setTurns(detail.turns ?? [])
          setHistoryError(null)
        }
      })
      .catch(err => {
        if (!cancelled) setHistoryError(err instanceof ApiError ? err.message : 'Failed to load session')
      })
      .finally(() => {
        if (!cancelled) setLoadingHistory(false)
      })
    return () => {
      cancelled = true
    }
  }, [sessionId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [turns, sending])

  // Return focus to the composer once a request settles, so the user can keep typing.
  useEffect(() => {
    if (!sending && !loadingHistory) inputRef.current?.focus()
  }, [sending, loadingHistory])

  async function sendQuestion(question: string, isRetry: boolean) {
    // On a retry the user's question bubble is already in the thread, so don't
    // append it again.
    if (!isRetry) {
      setTurns(prev => [...prev, { role: 'user', content: question }])
    }
    setSendError(null)
    setRetryQuestion(null)
    setSending(true)
    try {
      const turn = await postMessage(sessionId, question)
      setTurns(prev => [...prev, turn])
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : "Couldn't complete that analysis, please try rephrasing or ask something simpler."
      // Surface a retryable banner rather than a permanent assistant bubble, so
      // an interrupted request never leaves a dangling error in the thread and
      // the exact question can be re-sent with one click.
      setSendError(message)
      setRetryQuestion(question)
    } finally {
      setSending(false)
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const question = input.trim()
    if (!question || sending) return
    setInput('')
    void sendQuestion(question, false)
  }

  function handleRetry() {
    if (retryQuestion && !sending) void sendQuestion(retryQuestion, true)
  }

  function copySessionId() {
    navigator.clipboard?.writeText(sessionId).then(
      () => setCopied(true),
      () => {
        /* clipboard may be blocked; ignore */
      }
    )
  }

  return (
    <div className="flex h-screen flex-col">
      {/* Header */}
      <header className="sticky top-0 z-20 border-b border-line bg-canvas/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-3xl items-center justify-between gap-3 px-4">
          <Button variant="ghost" size="sm" onClick={onBack} leftIcon={<ArrowLeftIcon className="h-4 w-4" />}>
            Library
          </Button>
          <button
            onClick={copySessionId}
            className="group flex min-w-0 items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-muted transition-colors hover:bg-surface-2"
            title="Copy session ID"
          >
            <span className="truncate font-mono">{sessionId}</span>
            <CopyIcon className="h-3.5 w-3.5 shrink-0 opacity-60 group-hover:opacity-100" />
          </button>
          <ThemeToggle />
        </div>
      </header>

      {/* Messages */}
      <div className="mx-auto w-full max-w-3xl flex-1 overflow-y-auto px-4">
        <div className="space-y-4 py-6">
          {loadingHistory && (
            <div className="space-y-4">
              <div className="flex justify-end">
                <Skeleton className="h-10 w-48 rounded-2xl" />
              </div>
              <div className="flex gap-2.5">
                <Skeleton className="h-8 w-8 rounded-full" />
                <Skeleton className="h-24 w-72 rounded-2xl" />
              </div>
            </div>
          )}

          {historyError && <Alert tone="danger">{historyError}</Alert>}

          {!loadingHistory && !historyError && turns.length === 0 && (
            <div className="animate-fade-in flex flex-col items-center justify-center py-16 text-center">
              <span className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-soft text-primary-soft-fg">
                <TableIcon className="h-7 w-7" />
              </span>
              <p className="text-base font-semibold text-foreground">Ask anything about your data</p>
              <p className="mt-1.5 max-w-sm text-sm text-muted">
                Try “How many rows are there?”, “Show the top 10 by count”, or “Plot the trend over time”.
              </p>
            </div>
          )}

          {turns.map((turn, i) => (
            <TurnBubble
              key={turn.turn_id ?? turn.id ?? i}
              turn={turn}
              sessionId={sessionId}
              sending={sending}
              onAsk={q => {
                if (!sending) void sendQuestion(q, false)
              }}
            />
          ))}

          {sending && <ThinkingBubble />}

          {sendError && !sending && (
            <Alert
              tone="warning"
              action={
                <Button variant="secondary" size="sm" onClick={handleRetry}>
                  Retry
                </Button>
              }
            >
              {sendError}
            </Alert>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Composer */}
      <div className="border-t border-line bg-canvas/80 backdrop-blur-md">
        <form onSubmit={handleSubmit} className="mx-auto flex max-w-3xl items-center gap-2 px-4 py-4">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Ask a question about the data…"
            disabled={sending}
            autoFocus
            aria-label="Ask a question about the data"
            className="input h-11"
          />
          <Button
            type="submit"
            aria-label="Ask"
            loading={sending}
            disabled={sending || !input.trim()}
            leftIcon={!sending && <SendIcon className="h-4 w-4" />}
            className="h-11 px-3.5 sm:px-5"
          >
            <span className="hidden sm:inline">{sending ? 'Asking…' : 'Ask'}</span>
          </Button>
        </form>
      </div>

      {copied && <Toast message="Session ID copied" onDone={() => setCopied(false)} />}
    </div>
  )
}
