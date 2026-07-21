import pandas as pd


def profile_dataframe(df: pd.DataFrame) -> dict:
    """Pure function: dataframe -> profile dict (columns/dtypes/null-counts/duplicates).

    Never returns raw cell values beyond min/max on numeric/datetime columns —
    the profile is safe to pass to an LLM prompt.
    """
    columns = []
    for col in df.columns:
        series = df[col]
        dtype = str(series.dtype)
        entry: dict = {
            "name": str(col),
            "dtype": dtype,
            "null_count": int(series.isna().sum()),
            "distinct_count": int(series.nunique(dropna=True)),
            "min": None,
            "max": None,
        }
        if pd.api.types.is_numeric_dtype(series) or pd.api.types.is_datetime64_any_dtype(series):
            non_null = series.dropna()
            if len(non_null) > 0:
                entry["min"] = str(non_null.min())
                entry["max"] = str(non_null.max())
        columns.append(entry)

    duplicate_row_count = int(df.duplicated().sum())

    return {
        "columns": columns,
        "duplicate_row_count": duplicate_row_count,
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
    }


def load_and_profile_csv(path: str) -> tuple[pd.DataFrame, dict]:
    df = pd.read_csv(path)
    return df, profile_dataframe(df)
