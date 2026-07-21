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


def test_execute_times_out_on_infinite_loop():
    df = pd.DataFrame({"a": [1]})
    result = execute_code("while True:\n    pass", {"crime_reports": df}, timeout_seconds=0.5)
    assert result["error"] is not None
    assert "timeout" in result["error"].lower()
