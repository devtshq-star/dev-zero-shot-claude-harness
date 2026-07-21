import threading
import builtins as _builtins_module

import pandas as pd

_SAFE_BUILTINS = {
    name: getattr(_builtins_module, name)
    for name in (
        "len", "range", "sum", "min", "max", "sorted", "list", "dict", "set",
        "tuple", "str", "int", "float", "bool", "enumerate", "zip", "abs",
        "round", "any", "all", "map", "filter", "reversed", "True", "False", "None",
    )
}


class CodeExecutionTimeout(Exception):
    pass


def execute_code(code: str, dataframes: dict[str, pd.DataFrame], timeout_seconds: float = 5.0) -> dict:
    """Runs LLM-generated pandas code against real dataframe(s), restricted:
    no imports, no filesystem/network access, wall-clock timeout.

    The code must assign its answer to a variable named `result`. Returns
    {"value": ..., "table": [...] | None, "error": str | None} — never raises.
    """
    exec_globals = {"__builtins__": _SAFE_BUILTINS, "pd": pd, "dfs": dataframes}
    if len(dataframes) == 1:
        exec_globals["df"] = next(iter(dataframes.values()))
    exec_locals: dict = {}

    outcome: dict = {}

    def _run():
        try:
            exec(code, exec_globals, exec_locals)
            outcome["value"] = exec_locals.get("result")
        except Exception as exc:  # noqa: BLE001 - intentionally broad, this is a sandbox boundary
            outcome["error"] = f"{type(exc).__name__}: {exc}"

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        return {"value": None, "table": None, "error": f"Execution exceeded {timeout_seconds}s timeout"}

    if "error" in outcome:
        return {"value": None, "table": None, "error": outcome["error"]}

    value = outcome.get("value")
    table = _to_table(value)
    return {"value": _to_jsonable(value), "table": table, "error": None}


def _to_table(value) -> list[dict] | None:
    if isinstance(value, pd.DataFrame):
        return value.head(200).to_dict(orient="records")
    if isinstance(value, pd.Series):
        return value.reset_index().head(200).to_dict(orient="records")
    return None


def _to_jsonable(value):
    if isinstance(value, pd.DataFrame):
        return f"<DataFrame: {len(value)} rows x {len(value.columns)} cols>"
    if isinstance(value, pd.Series):
        return f"<Series: {len(value)} values>"
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:  # noqa: BLE001
            return str(value)
    return value
