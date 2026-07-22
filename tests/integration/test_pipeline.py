"""Integration tests — require a real LLM key (NVIDIA/Anthropic/Gemini) and the
real Postgres test database. Exercise the full primary journey end-to-end."""
import pytest

from db.models import AuditLogEntryRow, ConversationSessionRow, DatasetRow
from db.session import create_db_session
from graph.runner import run_agent
from tools.csv_profiling import load_and_profile_csv


def _upload_sample_dataset(csv_path: str) -> str:
    df, profile = load_and_profile_csv(csv_path)
    with create_db_session() as session:
        dataset = DatasetRow(
            name="crime_reports.csv",
            original_filename="crime_reports.csv",
            storage_path=csv_path,
            row_count=profile["row_count"],
            column_count=profile["column_count"],
            profile={"columns": profile["columns"], "duplicate_row_count": profile["duplicate_row_count"]},
        )
        session.add(dataset)
        session.flush()
        return dataset.id


def _create_session(dataset_id: str) -> str:
    with create_db_session() as session:
        conv = ConversationSessionRow(dataset_ids=[dataset_id])
        session.add(conv)
        session.flush()
        return conv.id


@pytest.mark.usefixtures("_require_llm_key")
def test_pipeline_answers_real_question_with_computed_numbers(_isolated_db, sample_crime_csv):
    dataset_id = _upload_sample_dataset(str(sample_crime_csv))
    session_id = _create_session(dataset_id)

    result = run_agent(session_id, "How many rows are in this dataset?")

    assert result["needs_clarification"] is False
    assert result["content"] is not None
    assert "600" in result["content"]
    assert result["token_usage"]["prompt_tokens"] > 0

    with create_db_session() as session:
        entries = session.query(AuditLogEntryRow).filter(AuditLogEntryRow.session_id == session_id).all()
        assert len(entries) == 1
        assert entries[0].exec_status == "success"
        assert entries[0].generated_code is not None


@pytest.mark.usefixtures("_require_llm_key")
def test_pipeline_breakdown_by_district_matches_real_data(_isolated_db, sample_crime_csv):
    dataset_id = _upload_sample_dataset(str(sample_crime_csv))
    session_id = _create_session(dataset_id)

    result = run_agent(session_id, "How many rows have district equal to Lucknow?")

    assert result["content"] is not None
    # 600 rows across 6 districts, evenly distributed by construction -> 100 each
    assert "100" in result["content"]


@pytest.mark.usefixtures("_require_llm_key")
def test_pipeline_via_api_full_round_trip(api_client, sample_crime_csv):
    with open(sample_crime_csv, "rb") as f:
        upload = api_client.post("/api/datasets", files={"files": ("crime_reports.csv", f, "text/csv")})
    dataset_id = upload.json()["data"][0]["id"]

    session_resp = api_client.post("/api/sessions", json={"dataset_ids": [dataset_id]})
    session_id = session_resp.json()["data"]["id"]

    r = api_client.post(f"/api/sessions/{session_id}/messages", json={"question": "How many rows are there?"})
    assert r.status_code == 200
    body = r.json()["data"]
    assert "600" in body["content"]
    assert body["token_usage"]["prompt_tokens"] > 0

    detail = api_client.get(f"/api/sessions/{session_id}")
    turns = detail.json()["data"]["turns"]
    assert len(turns) == 2  # user question + assistant answer
    assert turns[0]["role"] == "user"
    assert turns[1]["role"] == "assistant"


@pytest.mark.usefixtures("_require_llm_key")
def test_pipeline_returns_follow_ups(api_client, sample_crime_csv):
    with open(sample_crime_csv, "rb") as f:
        upload = api_client.post("/api/datasets", files={"files": ("crime_reports.csv", f, "text/csv")})
    dataset_id = upload.json()["data"][0]["id"]
    session_id = api_client.post("/api/sessions", json={"dataset_ids": [dataset_id]}).json()["data"]["id"]

    r = api_client.post(f"/api/sessions/{session_id}/messages",
                        json={"question": "How many rows are grouped by district?"})
    assert r.status_code == 200
    follow_ups = r.json()["data"]["follow_ups"]
    assert isinstance(follow_ups, list)
    # persisted on the turn and returned in history
    detail = api_client.get(f"/api/sessions/{session_id}")
    assistant_turns = [t for t in detail.json()["data"]["turns"] if t["role"] == "assistant"]
    assert assistant_turns and "follow_ups" in assistant_turns[-1]


@pytest.mark.usefixtures("_require_llm_key")
def test_pipeline_multi_file_join(api_client, sample_crime_csv, sample_stations_csv):
    with open(sample_crime_csv, "rb") as f:
        d1 = api_client.post("/api/datasets", files={"files": ("crime_reports.csv", f, "text/csv")}).json()["data"][0]["id"]
    with open(sample_stations_csv, "rb") as f:
        d2 = api_client.post("/api/datasets", files={"files": ("station_rosters.csv", f, "text/csv")}).json()["data"][0]["id"]

    session_id = api_client.post("/api/sessions", json={"dataset_ids": [d1, d2]}).json()["data"]["id"]

    r = api_client.post(
        f"/api/sessions/{session_id}/messages",
        json={"question": "How many officers are in the district named Lucknow?"},
    )
    assert r.status_code == 200
    body = r.json()["data"]
    # station_rosters puts 120 officers in Lucknow — answer must come from the
    # second dataset, proving both dataframes are in scope.
    assert "120" in body["content"]


@pytest.mark.usefixtures("_require_llm_key")
def test_pipeline_conversation_history_supports_followup(api_client, sample_crime_csv):
    with open(sample_crime_csv, "rb") as f:
        upload = api_client.post("/api/datasets", files={"files": ("crime_reports.csv", f, "text/csv")})
    dataset_id = upload.json()["data"][0]["id"]
    session_resp = api_client.post("/api/sessions", json={"dataset_ids": [dataset_id]})
    session_id = session_resp.json()["data"]["id"]

    api_client.post(f"/api/sessions/{session_id}/messages", json={"question": "How many rows are there in total?"})
    r = api_client.post(f"/api/sessions/{session_id}/messages", json={"question": "And how many columns does it have?"})

    assert r.status_code == 200
    assert "4" in r.json()["data"]["content"]
