# API

---

## API Style

REST, served by FastAPI at `http://localhost:8001`, consumed by the Next.js chat UI at `/app/`.

## Endpoints

### `POST /api/datasets`

**Purpose:** Upload one or more CSV files; each is parsed and profiled immediately.

**Request:** `multipart/form-data`, field `files` (one or more file parts).

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "name": "crime_reports_june.csv",
      "row_count": 12045,
      "column_count": 9,
      "profile": {
        "columns": [
          {"name": "district", "dtype": "object", "null_count": 0, "distinct_count": 75},
          {"name": "occurred_at", "dtype": "datetime64", "null_count": 3, "min": "2026-06-01", "max": "2026-06-30"}
        ],
        "duplicate_row_count": 2
      },
      "uploaded_at": "2026-07-21T10:00:00Z"
    }
  ],
  "error": null
}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | A file is not a valid CSV, or fails to parse |
| 500 | Filesystem write or DB insert failed |

### `GET /api/datasets`

**Purpose:** List previously uploaded datasets (for resuming an analysis across days).

**Response:** `{"data": [ {...same shape as above, without full profile} ], "error": null}`

### `GET /api/datasets/{id}`

**Purpose:** Full detail + profile for one dataset.

Since Phase 2, dataset responses also include a derived `data_quality_flags` array — short human-readable strings computed deterministically from the profile (e.g. `"column 'District_Notes' is 82% null"`, `"2 duplicate rows"`). Empty when the data looks clean.

```json
{"data": {"id": "uuid", "name": "...", "row_count": 800, "column_count": 17,
          "profile": { ... }, "data_quality_flags": ["column 'District_Notes' is 82% null"],
          "uploaded_at": "..."}, "error": null}
```

**Error cases:** `404` if the dataset doesn't exist.

### `POST /api/sessions`

**Purpose:** Create a new conversation session bound to one or more datasets.

**Request:**
```json
{"dataset_ids": ["uuid1", "uuid2"]}
```

**Response:**
```json
{"data": {"id": "uuid", "dataset_ids": ["uuid1", "uuid2"], "created_at": "..."}, "error": null}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | `dataset_ids` empty or references a nonexistent dataset |

### `GET /api/sessions`

**Purpose:** List existing sessions (for resuming).

### `GET /api/sessions/{id}`

**Purpose:** Session detail + full turn history, in chronological order.

**Error cases:** `404` if the session doesn't exist.

### `POST /api/sessions/{id}/messages`

**Purpose:** Ask a question; runs the LangGraph Q&A agent end-to-end and returns the assistant's turn.

**Request:**
```json
{"question": "How many thefts were reported in Lucknow in June?"}
```

**Response:**
```json
{
  "data": {
    "turn_id": "uuid",
    "role": "assistant",
    "content": "There were 342 thefts reported in Lucknow district in June.",
    "table_data": [{"district": "Lucknow", "crime_type": "theft", "count": 342}],
    "chart_spec": null,
    "needs_clarification": false,
    "follow_ups": ["Which district had the most active cases?", "How did cases trend over time?"],
    "token_usage": {"prompt_tokens": 812, "completion_tokens": 96, "estimated_cost_usd": 0.0009}
  },
  "error": null
}
```

Since Phase 2, a successful answer also carries `follow_ups` — 2–3 suggested next questions (best-effort; may be an empty array). The same `follow_ups` field is persisted on the turn and returned in `GET /api/sessions/{id}` history. `GET /api/sessions/{id}` turn objects also carry `follow_ups`.

When the question is ambiguous, `content` holds the clarifying question and `needs_clarification` is `true`; `table_data`/`chart_spec`/`follow_ups` are empty/null.

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | `question` empty |
| 404 | session doesn't exist |
| 502 | the LLM/analysis pipeline failed after its retry budget — `content` still returns a clear, non-technical message; the audit log records the failure |

### `GET /api/sessions/{session_id}/turns/{turn_id}/export?format=csv|pdf`

**Purpose:** Download the result table of an assistant turn as a file.

**Response:** a file attachment — `text/csv` (`format=csv`) or `application/pdf` (`format=pdf`), with a `Content-Disposition: attachment` filename. The PDF is a titled table (the question as heading, the rows as a table).

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | `format` is not `csv`/`pdf`, or the turn has no `table_data` to export |
| 404 | session or turn doesn't exist |

### `GET /health`

Existing endpoint, unchanged.

## Authentication

None in Phases 1–2 — single shared workspace, no login (see `spec/roadmap.md` → Out of Scope). Phase 3 adds role/district-based authentication as a prerequisite for the MSSQL connection to production police data.
