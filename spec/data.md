# Data Model

---

## Storage Technology

PostgreSQL via SQLAlchemy 2.0 + Alembic migrations. Uploaded CSV files themselves are persisted on the local filesystem under `data/uploads/<dataset_id>.csv`; Postgres stores metadata, profiles, conversation state, and the audit trail — never raw row data duplicated into a DB table (the CSV file itself is the source of row data, loaded into memory by pandas when a session needs it).

## Entities

### Entity: Dataset

Represents one uploaded CSV file and its computed profile.

| Field | Type | Required | Description |
|-------|------|----------|--------------|
| id | UUID (text) | yes | Primary key |
| name | text | yes | Display name (defaults to original filename) |
| original_filename | text | yes | As uploaded |
| storage_path | text | yes | Path under `data/uploads/` |
| row_count | integer | yes | Computed at upload |
| column_count | integer | yes | Computed at upload |
| profile | JSON | yes | Per-column dtype, null count, distinct-value count, min/max where numeric |
| uploaded_at | timestamptz | yes | |

### Entity: ConversationSession

Represents one ongoing chat session bound to one or more datasets.

| Field | Type | Required | Description |
|-------|------|----------|--------------|
| id | UUID (text) | yes | Primary key |
| dataset_ids | JSON (list of Dataset.id) | yes | The dataset(s) this session queries |
| created_at | timestamptz | yes | |
| last_active_at | timestamptz | yes | Updated on every new turn |

### Entity: ConversationTurn

One message (user question or assistant answer) within a session.

| Field | Type | Required | Description |
|-------|------|----------|--------------|
| id | UUID (text) | yes | Primary key |
| session_id | UUID (text, FK → ConversationSession.id) | yes | |
| role | text (`"user"` \| `"assistant"`) | yes | |
| content | text | yes | The message text (question or prose answer, or a clarifying question) |
| table_data | JSON, nullable | no | Structured table rows, when the answer includes one |
| chart_spec | JSON, nullable | no | Chart spec, when the answer includes one |
| created_at | timestamptz | yes | |

### Entity: AuditLogEntry

Append-only record of every question asked and what the agent did to answer it.

| Field | Type | Required | Description |
|-------|------|----------|--------------|
| id | UUID (text) | yes | Primary key |
| session_id | UUID (text, FK → ConversationSession.id) | yes | |
| turn_id | UUID (text, FK → ConversationTurn.id), nullable | no | The resulting assistant turn, if any (null for a failed/errored question) |
| question | text | yes | Exactly what the user asked |
| generated_code | text, nullable | no | The final (executed or last-attempted) pandas code |
| exec_status | text (`"success"` \| `"error"` \| `"clarification"`) | yes | |
| result_summary | text, nullable | no | A short summary of the computed result (or the error) |
| latency_ms | integer | yes | Total time to answer |
| created_at | timestamptz | yes | |

### Relationships

- `ConversationSession` 1—N `ConversationTurn`
- `ConversationSession` 1—N `AuditLogEntry`
- `ConversationSession` N—N `Dataset` (via the `dataset_ids` JSON list — no join table needed at this scale)
- `AuditLogEntry` 0/1—1 `ConversationTurn` (null when the question failed before producing a turn)

## Data Lifecycle

- A `Dataset` is created on upload and never auto-deleted in Phase 1 (manual deletion is out of scope — see `spec/roadmap.md`).
- A `ConversationSession` and its `ConversationTurn`s persist indefinitely (supports "return to the same dataset across days").
- `AuditLogEntry` rows are append-only and never deleted or edited by the application.

## Sensitive Data

- CSV file contents (crime/case/personnel records) are the sensitive payload. They are stored only in the local filesystem and loaded into memory server-side — never included in any LLM request body, and never duplicated into a Postgres column.
- `AuditLogEntry.generated_code` and `result_summary` may contain derived/aggregate figures about sensitive data (e.g. "342 thefts in Lucknow") — these are necessarily present for the audit trail to be useful, but never raw per-record data (e.g. no individual's name/ID appears unless the user's own question and the real data legitimately produce it as a computed answer — Phase 1 does not add redaction on top of this; access control in Phase 2 is the intended control for who can read the audit log).
