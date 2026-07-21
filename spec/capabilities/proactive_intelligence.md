# Capability: Proactive Intelligence

## What It Does
Surfaces things the analyst didn't explicitly ask for: a data-quality summary on a dataset's profile (columns with high null rates, duplicate rows), and 2–3 relevant follow-up questions after each answer.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset profile | JSON | Computed at upload (Phase 1) | yes |
| question + computed result | various | The Q&A run | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| Data-quality flags | list of short strings (e.g. "column `District_Notes` is 82% null", "2 duplicate rows") | dataset profile response → UI |
| Follow-up suggestions | list of 2–3 short question strings | assistant turn response → UI (clickable chips) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| NVIDIA NIM LLM | generate follow-up suggestions from the question + result in `finalize_answer` | non-fatal — the answer still returns; suggestions default to empty |

## Business Rules
- Data-quality flags are derived deterministically from the existing profile (null counts, duplicate count) — no extra LLM call, no raw rows.
- Follow-up suggestions are generated as part of the existing `finalize_answer` LLM call (no additional round-trip) and must be answerable against the session's datasets.
- A failure to produce suggestions never fails the answer — suggestions are best-effort; the computed answer is not.

## Success Criteria
- [ ] A dataset with a high-null column shows a data-quality flag naming that column and its null rate.
- [ ] Every successful answer returns 2–3 follow-up suggestions (or an empty list if the model declines) — never causes the answer to fail.
- [ ] Clicking a suggested follow-up in the UI asks it as the next question.
