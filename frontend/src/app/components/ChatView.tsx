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
import { ApiError, ChartSpec, TableRow, Turn, getSession, postMessage } from '../lib/api'

function DataTable({ rows }: { rows: TableRow[] }) {
  if (rows.length === 0) return null
  const columns = Object.keys(rows[0])
  return (
    <div className="mt-3 overflow-x-auto rounded-lg border border-gray-200">
      <table className="w-full text-left text-xs">
        <thead className="bg-gray-50">
          <tr>
            {columns.map(col => (
              <th key={col} className="px-3 py-2 font-medium text-gray-600">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t border-gray-100">
              {columns.map(col => (
                <td key={col} className="px-3 py-2 text-gray-800">
                  {String(row[col] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Chart({ spec, data }: { spec: ChartSpec; data: TableRow[] }) {
  const isLine = spec.type === 'line'
  return (
    <div className="mt-3 h-64 w-full rounded-lg border border-gray-200 bg-white p-2">
      <ResponsiveContainer width="100%" height="100%">
        {isLine ? (
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey={spec.x_field} tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Line type="monotone" dataKey={spec.y_field} stroke="#2563eb" strokeWidth={2} dot={false} />
          </LineChart>
        ) : (
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey={spec.x_field} tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey={spec.y_field} fill="#2563eb" />
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  )
}

function formatCost(usd: number): string {
  if (usd === 0) return '$0'
  if (usd < 0.01) return `$${usd.toFixed(4)}`
  return `$${usd.toFixed(2)}`
}

function TurnBubble({ turn }: { turn: Turn }) {
  const isUser = turn.role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-3 text-sm shadow-sm ${
          isUser ? 'bg-blue-600 text-white' : 'border border-gray-200 bg-white text-gray-900'
        }`}
      >
        <p className="whitespace-pre-wrap">{turn.content}</p>
        {!isUser && turn.needs_clarification && (
          <p className="mt-1 text-xs font-medium text-amber-700">Clarification needed</p>
        )}
        {!isUser && turn.table_data && turn.table_data.length > 0 && <DataTable rows={turn.table_data} />}
        {!isUser && turn.chart_spec && turn.table_data && <Chart spec={turn.chart_spec} data={turn.table_data} />}
        {!isUser && turn.token_usage && (
          <p className="mt-2 text-xs text-gray-400">
            {turn.token_usage.prompt_tokens + turn.token_usage.completion_tokens} tokens · ~
            {formatCost(turn.token_usage.estimated_cost_usd)}
          </p>
        )}
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
  const bottomRef = useRef<HTMLDivElement>(null)

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

  return (
    <main className="mx-auto flex h-screen max-w-3xl flex-col px-4 py-6">
      <div className="mb-4 flex items-center justify-between">
        <button onClick={onBack} className="text-sm font-medium text-blue-600 hover:underline">
          ← Upload &amp; Library
        </button>
        <span className="font-mono text-xs text-gray-400">{sessionId}</span>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto pb-4">
        {loadingHistory && <p className="text-sm text-gray-400">Loading conversation…</p>}
        {historyError && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{historyError}</div>
        )}
        {!loadingHistory && !historyError && turns.length === 0 && (
          <p className="text-sm text-gray-400">Ask a question about the selected dataset(s) to get started.</p>
        )}
        {turns.map((turn, i) => (
          <TurnBubble key={turn.turn_id ?? turn.id ?? i} turn={turn} />
        ))}
        {sending && (
          <div className="flex justify-start">
            <div className="rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm text-gray-400 shadow-sm">
              thinking…
            </div>
          </div>
        )}
        {sendError && !sending && (
          <div className="flex items-start justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <span>{sendError}</span>
            <button
              onClick={handleRetry}
              className="shrink-0 rounded-md bg-amber-600 px-3 py-1 text-xs font-medium text-white hover:bg-amber-700"
            >
              Retry
            </button>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2 border-t border-gray-200 pt-4">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask a question about the data…"
          disabled={sending}
          className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {sending ? 'Asking…' : 'Ask'}
        </button>
      </form>
    </main>
  )
}
