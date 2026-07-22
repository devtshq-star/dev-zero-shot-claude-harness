"""Render a turn's result table to CSV or PDF bytes — pure formatting, no LLM,
no re-computation. Operates only on the already-stored `table_data`.

The PDF is a government-style "TECHNICAL HEADQUARTER — UTTAR PRADESH POLICE"
analysis report: branded repeating header, KPI summary cards, an enterprise BI
data table (striped rows, navy heading, right-aligned numbers, auto widths,
heading repeated across pages, rows never split), a light diagonal watermark and
a confidential footer with "Page X of Y".
"""
import csv
import io
import re
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Styles — official, restrained government palette (no gradients).
# ---------------------------------------------------------------------------
NAVY = (13, 31, 74)        # table heading / titles
BLUE = (30, 64, 128)       # section headings / accents
RED = (176, 32, 44)        # confidential label
GREY = (110, 116, 128)     # secondary text / footer
LIGHT_GREY = (243, 245, 249)  # even-row / card fill
BORDER = (210, 214, 224)   # hairline borders
WHITE = (255, 255, 255)

LOGO_PATH = Path(__file__).parent / "assets" / "up_police_logo.png"

# Page geometry (mm) — A4, generous government margins.
MARGIN_L = 18
MARGIN_R = 18
MARGIN_TOP = 25
MARGIN_BOTTOM = 20


# ---------------------------------------------------------------------------
# CSV (unchanged)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Value formatting utilities
# ---------------------------------------------------------------------------
_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[ T].*)?$")
_MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _latin1(text: str) -> str:
    # fpdf2's core fonts are latin-1 only; drop characters they can't encode
    # rather than crashing on an export.
    return str(text).encode("latin-1", "replace").decode("latin-1")


def _is_number(value) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        try:
            float(value.replace(",", ""))
            return True
        except (ValueError, AttributeError):
            return False
    return False


