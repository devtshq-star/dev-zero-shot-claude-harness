# Capability: Multi-file Analysis

## What It Does
Lets a session span more than one uploaded dataset, so a question can join or compare across files (e.g. crime counts against station rosters, or two districts' CSVs) — with the generated analysis code addressing each dataframe by name.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_ids | list[str] (2+) | Session creation | yes |
| question | string | User chat message | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| Assistant turn | prose + optional table/chart, computed across the datasets | chat UI |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| NVIDIA NIM LLM | generate code referencing multiple dataframes | self-correction loop as in Phase 1 |
| Local sandbox | run the code against all loaded dataframes | recoverable error → retry |

## Business Rules
- Each dataset is exposed to the generated code as `dfs["<dataset name>"]`; the schema of every dataset in the session is included (schema only — never rows).
- Joins/merges must be produced by the generated pandas code, executed locally — no raw rows cross to the LLM.
- Column-name collisions across files are the analyst's to disambiguate via the clarification path when the question is ambiguous.

## Success Criteria
- [ ] A session created over two datasets can answer a question that requires both (e.g. a join key present in each), returning a real computed result.
- [ ] The `dfs` dict in the sandbox contains one entry per dataset in the session, keyed by dataset name.
- [ ] A single-dataset session still works unchanged (the `df` convenience binding remains).
