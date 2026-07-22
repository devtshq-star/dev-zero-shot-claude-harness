'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ApiError,
  Dataset,
  SessionSummary,
  createSession,
  listDatasets,
  listSessions,
  uploadDataset,
} from '../lib/api'
import {
  ChatIcon,
  DatabaseIcon,
  PlusIcon,
  SparklesIcon,
  TableIcon,
  UploadIcon,
} from './icons'
import { Alert, AppHeader, Badge, Button, Card, EmptyState, Skeleton, Spinner } from './ui'

interface UploadItem {
  key: string
  fileName: string
  status: 'uploading' | 'done' | 'error'
  dataset?: Dataset
  error?: string
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function ProfileCard({ dataset }: { dataset: Dataset }) {
  const profile = dataset.profile
  const qualityFlags = (dataset.data_quality_flags ?? []).filter(f => f.trim().length > 0)
  return (
    <Card className="animate-rise-in overflow-hidden p-0">
      <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary-soft-fg">
            <TableIcon className="h-4 w-4" />
          </span>
          <h3 className="truncate text-sm font-semibold text-foreground">{dataset.name}</h3>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <Badge tone="neutral">{dataset.row_count.toLocaleString()} rows</Badge>
          <Badge tone="neutral">{dataset.column_count} cols</Badge>
        </div>
      </div>

      <div className="space-y-3 p-4">
        {qualityFlags.length > 0 && (
          <Alert tone="warning">
            <p className="font-semibold">Data quality</p>
            <ul className="mt-1 list-disc space-y-0.5 pl-4">
              {qualityFlags.map((flag, i) => (
                <li key={i}>{flag}</li>
              ))}
            </ul>
          </Alert>
        )}
        {profile && (
          <>
            {profile.duplicate_row_count > 0 && (
              <div>
                <Badge tone="warning">
                  {profile.duplicate_row_count} duplicate row{profile.duplicate_row_count === 1 ? '' : 's'}
                </Badge>
              </div>
            )}
            <div className="overflow-x-auto rounded-lg border border-line">
              <table className="w-full text-left text-xs">
                <thead className="bg-surface-2 text-muted">
                  <tr>
                    <th className="px-3 py-2 font-medium">Column</th>
                    <th className="px-3 py-2 font-medium">Type</th>
                    <th className="px-3 py-2 font-medium">Nulls</th>
                    <th className="px-3 py-2 font-medium">Distinct</th>
                    <th className="px-3 py-2 font-medium">Range</th>
                  </tr>
                </thead>
                <tbody>
                  {profile.columns.map(col => (
                    <tr key={col.name} className="border-t border-line/70 transition-colors hover:bg-surface-2/60">
                      <td className="px-3 py-2 font-mono text-foreground">{col.name}</td>
                      <td className="px-3 py-2 text-muted">{col.dtype}</td>
                      <td className="px-3 py-2">
                        {col.null_count > 0 ? (
                          <span className="font-medium text-warning-fg">{col.null_count}</span>
                        ) : (
                          <span className="text-faint">0</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-muted">{col.distinct_count ?? '—'}</td>
                      <td className="px-3 py-2 text-muted">
                        {col.min !== undefined || col.max !== undefined ? `${col.min ?? '?'} – ${col.max ?? '?'}` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </Card>
  )
}

function SectionTitle({ children, count }: { children: React.ReactNode; count?: number }) {
  return (
    <div className="flex items-center gap-2">
      <h2 className="text-base font-semibold tracking-tight text-foreground">{children}</h2>
      {count !== undefined && count > 0 && <Badge tone="neutral">{count}</Badge>}
    </div>
  )
}

export default function UploadLibrary({ onOpenSession }: { onOpenSession: (id: string) => void }) {
  const [uploadItems, setUploadItems] = useState<UploadItem[]>([])
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [datasetsError, setDatasetsError] = useState<string | null>(null)
  const [datasetsLoading, setDatasetsLoading] = useState(true)
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [sessionsError, setSessionsError] = useState<string | null>(null)
  const [sessionsLoading, setSessionsLoading] = useState(true)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [dragOver, setDragOver] = useState(false)
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const refreshDatasets = useCallback(() => {
    listDatasets()
      .then(data => {
        setDatasets(data)
        setDatasetsError(null)
      })
      .catch(err => setDatasetsError(err instanceof ApiError ? err.message : 'Failed to load datasets'))
      .finally(() => setDatasetsLoading(false))
  }, [])

  const refreshSessions = useCallback(() => {
    listSessions()
      .then(data => {
        setSessions(data)
        setSessionsError(null)
      })
      .catch(err => setSessionsError(err instanceof ApiError ? err.message : 'Failed to load sessions'))
      .finally(() => setSessionsLoading(false))
  }, [])

  useEffect(() => {
    refreshDatasets()
    refreshSessions()
  }, [refreshDatasets, refreshSessions])

  const handleFiles = useCallback(
    (fileList: FileList | File[]) => {
      const files = Array.from(fileList)
      for (const file of files) {
        const key = `${file.name}-${file.size}-${Date.now()}-${Math.random()}`
        if (!file.name.toLowerCase().endsWith('.csv')) {
          setUploadItems(prev => [
            ...prev,
            { key, fileName: file.name, status: 'error', error: 'Only .csv files are supported' },
          ])
          continue
        }
        setUploadItems(prev => [...prev, { key, fileName: file.name, status: 'uploading' }])
        uploadDataset(file)
          .then(dataset => {
            setUploadItems(prev =>
              prev.map(item => (item.key === key ? { ...item, status: 'done', dataset } : item))
            )
            refreshDatasets()
          })
          .catch(err => {
            const message = err instanceof ApiError ? err.message : 'Upload failed'
            setUploadItems(prev => (prev.map(item => (item.key === key ? { ...item, status: 'error', error: message } : item))))
          })
      }
    },
    [refreshDatasets]
  )

  function onDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer.files?.length) handleFiles(e.dataTransfer.files)
  }

  function toggleSelected(id: string) {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function startSession() {
    if (selected.size === 0) return
    setStarting(true)
    setStartError(null)
    try {
      const session = await createSession(Array.from(selected))
      onOpenSession(session.id)
    } catch (err) {
      setStartError(err instanceof ApiError ? err.message : 'Failed to start session')
    } finally {
      setStarting(false)
    }
  }

  return (
    <div className="min-h-screen">
      <AppHeader />

      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6 sm:py-10">
        {/* Hero */}
        <div className="animate-fade-in mb-8">
          <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
            Analyze your datasets in plain language
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-muted sm:text-base">
            Upload CSV files, then start a session and ask questions in chat. The agent runs real analysis
            against your data — never a guessed number.
          </p>
        </div>

        {/* Upload */}
        <section className="mb-10">
          <div className="mb-3">
            <SectionTitle>Upload datasets</SectionTitle>
          </div>
          <div
            onDragOver={e => {
              e.preventDefault()
              setDragOver(true)
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={e => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                fileInputRef.current?.click()
              }
            }}
            role="button"
            tabIndex={0}
            aria-label="Upload CSV files by clicking or dropping them here"
            className={cxDrop(dragOver)}
          >
            <span
              className={`flex h-12 w-12 items-center justify-center rounded-2xl transition-colors ${
                dragOver ? 'bg-primary text-primary-fg' : 'bg-primary-soft text-primary-soft-fg'
              }`}
            >
              <UploadIcon className="h-6 w-6" />
            </span>
            <p className="mt-3 text-sm font-medium text-foreground">
              Drag &amp; drop CSV files here, or <span className="text-primary">browse</span>
            </p>
            <p className="mt-1 text-xs text-faint">Multiple .csv files accepted · nothing leaves your server but schema</p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              multiple
              className="hidden"
              onChange={e => {
                if (e.target.files?.length) handleFiles(e.target.files)
                e.target.value = ''
              }}
            />
          </div>

          {uploadItems.length > 0 && (
            <div className="mt-4 space-y-3">
              {uploadItems.map(item => (
                <div key={item.key}>
                  {item.status === 'uploading' && (
                    <Card className="flex items-center gap-3 px-4 py-3 text-sm text-muted">
                      <Spinner className="h-4 w-4 text-primary" />
                      <span>
                        Uploading &amp; parsing <span className="font-medium text-foreground">{item.fileName}</span>…
                      </span>
                    </Card>
                  )}
                  {item.status === 'error' && (
                    <Alert tone="danger">
                      <span className="font-medium">{item.fileName}:</span> {item.error}
                    </Alert>
                  )}
                  {item.status === 'done' && item.dataset && <ProfileCard dataset={item.dataset} />}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Library */}
        <section className="mb-10">
          <div className="mb-3 flex items-center justify-between gap-3">
            <SectionTitle count={datasets.length}>Dataset library</SectionTitle>
            <Button
              onClick={startSession}
              disabled={selected.size === 0 || starting}
              loading={starting}
              leftIcon={!starting && <SparklesIcon className="h-4 w-4" />}
            >
              {starting ? 'Starting…' : `Start session${selected.size ? ` (${selected.size})` : ''}`}
            </Button>
          </div>

          {startError && <div className="mb-3"><Alert tone="danger">{startError}</Alert></div>}
          {datasetsError && <div className="mb-3"><Alert tone="danger">{datasetsError}</Alert></div>}

          {datasetsLoading && !datasetsError && (
            <div className="space-y-2">
              {[0, 1, 2].map(i => (
                <Skeleton key={i} className="h-[58px] w-full rounded-xl" />
              ))}
            </div>
          )}

          {!datasetsLoading && datasets.length === 0 && !datasetsError && (
            <EmptyState
              icon={<DatabaseIcon className="h-6 w-6" />}
              title="No datasets yet"
              description="Upload a CSV above to see it profiled and ready to query."
            />
          )}

          <ul className="space-y-2">
            {datasets.map(ds => {
              const isSel = selected.has(ds.id)
              return (
                <li key={ds.id}>
                  <label
                    className={`group flex cursor-pointer items-center gap-3 rounded-xl border bg-surface p-3 shadow-[var(--shadow-xs)] transition-all hover:shadow-[var(--shadow-sm)] ${
                      isSel ? 'border-primary ring-2 ring-[var(--ring)]' : 'border-line hover:border-line-strong'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={isSel}
                      onChange={() => toggleSelected(ds.id)}
                      className="h-4 w-4 shrink-0 accent-[var(--primary)]"
                    />
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-surface-2 text-muted group-hover:text-primary">
                      <DatabaseIcon className="h-4 w-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-foreground">{ds.name}</p>
                      <p className="mt-0.5 text-xs text-muted">
                        {ds.row_count.toLocaleString()} rows · uploaded {formatDate(ds.uploaded_at)}
                      </p>
                    </div>
                  </label>
                </li>
              )
            })}
          </ul>
        </section>

        {/* Sessions */}
        <section>
          <div className="mb-3">
            <SectionTitle count={sessions.length}>Sessions</SectionTitle>
          </div>

          {sessionsError && <div className="mb-3"><Alert tone="danger">{sessionsError}</Alert></div>}

          {sessionsLoading && !sessionsError && (
            <div className="space-y-2">
              {[0, 1].map(i => (
                <Skeleton key={i} className="h-[54px] w-full rounded-xl" />
              ))}
            </div>
          )}

          {!sessionsLoading && sessions.length === 0 && !sessionsError && (
            <EmptyState
              icon={<ChatIcon className="h-6 w-6" />}
              title="No sessions yet"
              description="Select one or more datasets above and start a session to begin asking questions."
            />
          )}

          <ul className="space-y-2">
            {sessions.map(s => (
              <li
                key={s.id}
                className="flex items-center justify-between gap-3 rounded-xl border border-line bg-surface p-3 shadow-[var(--shadow-xs)] transition-shadow hover:shadow-[var(--shadow-sm)]"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary-soft-fg">
                    <ChatIcon className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <p className="truncate font-mono text-xs text-muted">{s.id}</p>
                    <p className="mt-0.5 text-xs text-muted">
                      {s.dataset_ids.length} dataset{s.dataset_ids.length === 1 ? '' : 's'} · created{' '}
                      {formatDate(s.created_at)}
                    </p>
                  </div>
                </div>
                <Button variant="secondary" size="sm" onClick={() => onOpenSession(s.id)}>
                  Resume
                </Button>
              </li>
            ))}
          </ul>
        </section>
      </main>
    </div>
  )
}

function cxDrop(dragOver: boolean): string {
  return [
    'flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-all',
    dragOver
      ? 'border-primary bg-primary-soft/60 scale-[1.01]'
      : 'border-line-strong bg-surface hover:border-primary hover:bg-surface-2',
  ].join(' ')
}