def _fmt_number(value, decimals: int | None = None) -> str:
    try:
        num = float(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return str(value)
    if decimals is None:
        decimals = 0 if num == int(num) else 2
    return f"{num:,.{decimals}f}"


def _fmt_date(value) -> str:
    m = _ISO_DATE.match(str(value))
    if not m:
        return str(value)
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if 1 <= mo <= 12:
        return f"{d:02d}-{_MONTHS[mo]}-{y}"
    return str(value)


def _numeric_columns(table: list[dict], fieldnames: list[str]) -> dict[str, int]:
    """Map each fully-numeric column to a fixed decimal count (2 if any value in
    the column has a fractional part, else 0) so a column formats consistently."""
    numeric: dict[str, int] = {}
    for name in fieldnames:
        present = [r.get(name) for r in table if r.get(name) not in (None, "")]
        if present and all(_is_number(v) for v in present):
            has_fraction = any(float(str(v).replace(",", "")) % 1 != 0 for v in present)
            numeric[name] = 2 if has_fraction else 0
    return numeric


def _display_value(value, decimals: int | None) -> str:
    if value is None or value == "":
        return "-"
    if decimals is not None:
        return _fmt_number(value, decimals)
    return _fmt_date(value)


def _col_weights(table: list[dict], fieldnames: list[str], sample: int = 60) -> list[float]:
    """Relative column widths from the longest content in each column (clamped)."""
    weights = []
    for name in fieldnames:
        longest = len(str(name))
        for row in table[:sample]:
            longest = max(longest, len(str(row.get(name, ""))))
        weights.append(min(max(longest, 4), 40))
    return weights


# ---------------------------------------------------------------------------
# The report document — header() and footer() repeat on every page.
# ---------------------------------------------------------------------------
def _build_pdf(table: list[dict], meta: dict):
    from fpdf import FPDF
    from fpdf.enums import Align
    from fpdf.fonts import FontFace

    fieldnames = list(table[0].keys()) if table else []
    # Wide tables read better in landscape; otherwise stay portrait.
    orientation = "L" if len(fieldnames) > 5 else "P"

    class GovReport(FPDF):
        def header(self) -> None:
            self._watermark()
            if self.page_no() == 1:
                self._brand_header_full()
            else:
                self._brand_header_compact()

        def footer(self) -> None:
            self.set_y(-15)
            self.set_draw_color(*BORDER)
            self.set_line_width(0.2)
            self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
            self.ln(1.5)
            self.set_font("Helvetica", "", 7.5)
            self.set_text_color(*GREY)
            left = "Generated by Technical Headquarters  ·  Confidential Government Document"
            right = f"Page {self.page_no()} of {{nb}}"
            self.cell((self.w - self.l_margin - self.r_margin) * 0.75, 4, _latin1(left), align="L")
            self.cell((self.w - self.l_margin - self.r_margin) * 0.25, 4, right, align="R")
            self.set_xy(self.l_margin, self.get_y() + 4)
            self.set_font("Helvetica", "", 7)
            self.cell(0, 4, _latin1(f"Generated on: {meta['generated_on']}"), align="L")

        # -- header pieces -------------------------------------------------
        def _watermark(self) -> None:
            with self.local_context(fill_opacity=0.05, stroke_opacity=0.05):
                self.set_font("Helvetica", "B", 46)
                self.set_text_color(*NAVY)
                with self.rotation(45, self.w / 2, self.h / 2):
                    self.set_xy(0, self.h / 2 - 10)
                    self.cell(self.w, 20, "UTTAR PRADESH POLICE", align="C")

        def _confidential_tag(self) -> None:
            self.set_font("Helvetica", "B", 8)
            self.set_text_color(*RED)
            self.set_xy(self.w - self.r_margin - 40, 8)
            self.cell(40, 4, "CONFIDENTIAL", align="R")

        def _brand_header_full(self) -> None:
            self._confidential_tag()
            top = 12
            logo_w = 26
            if LOGO_PATH.exists():
                self.image(str(LOGO_PATH), x=(self.w - logo_w) / 2, y=top, w=logo_w, keep_aspect_ratio=True)
                text_y = top + logo_w + 2
            else:
                self._vector_seal((self.w - 22) / 2, top, 22)
                text_y = top + 24
            self.set_y(text_y)
            self.set_font("Helvetica", "B", 13)
            self.set_text_color(*NAVY)
            self.cell(0, 6, "TECHNICAL HEADQUARTER", align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_font("Helvetica", "B", 15)
            self.set_text_color(*BLUE)
            self.cell(0, 7, "UTTAR PRADESH POLICE", align="C", new_x="LMARGIN", new_y="NEXT")
            self.ln(1.5)
            self.set_font("Helvetica", "B", 20)
            self.set_text_color(*NAVY)
            self.cell(0, 9, _latin1(self._spaced("ANALYSIS REPORT")), align="C", new_x="LMARGIN", new_y="NEXT")
            self.ln(1)
            self._rule()
            self.set_y(self.get_y() + 3)

        def _brand_header_compact(self) -> None:
            self._confidential_tag()
            logo_w = 11
            y = 10
            if LOGO_PATH.exists():
                self.image(str(LOGO_PATH), x=self.l_margin, y=y, w=logo_w, keep_aspect_ratio=True)
            self.set_xy(self.l_margin + logo_w + 3, y + 1)
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(*NAVY)
            self.cell(0, 4, "TECHNICAL HEADQUARTER · UTTAR PRADESH POLICE", new_x="LMARGIN", new_y="NEXT")
            self.set_x(self.l_margin + logo_w + 3)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(*GREY)
            self.cell(0, 4, _latin1(meta["report_name"]), new_x="LMARGIN", new_y="NEXT")
            self.set_y(y + logo_w + 1)
            self._rule()
            self.set_y(self.get_y() + 3)

        def _vector_seal(self, x: float, y: float, size: float) -> None:
            """Fallback emblem when no logo PNG is supplied — a simple navy seal."""
            self.set_draw_color(*NAVY)
            self.set_line_width(0.6)
            self.set_fill_color(*LIGHT_GREY)
            self.ellipse(x, y, size, size, style="D")
            self.ellipse(x + 2, y + 2, size - 4, size - 4, style="D")
            self.set_font("Helvetica", "B", 7)
            self.set_text_color(*NAVY)
            self.set_xy(x, y + size / 2 - 2.5)
            self.cell(size, 5, "U.P.\nPOLICE", align="C")

        def _rule(self) -> None:
            self.set_draw_color(*BLUE)
            self.set_line_width(0.5)
            self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())

        @staticmethod
        def _spaced(text: str) -> str:
            return " ".join(text)

    pdf = GovReport(orientation=orientation, unit="mm", format="A4")
    pdf.set_title(_latin1(meta["report_name"]))
    pdf.set_author("Technical Headquarter, Uttar Pradesh Police")
    pdf.set_margins(MARGIN_L, MARGIN_TOP, MARGIN_R)
    pdf.set_auto_page_break(auto=True, margin=MARGIN_BOTTOM)
    pdf.alias_nb_pages()  # resolves {nb} in the footer
    pdf.add_page()

    _section_title(pdf, "Report Information")
    _info_card(pdf, meta, table, fieldnames)
    pdf.ln(4)

    _section_title(pdf, "Summary")
    _summary_cards(pdf, table, fieldnames)
    pdf.ln(4)

    _section_title(pdf, "Data")
    if not table:
        _empty_notice(pdf)
    else:
        _data_table(pdf, table, fieldnames, FontFace, Align)

    return bytes(pdf.output())


# ---------------------------------------------------------------------------
# Section building blocks
# ---------------------------------------------------------------------------
def _section_title(pdf, text: str) -> None:
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*BLUE)
    pdf.cell(0, 6, _latin1(text), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*BORDER)
    pdf.set_line_width(0.3)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(3)


