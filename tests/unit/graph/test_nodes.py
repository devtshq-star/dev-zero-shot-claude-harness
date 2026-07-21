"""Node-level tests — no LLM key required (LLMClient is mocked). These prove
the data-residency constraint by construction: raw row values must never
appear in any prompt sent to the LLM."""
from unittest.mock import patch

import pandas as pd

from db.models import ConversationSessionRow, ConversationTurnRow, DatasetRow
from db.session import create_db_session
from graph.nodes import classify_intent, execute_code, generate_code, load_context
from graph.state import AgentState


def _make_dataset_with_sentinel_row(db_engine) -> str:
    """A district name unlikely to appear anywhere except as a raw cell value."""
    sentinel = "Zzyzxopolis-District"
    with create_db_session() as session:
        conv = ConversationSessionRow(dataset_ids=[])
        session.add(conv)
        session.flush()
        session_id = conv.id

    import tempfile
    from tools.csv_profiling import load_and_profile_csv

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
        f.write("district,count\n")
        f.write(f"{sentinel},7\n")
        f.write("Kanpur,3\n")
        path = f.name

    df, profile = load_and_profile_csv(path)
    with create_db_session() as session:
        dataset = DatasetRow(
            name="sentinel.csv", original_filename="sentinel.csv", storage_path=path,
            row_count=profile["row_count"], column_count=profile["column_count"],
            profile={"columns": profile["columns"], "duplicate_row_count": profile["duplicate_row_count"]},
        )
        session.add(dataset)
        session.flush()
        dataset_id = dataset.id
        conv = session.get(ConversationSessionRow, session_id)
        conv.dataset_ids = [dataset_id]

    return session_id, sentinel


def test_load_context_schema_never_contains_raw_row_values(_isolated_db):
    session_id, sentinel = _make_dataset_with_sentinel_row(_isolated_db)
    state: AgentState = {"session_id": session_id, "dataset_ids": None}
    with create_db_session() as session:
        conv = session.get(ConversationSessionRow, session_id)
        state["dataset_ids"] = conv.dataset_ids

    result = load_context(state)
    assert result.get("error") is None
    schema_str = str(result["schema_context"])
    assert sentinel not in schema_str  # a string column's category values never leak into schema


def test_classify_intent_prompt_never_contains_raw_row_values(_isolated_db):
    session_id, sentinel = _make_dataset_with_sentinel_row(_isolated_db)
    with create_db_session() as session:
        conv = session.get(ConversationSessionRow, session_id)
        dataset_ids = conv.dataset_ids

    state: AgentState = {
        "session_id": session_id,
        "dataset_ids": dataset_ids,
        "question": "How many districts are there?",
    }
    state = load_context(state)
    assert state.get("error") is None

    captured_prompts = []

    def _fake_call(prompt, *, system=None):
        captured_prompts.append(prompt)
        return '{"ambiguous": false, "clarification_question": null}', {
            "prompt_tokens": 1, "completion_tokens": 1, "estimated_cost_usd": 0.0,
        }

    with patch("graph.nodes.LLMClient") as MockClient:
        MockClient.return_value.call_model_with_usage.side_effect = _fake_call
        classify_intent(state)

    assert len(captured_prompts) == 1
    assert sentinel not in captured_prompts[0]


def test_generate_code_prompt_never_contains_raw_row_values(_isolated_db):
    session_id, sentinel = _make_dataset_with_sentinel_row(_isolated_db)
    with create_db_session() as session:
        conv = session.get(ConversationSessionRow, session_id)
        dataset_ids = conv.dataset_ids

    state: AgentState = {
        "session_id": session_id,
        "dataset_ids": dataset_ids,
        "question": "How many rows are there?",
        "exec_result": None,
        "attempts": 0,
    }
    state = load_context(state)

    captured_prompts = []

    def _fake_call(prompt, *, system=None):
        captured_prompts.append(prompt)
        return "```python\nresult = len(df)\n```", {
            "prompt_tokens": 1, "completion_tokens": 1, "estimated_cost_usd": 0.0,
        }

    with patch("graph.nodes.LLMClient") as MockClient:
        MockClient.return_value.call_model_with_usage.side_effect = _fake_call
        result = generate_code(state)

    assert sentinel not in captured_prompts[0]
    assert result["generated_code"] == "result = len(df)"


def test_execute_code_runs_against_real_dataframe(_isolated_db):
    session_id, sentinel = _make_dataset_with_sentinel_row(_isolated_db)
    with create_db_session() as session:
        conv = session.get(ConversationSessionRow, session_id)
        dataset_ids = conv.dataset_ids

    state: AgentState = {"session_id": session_id, "dataset_ids": dataset_ids, "question": "x"}
    state = load_context(state)
    state["generated_code"] = "result = len(df)"

    result = execute_code(state)
    assert result["exec_result"]["error"] is None
    assert result["exec_result"]["value"] == 2  # the sentinel row + Kanpur row
