from config.settings import get_settings
from observability.events import get_logger

log = get_logger("llm")

_ZERO_USAGE = {"prompt_tokens": 0, "completion_tokens": 0, "estimated_cost_usd": 0.0}


def _build(provider: str, model: str, api_key: str, base_url: str = ""):
    """Instantiate one provider by name. Raises if the name is unknown."""
    if provider == "nvidia":
        from llm.providers.nvidia import NvidiaProvider
        return NvidiaProvider(api_key=api_key, model=model, base_url=base_url)
    if provider == "anthropic":
        from llm.providers.anthropic import AnthropicProvider
        return AnthropicProvider(api_key=api_key, model=model)
    if provider == "gemini":
        from llm.providers.gemini import GeminiProvider
        return GeminiProvider(api_key=api_key, model=model)
    raise RuntimeError(f"Unknown LLM provider: {provider!r}. Supported: nvidia, anthropic, gemini")


def _resolve_primary(s):
    provider = s.llm_provider

    # auto-detect from whichever key is set
    if not provider:
        if s.nvidia_api_key:
            provider = "nvidia"
        elif s.anthropic_api_key:
            provider = "anthropic"
        elif s.gemini_api_key:
            provider = "gemini"
        else:
            raise RuntimeError(
                "No LLM provider configured. Set AGENT_NVIDIA_API_KEY, "
                "AGENT_ANTHROPIC_API_KEY, or AGENT_GEMINI_API_KEY in .env, "
                "or set AGENT_LLM_PROVIDER explicitly."
            )

    key_by_provider = {
        "nvidia": s.nvidia_api_key,
        "anthropic": s.anthropic_api_key,
        "gemini": s.gemini_api_key,
    }
    api_key = key_by_provider.get(provider, "")
    return provider, _build(provider, s.llm_model, api_key, s.llm_base_url)


def _resolve_fallback(s):
    """The optional fallback provider, or None when not configured."""
    if s.fallback_provider and s.fallback_api_key:
        return s.fallback_provider, _build(
            s.fallback_provider, s.fallback_model, s.fallback_api_key, s.fallback_base_url
        )
    return None


def _call(provider, prompt: str, system: str | None) -> tuple[str, dict]:
    """Invoke one provider, normalizing to (text, usage). Providers without
    native usage reporting return a zeroed usage dict rather than raising."""
    if hasattr(provider, "call_model_with_usage"):
        return provider.call_model_with_usage(prompt, system=system)
    text = provider.call_model(prompt, system=system)
    return text, dict(_ZERO_USAGE)


class LLMClient:
    def __init__(self) -> None:
        s = get_settings()
        self._primary_name, self._primary = _resolve_primary(s)
        fallback = _resolve_fallback(s)
        self._fallback_name, self._fallback = fallback if fallback else (None, None)

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        text, _ = self.call_model_with_usage(prompt, system=system)
        return text

    def call_model_with_usage(self, prompt: str, *, system: str | None = None) -> tuple[str, dict]:
        """Call the primary provider; on any error, fall back to the configured
        fallback provider (if any) for this single call. If there is no fallback,
        or the fallback also fails, the error propagates."""
        try:
            return _call(self._primary, prompt, system=system)
        except Exception as exc:  # noqa: BLE001 - deliberately broad: any primary failure triggers fallback
            if self._fallback is None:
                raise
            log.warning(
                "primary_llm_failed_falling_back",
                primary=self._primary_name,
                fallback=self._fallback_name,
                error=str(exc),
            )
            return _call(self._fallback, prompt, system=system)
