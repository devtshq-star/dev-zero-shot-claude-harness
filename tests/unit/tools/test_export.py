from tools.export import table_to_csv_bytes, table_to_pdf_bytes


def test_csv_export_matches_rows():
    table = [
        {"district": "Lucknow", "count": 342},
        {"district": "Kanpur", "count": 210},
    ]
    out = table_to_csv_bytes(table).decode("utf-8")
    lines = out.strip().splitlines()
    assert lines[0] == "district,count"
    assert "Lucknow,342" in out
    assert "Kanpur,210" in out


def test_csv_export_handles_none_values():
    table = [{"district": "Lucknow", "count": None}]
    out = table_to_csv_bytes(table).decode("utf-8")
    assert "Lucknow," in out


def test_csv_export_empty_table():
    assert table_to_csv_bytes([]) == b""


def test_pdf_export_produces_valid_pdf():
    table = [{"district": "Lucknow", "count": 342}]
    out = table_to_pdf_bytes(table, title="How many per district?")
    assert out[:5] == b"%PDF-"
    assert len(out) > 200


def test_pdf_export_handles_unicode_title():
    table = [{"col": "value"}]
    out = table_to_pdf_bytes(table, title="COVID cases — District ₹ report")
    assert out[:5] == b"%PDF-"
