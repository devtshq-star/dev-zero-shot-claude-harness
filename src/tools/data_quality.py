"""Deterministic data-quality flags derived from a dataset profile.

No LLM call and no raw rows — purely a summary of the already-computed profile
(null counts, distinct counts, duplicate rows). Safe to surface in the UI.
"""

# A column is flagged as high-null at/above this fraction of missing values.
_HIGH_NULL_FRACTION = 0.30


def compute_data_quality_flags(profile: dict, row_count: int) -> list[str]:
    flags: list[str] = []
    columns = profile.get("columns", []) if profile else []

    if row_count > 0:
        for col in columns:
            null_count = col.get("null_count", 0) or 0
            fraction = null_count / row_count
            if fraction >= _HIGH_NULL_FRACTION:
                flags.append(f"column '{col.get('name')}' is {round(fraction * 100)}% null")

    for col in columns:
        distinct = col.get("distinct_count")
        if distinct == 1 and row_count > 1:
            flags.append(f"column '{col.get('name')}' has a single value in every row")

    duplicates = profile.get("duplicate_row_count", 0) if profile else 0
    if duplicates and duplicates > 0:
        flags.append(f"{duplicates} duplicate row{'s' if duplicates != 1 else ''}")

    return flags
