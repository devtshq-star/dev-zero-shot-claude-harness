# Capability: Audit Logging

## What It Does
Records a full, queryable audit trail of every question asked, the code generated to answer it, and the result produced — with a timestamp — for every interaction with the agent. This is a core requirement given the sensitivity of police data, not an optional add-on.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| session_id, question, generated_code, result_summary, latency_ms | various | Produced internally by the Q&A graph run (see `spec/agent.md` → `finalize_answer`) | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| Audit log entry | DB row (`audit_log_entries`) | Postgres, one row per question asked (including clarification-only turns and failed turns) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Postgres | insert `audit_log_entries` row | fatal — if the audit row cannot be written, the whole request fails rather than returning an answer with no audit trail |

## Business Rules
- Every turn is logged, including: successful answers, clarification requests, and failed/errored turns — not just successes.
- The logged `generated_code` is the exact code that was executed (the last attempt, on a self-corrected question) — never a summary or paraphrase.
- Audit entries are never deleted or mutated by the application — they are an append-only record.
- Audit entries are queryable by session, by time range, and by dataset, so a supervisor can reconstruct exactly what was asked and computed.

## Success Criteria
- [ ] Every question asked in a session has exactly one corresponding audit-log row, with a timestamp, the generated code, and a summary of the result.
- [ ] A failed question (e.g. exhausted retry attempts) still produces an audit-log row recording the failure, not a silently dropped interaction.
- [ ] Audit-log rows persist across server restarts (Postgres-backed, not in-memory).
