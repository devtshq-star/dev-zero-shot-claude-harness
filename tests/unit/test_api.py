"""API contract tests — no LLM key required; the Q&A graph is mocked where relevant."""
from unittest.mock import patch


def test_health(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "ok"


def test_upload_csv_returns_profile(api_client, sample_crime_csv):
    with open(sample_crime_csv, "rb") as f:
        r = api_client.post("/api/datasets", files={"files": ("crime_reports.csv", f, "text/csv")})
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 1
    dataset = data[0]
    assert dataset["row_count"] == 600
    assert dataset["column_count"] == 4
    column_names = {c["name"] for c in dataset["profile"]["columns"]}
    assert column_names == {"district", "crime_type", "occurred_at", "case_status"}


def test_upload_rejects_non_csv(api_client, tmp_path):
    bad_file = tmp_path / "notes.txt"
    bad_file.write_text("not a csv")
    with open(bad_file, "rb") as f:
        r = api_client.post("/api/datasets", files={"files": ("notes.txt", f, "text/plain")})
    assert r.status_code == 400


def test_list_and_get_dataset(api_client, sample_crime_csv):
    with open(sample_crime_csv, "rb") as f:
        upload = api_client.post("/api/datasets", files={"files": ("crime_reports.csv", f, "text/csv")})
    dataset_id = upload.json()["data"][0]["id"]

    listed = api_client.get("/api/datasets")
    assert listed.status_code == 200
    assert any(d["id"] == dataset_id for d in listed.json()["data"])

    detail = api_client.get(f"/api/datasets/{dataset_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["id"] == dataset_id


def test_get_dataset_not_found(api_client):
    r = api_client.get("/api/datasets/nonexistent-id")
    assert r.status_code == 404


def test_create_session(api_client, sample_crime_csv):
    with open(sample_crime_csv, "rb") as f:
        upload = api_client.post("/api/datasets", files={"files": ("crime_reports.csv", f, "text/csv")})
    dataset_id = upload.json()["data"][0]["id"]

    r = api_client.post("/api/sessions", json={"dataset_ids": [dataset_id]})
    assert r.status_code == 200
    assert r.json()["data"]["dataset_ids"] == [dataset_id]


def test_create_session_empty_dataset_ids_rejected(api_client):
    r = api_client.post("/api/sessions", json={"dataset_ids": []})
    assert r.status_code == 400


def test_create_session_unknown_dataset_rejected(api_client):
    r = api_client.post("/api/sessions", json={"dataset_ids": ["does-not-exist"]})
    assert r.status_code == 400


def test_post_message_mocked(api_client, sample_crime_csv):
    with open(sample_crime_csv, "rb") as f:
        upload = api_client.post("/api/datasets", files={"files": ("crime_reports.csv", f, "text/csv")})
    dataset_id = upload.json()["data"][0]["id"]
    session_resp = api_client.post("/api/sessions", json={"dataset_ids": [dataset_id]})
    session_id = session_resp.json()["data"]["id"]

    fake_result = {
        "turn_id": "fake-turn-id",
        "content": "There are 600 rows.",
        "table_data": None,
        "chart_spec": None,
        "needs_clarification": False,
        "token_usage": {"prompt_tokens": 100, "completion_tokens": 20, "estimated_cost_usd": 0.0001},
    }
    with patch("api.sessions.run_agent", return_value=fake_result):
        r = api_client.post(f"/api/sessions/{session_id}/messages", json={"question": "How many rows?"})

    assert r.status_code == 200
    body = r.json()["data"]
    assert body["content"] == "There are 600 rows."
    assert body["needs_clarification"] is False
    assert body["token_usage"]["prompt_tokens"] == 100


def test_post_message_session_not_found(api_client):
    r = api_client.post("/api/sessions/nonexistent-id/messages", json={"question": "test"})
    assert r.status_code == 404


def test_post_message_empty_question_rejected(api_client, sample_crime_csv):
    with open(sample_crime_csv, "rb") as f:
        upload = api_client.post("/api/datasets", files={"files": ("crime_reports.csv", f, "text/csv")})
    dataset_id = upload.json()["data"][0]["id"]
    session_resp = api_client.post("/api/sessions", json={"dataset_ids": [dataset_id]})
    session_id = session_resp.json()["data"]["id"]

    r = api_client.post(f"/api/sessions/{session_id}/messages", json={"question": ""})
    assert r.status_code == 400


def test_get_session_detail_includes_turns(api_client, sample_crime_csv):
    with open(sample_crime_csv, "rb") as f:
        upload = api_client.post("/api/datasets", files={"files": ("crime_reports.csv", f, "text/csv")})
    dataset_id = upload.json()["data"][0]["id"]
    session_resp = api_client.post("/api/sessions", json={"dataset_ids": [dataset_id]})
    session_id = session_resp.json()["data"]["id"]

    fake_result = {
        "turn_id": "fake-turn-id",
        "content": "Answer.",
        "table_data": None,
        "chart_spec": None,
        "needs_clarification": False,
        "token_usage": {"prompt_tokens": 1, "completion_tokens": 1, "estimated_cost_usd": 0.0},
    }
    with patch("api.sessions.run_agent", return_value=fake_result):
        api_client.post(f"/api/sessions/{session_id}/messages", json={"question": "How many rows?"})

    detail = api_client.get(f"/api/sessions/{session_id}")
    assert detail.status_code == 200
    turns = detail.json()["data"]["turns"]
    assert len(turns) == 1  # the user turn is persisted by the route; the mocked assistant turn is not
    assert turns[0]["role"] == "user"
    assert turns[0]["content"] == "How many rows?"
