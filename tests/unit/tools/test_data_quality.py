from tools.data_quality import compute_data_quality_flags


def test_flags_high_null_column():
    profile = {
        "columns": [
            {"name": "District_Notes", "null_count": 820, "distinct_count": 5},
            {"name": "Confirmed", "null_count": 0, "distinct_count": 700},
        ],
        "duplicate_row_count": 0,
    }
    flags = compute_data_quality_flags(profile, row_count=1000)
    assert any("District_Notes" in f and "82% null" in f for f in flags)
    assert not any("Confirmed" in f for f in flags)


def test_flags_duplicates():
    profile = {"columns": [{"name": "a", "null_count": 0, "distinct_count": 3}], "duplicate_row_count": 4}
    flags = compute_data_quality_flags(profile, row_count=10)
    assert any("4 duplicate rows" in f for f in flags)


def test_flags_constant_column():
    profile = {"columns": [{"name": "state", "null_count": 0, "distinct_count": 1}], "duplicate_row_count": 0}
    flags = compute_data_quality_flags(profile, row_count=50)
    assert any("single value" in f for f in flags)


def test_clean_data_has_no_flags():
    profile = {
        "columns": [
            {"name": "a", "null_count": 0, "distinct_count": 50},
            {"name": "b", "null_count": 1, "distinct_count": 40},
        ],
        "duplicate_row_count": 0,
    }
    assert compute_data_quality_flags(profile, row_count=50) == []
