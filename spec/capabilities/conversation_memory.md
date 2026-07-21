# Capability: Conversation Memory

## What It Does
Persists conversation history and the set of loaded datasets for a session, so follow-up questions ("and what about last month?") work without re-explaining context, and so a user can return to the same analysis across multiple days.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| session_id | string | Existing or newly created session | yes |
| dataset_ids | list[string] | Chosen at session creation | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| Turn history | ordered list of `{role, content, created_at}` | API response when a session is reopened |
| Session list | list of sessions with their bound dataset(s) and last-active time | API response → chat UI's session picker |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Postgres | read/write `conversation_sessions`, `conversation_turns` | fatal for writes (a turn that isn't persisted didn't happen, for audit purposes); reads fail with a clear "history unavailable" rather than silently showing an empty history |

## Business Rules
- The last 20 turns of a session are loaded verbatim into the LLM prompt context for `classify_intent`/`generate_code` (see `spec/agent.md` → Memory & Context) — no summarization in Phase 1.
- Reopening a session on a different day loads the same dataset(s) and full turn history — the user does not need to re-upload.
- A session is scoped to the dataset(s) chosen when it was created; adding a dataset mid-session is out of scope for Phase 1 (create a new session instead).

## Success Criteria
- [ ] A follow-up question referencing "that" or "last month" in a prior turn is answered correctly using the stored conversation history.
- [ ] Closing the browser and reopening the same session the next day shows the full prior conversation and the same datasets, queryable immediately.
- [ ] The turn history returned for a session is in chronological order and includes both user and assistant messages.
