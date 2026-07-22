import json

import pandas as pd

from tools.code_sandbox import execute_code


def test_execute_simple_aggregation():
    df = pd.DataFrame({"district": ["Lucknow", "Kanpur", "Lucknow"], "count": [1, 2, 3]})
    result = execute_code("result = len(df)", {"crime_reports": df})
    assert result["error"] is None
    assert result["value"] == 3


def test_execute_returns_table_for_dataframe_result():
    df = pd.DataFrame({"district": ["Lucknow", "Kanpur"], "count": [5, 2]})
    code = "result = df.groupby('district')['count'].sum().reset_index()"
    result = execute_code(code, {"crime_reports": df})
    assert result["error"] is None
    assert result["table"] is not None
    assert len(result["table"]) == 2


def test_execute_captures_error_without_raising():
    df = pd.DataFrame({"a": [1, 2, 3]})
    result = execute_code("result = df['nonexistent_column'].sum()", {"crime_reports": df})
    assert result["error"] is not None
    assert result["value"] is None


def test_execute_blocks_imports():
    df = pd.DataFrame({"a": [1, 2, 3]})
    result = execute_code("import os\nresult = os.getcwd()", {"crime_reports": df})
    assert result["error"] is not None


def test_execute_multi_dataframe_join():
    crimes = pd.DataFrame({"district": ["Lucknow", "Kanpur"], "count": [10, 5]})
    stations = pd.DataFrame({"district": ["Lucknow", "Kanpur"], "officers": [50, 30]})
    code = (
        "merged = dfs['crimes'].merge(dfs['stations'], on='district')\n"
        "result = merged"
    )
    result = execute_code(code, {"crimes": crimes, "stations": stations})
    assert result["error"] is None
    assert len(result["table"]) == 2


def test_table_replaces_nan_with_none_for_valid_json():
    # A missing/empty cell becomes NaN in pandas. Emitting the literal token
    # NaN into the JSON column crashes the persist step (PostgreSQL rejects it),
    # so non-finite floats must be sanitized to null before serialization.
    df = pd.DataFrame({"district": ["Lucknow", "Kanpur"], "last_updated": [float("nan"), 3.0]})
    result = execute_code("result = df", {"crime_reports": df})
    assert result["error"] is None
    assert result["table"][0]["last_updated"] is None
    assert result["table"][1]["last_updated"] == 3.0
    # The serialized form must be valid JSON with no NaN/Infinity tokens.
    serialized = json.dumps(result["table"])
    assert "NaN" not in serialized
    assert "Infinity" not in serialized


def test_execute_times_out_on_infinite_loop():
    df = pd.DataFrame({"a": [1]})
    result = execute_code("while True:\n    pass", {"crime_reports": df}, timeout_seconds=0.5)
    assert result["error"] is not None
    assert "timeout" in result["error"].lower()