def _info_card(pdf, meta: dict, table: list[dict], fieldnames: list[str]) -> None:
    rows = [
        ("Report Name", meta["report_name"]),
        ("Generated On", meta["generated_on"]),
        ("Generated By", meta.get("generated_by", "System Administrator")),
        ("Report ID", meta.get("report_id", "-")),
        ("Total Records", f"{len(table):,}"),
        ("Data Columns", f"{len(fieldnames):,}"),
    ]
    inner_w = pdf.w - pdf.l_margin - pdf.r_margin
    col_w = inner_w / 2
    label_w = 34
    line_h = 7
    start_y = pdf.get_y()
    n_rows = (len(rows) + 1) // 2

    pdf.set_fill_color(*LIGHT_GREY)
    pdf.set_draw_color(*BORDER)
    pdf.set_line_width(0.3)
    pdf.rect(pdf.l_margin, start_y, inner_w, n_rows * line_h + 4, style="DF")

    for i, (label, value) in enumerate(rows):
        r, c = divmod(i, 2)
        x = pdf.l_margin + c * col_w + 3
        y = start_y + 2 + r * line_h
        pdf.set_xy(x, y)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*GREY)
        pdf.cell(label_w, line_h, _latin1(f"{label}"), align="L")
        pdf.set_xy(x + label_w, y)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*NAVY)
        pdf.cell(col_w - label_w - 6, line_h, _latin1(str(value)), align="L")

    pdf.set_y(start_y + n_rows * line_h + 4)


