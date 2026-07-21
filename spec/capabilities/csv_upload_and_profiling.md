# Capability: CSV Upload & Profiling

## What It Does
Accepts one or more uploaded CSV files, parses them, and immediately produces an auto-profile (row/column counts, dtypes, null counts, duplicate-row count) with zero manual steps.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| files | multipart file(s) | User upload via chat UI | yes |
| dataset_name | string | User-provided or defaulted to filename | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| Dataset record | DB row (`datasets` table) | Postgres |
| Persisted file | CSV file | `data/uploads/<dataset_id>.csv` |
| Profile summary | JSON (columns, dtypes, row_count, null_counts, duplicate_count) | API response → chat UI |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Local filesystem | write uploaded file | 400 to user: "upload failed, try again"; no partial dataset row created |
| Postgres | insert `datasets` row | 500 to user; file cleaned up (no orphaned file without a DB row) |

## Business Rules
- Only `.csv` files are accepted; a non-CSV upload is rejected with a clear error before any parsing is attempted.
- A parse failure (malformed CSV) is reported with the specific error (e.g. "row 45 has more columns than the header") — never a generic "upload failed."
- Profiling never sends the file contents to the LLM — it runs entirely with pandas, locally.
- Multiple files uploaded together are each profiled independently and each becomes its own `Dataset` row; joining across them happens later, at question-answering time (see `data_qa_chat.md`), not at upload time.

## Success Criteria
- [ ] Uploading a valid CSV returns a profile within a few seconds showing the real row/column count and real dtypes (not placeholders).
- [ ] Uploading a non-CSV file is rejected with a clear, specific error before reaching the parser.
- [ ] Uploading a CSV with an obvious data-quality issue (e.g. a column that is 40% null) surfaces that in the profile.
- [ ] The dataset is queryable in a chat session immediately after upload, with no separate "processing" step the user has to wait for.
