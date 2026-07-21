"""DB layer tests — no LLM key required, real PostgreSQL."""
from sqlalchemy.orm import Session

from db.models import AuditLogEntryRow, ConversationSessionRow, ConversationTurnRow, DatasetRow


def test_dataset_roundtrip(_isolated_db):
    with Session(_isolated_db) as s:
        dataset = DatasetRow(
            name="crime_reports.csv",
            original_filename="crime_reports.csv",
            storage_path="/tmp/x.csv",
            row_count=600,
            column_count=4,
            profile={"columns": [], "duplicate_row_count": 0},
        )
        s.add(dataset)
        s.commit()
        dataset_id = dataset.id

    with Session(_isolated_db) as s:
        fetched = s.get(DatasetRow, dataset_id)
        assert fetched is not None
        assert fetched.row_count == 600
        assert fetched.profile == {"columns": [], "duplicate_row_count": 0}


def test_session_and_turns(_isolated_db):
    with Session(_isolated_db) as s:
        conv = ConversationSessionRow(dataset_ids=["d1", "d2"])
        s.add(conv)
        s.commit()
        session_id = conv.id

        turn = ConversationTurnRow(session_id=session_id, role="user", content="How many rows?")
        s.add(turn)
        s.commit()

    with Session(_isolated_db) as s:
        conv = s.get(ConversationSessionRow, session_id)
        assert conv.dataset_ids == ["d1", "d2"]
        turns = s.query(ConversationTurnRow).filter(ConversationTurnRow.session_id == session_id).all()
        assert len(turns) == 1
        assert turns[0].content == "How many rows?"


def test_audit_log_entry(_isolated_db):
    with Session(_isolated_db) as s:
        conv = ConversationSessionRow(dataset_ids=["d1"])
        s.add(conv)
        s.commit()
        session_id = conv.id

        entry = AuditLogEntryRow(
            session_id=session_id,
            turn_id=None,
            question="How many rows?",
            generated_code="result = len(df)",
            exec_status="success",
            result_summary="600 rows",
            latency_ms=250,
        )
        s.add(entry)
        s.commit()

    with Session(_isolated_db) as s:
        entries = s.query(AuditLogEntryRow).filter(AuditLogEntryRow.session_id == session_id).all()
        assert len(entries) == 1
        assert entries[0].exec_status == "success"
        assert entries[0].generated_code == "result = len(df)"
