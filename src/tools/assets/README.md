# Report assets

## `up_police_logo.png` (optional)

Drop the official **Uttar Pradesh Police** logo here as `up_police_logo.png`
to have it embedded — centered at the top — in every exported PDF report.

- Format: **PNG with transparency** (recommended). JPG also works but has no
  transparency.
- Resolution: use a **high-resolution** source (≈ 500×500 px or larger). It is
  scaled down to ~26 mm wide with the aspect ratio preserved, so a large source
  stays crisp in print.
- Filename must be exactly `up_police_logo.png` (see `LOGO_PATH` in
  `src/tools/export.py`).

If the file is absent, the report falls back to a simple vector seal so exports
never break — no code change is needed once you add the PNG.
