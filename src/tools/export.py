"""Render a turn's result table to CSV or PDF bytes — pure formatting, no LLM,
no re-computation. Operates only on the already-stored `table_data`.
"""
import csv
import io


def table_to_csv_bytes(table: list[dict]) -> bytes:
    if not table:
        return b""
    fieldnames = list(table[0].keys())
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in table:
        writer.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in fieldnames})
    return buffer.getvalue().encode("utf-8")


def table_to_pdf_bytes(table: list[dict], title: str) -> bytes:
    from fpdf import FPDF

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 13)
    pdf.multi_cell(0, 8, _latin1(title))
    pdf.ln(2)

    if not table:
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 8, "No tabular data for this answer.")
        return bytes(pdf.output())

    fieldnames = list(table[0].keys())
    page_width = pdf.w - 2 * pdf.l_margin
    col_width = page_width / max(len(fieldnames), 1)
    row_height = 7

    pdf.set_font("Helvetica", "B", 9)
    for name in fieldnames:
        pdf.cell(col_width, row_height, _truncate(_latin1(str(name)), col_width, pdf), border=1)
    pdf.ln(row_height)

    pdf.set_font("Helvetica", "", 9)
    for row in table:
        for name in fieldnames:
            value = "" if row.get(name) is None else str(row.get(name))
            pdf.cell(col_width, row_height, _truncate(_latin1(value), col_width, pdf), border=1)
        pdf.ln(row_height)

    return bytes(pdf.output())


def _latin1(text: str) -> str:
    # fpdf2's core fonts are latin-1 only; drop characters it can't encode
    # rather than crashing on an export.
    return text.encode("latin-1", "replace").decode("latin-1")


def _truncate(text: str, width_mm: float, pdf) -> str:
    while text and pdf.get_string_width(text) > width_mm - 2:
        text = text[:-1]
    return text
