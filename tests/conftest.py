import os
import random
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture(autouse=True)
def _reset_settings_singleton():
    import config.settings as m
    m._settings = None
    yield
    m._settings = None


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch):
    """Real PostgreSQL test database (never SQLite-as-substitute) — created
    once and its tables dropped/recreated per test for isolation."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from db.models import Base
    import db.session as session_module

    test_db_url = os.environ.get("TEST_DATABASE_URL")
    if not test_db_url:
        pytest.skip("TEST_DATABASE_URL not set — required for real-Postgres tests")

    monkeypatch.setenv("AGENT_DATABASE_URL", test_db_url)

    engine = create_engine(test_db_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(session_module, "_engine", engine)
    monkeypatch.setattr(session_module, "_SessionLocal", factory)
    monkeypatch.setattr(session_module, "init_db", lambda: None)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def _require_llm_key():
    """Skip if no LLM provider key is set — works for NVIDIA, Anthropic, or Gemini."""
    from config.settings import get_settings
    s = get_settings()
    if not s.nvidia_api_key and not s.anthropic_api_key and not s.gemini_api_key:
        pytest.skip("No LLM key set in .env (AGENT_NVIDIA_API_KEY, AGENT_ANTHROPIC_API_KEY, or AGENT_GEMINI_API_KEY)")


@pytest.fixture
def api_client(_isolated_db, tmp_path, monkeypatch):
    """FastAPI test client with isolated DB and an isolated upload dir."""
    from fastapi.testclient import TestClient
    monkeypatch.setenv("AGENT_UPLOAD_DIR", str(tmp_path / "uploads"))
    from api import create_app
    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture
def sample_crime_csv(tmp_path) -> Path:
    """A realistically-sized CSV (600 rows) so aggregate answers are
    meaningfully different from a tiny/toy fixture."""
    random.seed(42)
    districts = ["Lucknow", "Kanpur", "Varanasi", "Agra", "Meerut", "Prayagraj"]
    crime_types = ["theft", "assault", "burglary", "fraud", "vandalism"]

    path = tmp_path / "crime_reports.csv"
    lines = ["district,crime_type,occurred_at,case_status"]
    for i in range(600):
        district = districts[i % len(districts)]
        crime_type = crime_types[(i * 3) % len(crime_types)]
        month = (i % 12) + 1
        day = (i % 28) + 1
        status = "open" if i % 4 == 0 else "closed"
        lines.append(f"{district},{crime_type},2026-{month:02d}-{day:02d},{status}")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
