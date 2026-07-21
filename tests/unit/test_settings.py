"""Settings + provider auto-detection — no LLM key required."""
import pytest


def test_auto_detects_nvidia(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_NVIDIA_API_KEY", "nvapi-fake")
    monkeypatch.setenv("AGENT_ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("AGENT_GEMINI_API_KEY", "")
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "")
    monkeypatch.setenv("AGENT_DATABASE_URL", f"sqlite:///{tmp_path}/t.db")

    import config.settings as m
    m._settings = None
    s = m.get_settings()
    assert s.nvidia_api_key == "nvapi-fake"


def test_auto_detects_anthropic(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_NVIDIA_API_KEY", "")
    monkeypatch.setenv("AGENT_ANTHROPIC_API_KEY", "sk-ant-fake")
    monkeypatch.setenv("AGENT_GEMINI_API_KEY", "")
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "")
    monkeypatch.setenv("AGENT_DATABASE_URL", f"sqlite:///{tmp_path}/t.db")

    import config.settings as m
    m._settings = None
    s = m.get_settings()
    assert s.anthropic_api_key == "sk-ant-fake"


def test_provider_raises_with_no_key(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_NVIDIA_API_KEY", "")
    monkeypatch.setenv("AGENT_ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("AGENT_GEMINI_API_KEY", "")
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "")
    monkeypatch.setenv("AGENT_DATABASE_URL", f"sqlite:///{tmp_path}/t.db")

    import config.settings as m
    m._settings = None

    from llm.client import _make_provider
    with pytest.raises(RuntimeError, match="No LLM provider configured"):
        _make_provider()


def test_explicit_provider_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_NVIDIA_API_KEY", "nvapi-fake")
    monkeypatch.setenv("AGENT_ANTHROPIC_API_KEY", "sk-ant-fake")
    monkeypatch.setenv("AGENT_GEMINI_API_KEY", "AIza-fake")
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENT_DATABASE_URL", f"sqlite:///{tmp_path}/t.db")

    import config.settings as m
    m._settings = None
    s = m.get_settings()
    assert s.llm_provider == "anthropic"


def test_nvidia_provider_constructed(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_NVIDIA_API_KEY", "nvapi-fake")
    monkeypatch.setenv("AGENT_ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("AGENT_GEMINI_API_KEY", "")
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "")
    monkeypatch.setenv("AGENT_DATABASE_URL", f"sqlite:///{tmp_path}/t.db")

    import config.settings as m
    m._settings = None

    from llm.client import _make_provider
    from llm.providers.nvidia import NvidiaProvider
    provider = _make_provider()
    assert isinstance(provider, NvidiaProvider)