def _summary_cards(pdf, table: list[dict], fieldnames: list[str]) -> None:
    numeric = _numeric_columns(table, fieldnames)
    cards: list[tuple[str, str]] = [
        ("Total Records", f"{len(table):,}"),
        ("Data Columns", f"{len(fieldnames):,}"),
    ]
    for name in fieldnames:
        if name in numeric and len(cards) < 4:
            total = sum(float(str(r.get(name)).replace(",", "")) for r in table if r.get(name) not in (None, ""))
            cards.append((f"Sum of {name}", _fmt_number(total, numeric[name])))

    inner_w = pdf.w - pdf.l_margin - pdf.r_margin
    gap = 4
    n = len(cards)
    card_w = (inner_w - gap * (n - 1)) / n
    card_h = 18
    y = pdf.get_y()

    for i, (label, value) in enumerate(cards):
        x = pdf.l_margin + i * (card_w + gap)
        pdf.set_fill_color(*WHITE)
        pdf.set_draw_color(*BORDER)
        pdf.set_line_width(0.3)
        pdf.rect(x, y, card_w, card_h, style="DF", round_corners=True, corner_radius=2)
        # accent bar
        pdf.set_fill_color(*BLUE)
        pdf.rect(x, y, 1.6, card_h, style="F")
        pdf.set_xy(x + 5, y + 3)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*GREY)
        pdf.cell(card_w - 7, 4, _latin1(label.upper()), align="L")
        pdf.set_xy(x + 5, y + 8)
        pdf.set_font("Helvetica", "B", 15)
        pdf.set_text_color(*NAVY)
        pdf.cell(card_w - 7, 8, _latin1(str(value)), align="L")

    pdf.set_y(y + card_h)


def _data_table(pdf, table: list[dict], fieldnames: list[str], FontFace, Align) -> None:
    numeric = _numeric_columns(table, fieldnames)
    display_cols = ["S.No", *fieldnames]
    weights = [3.0, *(_col_weights(table, fieldnames))]

    heading_style = FontFace(emphasis="BOLD", color=WHITE, fill_color=NAVY)
    # Explicit per-row fill for reliable striping (the table-level fill-mode enum
    # rendered alternate rows in the heading colour); even rows get a light tint.
    even_style = FontFace(fill_color=LIGHT_GREY)
    odd_style = FontFace(fill_color=WHITE)

    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(30, 30, 30)
    with pdf.table(
        first_row_as_headings=True,
        headings_style=heading_style,
        borders_layout="HORIZONTAL_LINES",
        line_height=6,
        col_widths=tuple(weights),
        padding=(1.6, 2.2),
        repeat_headings=1,
    ) as t:
        head = t.row()
        for name in display_cols:
            head.cell(_latin1(str(name).upper()), align="CENTER")
        for idx, row in enumerate(table, start=1):
            tr = t.row(style=even_style if idx % 2 == 0 else odd_style)
            tr.cell(str(idx), align="CENTER")
            for name in fieldnames:
                decimals = numeric.get(name)
                text = _display_value(row.get(name), decimals)
                tr.cell(_latin1(text), align="RIGHT" if decimals is not None else "LEFT")


def _empty_notice(pdf) -> None:
    pdf.ln(20)
    pdf.set_font("Helvetica", "I", 12)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 10, "No records available for selected criteria.", align="C")


# ---------------------------------------------------------------------------
# Public entry point — signature preserved (title kept for backwards compat).
# ---------------------------------------------------------------------------
def table_to_pdf_bytes(table: list[dict], title: str, meta: dict | None = None) -> bytes:
    now = datetime.now()
    full_meta = {
        "report_name": title or "Analysis Report",
        "generated_on": now.strftime("%d-%b-%Y  %H:%M"),
        "generated_by": "System Administrator",
        "report_id": "-",
    }
    if meta:
        full_meta.update({k: v for k, v in meta.items() if v is not None})
    return _build_pdf(table or [], full_meta)


def report_filename(title: str, when: datetime | None = None) -> str:
    """Government-style filename, e.g. Analysis_Report_District_Wise_2026-07-22_14-35.pdf."""
    when = when or datetime.now()
    slug = re.sub(r"[^A-Za-z0-9]+", "_", (title or "Analysis_Report")).strip("_")[:60] or "Analysis_Report"
    return f"UP_Police_Report_{slug}_{when:%Y-%m-%d_%H-%M}.pdf"
