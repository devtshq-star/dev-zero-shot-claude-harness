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
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-gray-900">{dataset.name}</h3>
        <span className="text-xs text-gray-500">
          {dataset.row_count.toLocaleString()} rows · {dataset.column_count} columns
        </span>
      </div>
      {profile && (
        <>
          {profile.duplicate_row_count > 0 && (
            <p className="mt-2 text-xs font-medium text-amber-700">
              {profile.duplicate_row_count} duplicate row{profile.duplicate_row_count === 1 ? '' : 's'} detected
            </p>
          )}
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-gray-200 text-gray-500">
                  <th className="py-1 pr-3 font-medium">Column</th>
                  <th className="py-1 pr-3 font-medium">Type</th>
                  <th className="py-1 pr-3 font-medium">Nulls</th>
                  <th className="py-1 pr-3 font-medium">Distinct</th>
                  <th className="py-1 font-medium">Range</th>
                </tr>
              </thead>
              <tbody>
                {profile.columns.map(col => (
                  <tr key={col.name} className="border-b border-gray-100 last:border-0">
                    <td className="py-1 pr-3 font-mono text-gray-800">{col.name}</td>
                    <td className="py-1 pr-3 text-gray-600">{col.dtype}</td>
                    <td className={`py-1 pr-3 ${col.null_count > 0 ? 'font-medium text-amber-700' : 'text-gray-600'}`}>
                      {col.null_count}
                    </td>
                    <td className="py-1 pr-3 text-gray-600">{col.distinct_count ?? '—'}</td>
                    <td className="py-1 text-gray-600">
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
  )
}

export default function UploadLibrary({ onOpenSession }: { onOpenSession: (id: string) => void }) {
  const [uploadItems, setUploadItems] = useState<UploadItem[]>([])
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [datasetsError, setDatasetsError] = useState<string | null>(null)
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [sessionsError, setSessionsError] = useState<string | null>(null)
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
  }, [])

  const refreshSessions = useCallback(() => {
    listSessions()
      .then(data => {
        setSessions(data)
        setSessionsError(null)
      })
      .catch(err => setSessionsError(err instanceof ApiError ? err.message : 'Failed to load sessions'))
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
    <main className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="mb-8 text-3xl font-bold tracking-tight">UP Police Data Analyst Agent</h1>

      <section className="mb-10">
        <h2 className="mb-3 text-lg font-semibold text-gray-800">Upload datasets</h2>
        <div
          onDragOver={e => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`cursor-pointer rounded-lg border-2 border-dashed p-8 text-center text-sm transition-colors ${
            dragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-white hover:border-gray-400'
          }`}
        >
          <p className="text-gray-600">Drag and drop CSV files here, or click to choose files</p>
          <p className="mt-1 text-xs text-gray-400">Multiple .csv files are accepted at once</p>
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
                  <div className="rounded-lg border border-gray-200 bg-white p-3 text-sm text-gray-500">
                    Uploading &amp; parsing {item.fileName}…
                  </div>
                )}
                {item.status === 'error' && (
                  <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                    <span className="font-medium">{item.fileName}:</span> {item.error}
                  </div>
                )}
                {item.status === 'done' && item.dataset && <ProfileCard dataset={item.dataset} />}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="mb-10">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-800">Dataset library</h2>
          <button
            onClick={startSession}
            disabled={selected.size === 0 || starting}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {starting ? 'Starting…' : `Start session${selected.size ? ` (${selected.size})` : ''}`}
          </button>
        </div>
        {startError && (
          <div className="mb-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{startError}</div>
        )}
        {datasetsError && (
          <div className="mb-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{datasetsError}</div>
        )}
        {datasets.length === 0 && !datasetsError && (
          <p className="text-sm text-gray-400">No datasets uploaded yet.</p>
        )}
        <ul className="space-y-2">
          {datasets.map(ds => (
            <li
              key={ds.id}
              className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-3 text-sm shadow-sm"
            >
              <input
                type="checkbox"
                checked={selected.has(ds.id)}
                onChange={() => toggleSelected(ds.id)}
                className="h-4 w-4"
              />
              <div className="flex-1">
                <span className="font-medium text-gray-900">{ds.name}</span>
                <span className="ml-2 text-xs text-gray-500">
                  {ds.row_count.toLocaleString()} rows · uploaded {formatDate(ds.uploaded_at)}
                </span>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold text-gray-800">Sessions</h2>
        {sessionsError && (
          <div className="mb-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{sessionsError}</div>
        )}
        {sessions.length === 0 && !sessionsError && (
          <p className="text-sm text-gray-400">No sessions yet — start one above.</p>
        )}
        <ul className="space-y-2">
          {sessions.map(s => (
            <li
              key={s.id}
              className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-3 text-sm shadow-sm"
            >
              <div>
                <span className="font-mono text-xs text-gray-500">{s.id}</span>
                <span className="ml-2 text-xs text-gray-500">
                  {s.dataset_ids.length} dataset{s.dataset_ids.length === 1 ? '' : 's'} · created{' '}
                  {formatDate(s.created_at)}
                </span>
              </div>
              <button
                onClick={() => onOpenSession(s.id)}
                className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
              >
                Resume
              </button>
            </li>
          ))}
        </ul>
      </section>
    </main>
  )
}
