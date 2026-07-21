import pandas as pd

from tools.csv_profiling import load_and_profile_csv, profile_dataframe


def test_profile_dataframe_basic():
    df = pd.DataFrame({
        "district": ["Lucknow", "Kanpur", "Lucknow", None],
        "count": [1, 2, 3, 4],
    })
    profile = profile_dataframe(df)
    assert profile["row_count"] == 4
    assert profile["column_count"] == 2

    district_col = next(c for c in profile["columns"] if c["name"] == "district")
    assert district_col["null_count"] == 1
    assert district_col["distinct_count"] == 2

    count_col = next(c for c in profile["columns"] if c["name"] == "count")
    assert count_col["min"] == "1"
    assert count_col["max"] == "4"


def test_profile_detects_duplicates():
    df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
    profile = profile_dataframe(df)
    assert profile["duplicate_row_count"] == 1


def test_profile_never_includes_raw_values_beyond_min_max(sample_crime_csv):
    df, profile = load_and_profile_csv(str(sample_crime_csv))
    assert len(df) == 600
    # Only column-level metadata should appear — no per-row content.
    serialized_keys = {tuple(c.keys()) for c in profile["columns"]}
    for keys in serialized_keys:
        assert set(keys) <= {"name", "dtype", "null_count", "distinct_count", "min", "max"}
