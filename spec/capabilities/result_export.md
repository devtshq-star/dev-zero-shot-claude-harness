# Capability: Result Export

## What It Does
Lets the analyst download the table behind any answer as a CSV or a formatted PDF, for filing or handing up the chain.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| turn_id | str | An assistant turn that has a result table | yes |
| format | "csv" \| "pdf" | Which export button was clicked | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| Export file | text/csv or application/pdf attachment | browser download |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Postgres | read the turn's `table_data` | 404 if the turn doesn't exist |
| — | render CSV/PDF in-process | 400 if the turn has no table to export |

## Business Rules
- Only the stored `table_data` of an assistant turn is exported — no re-computation, no LLM call.
- A turn with no table (prose-only or clarification) has nothing to export; the UI only shows export buttons when a table exists.
- The PDF is a simple titled table (question as heading, rows as a table) — presentation, not a re-analysis.

## Success Criteria
- [ ] Exporting a turn with a table as CSV downloads a file whose rows match `table_data`.
- [ ] Exporting the same turn as PDF downloads a valid PDF containing the question and the table.
- [ ] Requesting export for a turn with no table returns a clear 400; requesting a nonexistent turn returns 404.
