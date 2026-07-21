from config.settings import get_settings


def _make_provider():
    s = get_settings()
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

    if provider == "nvidia":
        from llm.providers.nvidia import NvidiaProvider
        return NvidiaProvider(api_key=s.nvidia_api_key, model=s.llm_model, base_url=s.llm_base_url)
    if provider == "anthropic":
        from llm.providers.anthropic import AnthropicProvider
        return AnthropicProvider(api_key=s.anthropic_api_key, model=s.llm_model)
    if provider == "gemini":
        from llm.providers.gemini import GeminiProvider
        return GeminiProvider(api_key=s.gemini_api_key, model=s.llm_model)

    raise RuntimeError(f"Unknown LLM provider: {provider!r}. Supported: nvidia, anthropic, gemini")


class LLMClient:
    def __init__(self) -> None:
        self._provider = _make_provider()

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        return self._provider.call_model(prompt, system=system)

    def call_model_with_usage(self, prompt: str, *, system: str | None = None) -> tuple[str, dict]:
        """Returns (text, usage_dict). Providers without native usage reporting
        return a zeroed usage dict rather than raising."""
        if hasattr(self._provider, "call_model_with_usage"):
            return self._provider.call_model_with_usage(prompt, system=system)
        text = self._provider.call_model(prompt, system=system)
        return text, {"prompt_tokens": 0, "completion_tokens": 0, "estimated_cost_usd": 0.0}
