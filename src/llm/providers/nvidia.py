from openai import OpenAI


class NvidiaProvider:
    """OpenAI-compatible client for NVIDIA NIM (https://integrate.api.nvidia.com/v1)."""

    DEFAULT_MODEL = "nvidia/llama-3.3-nemotron-super-49b-v1"
    DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"

    # Rough per-token cost estimate for the UI's cost readout — NIM pricing is
    # low relative to frontier models; adjust if NVIDIA publishes exact rates.
    _PROMPT_COST_PER_TOKEN = 0.00000015
    _COMPLETION_COST_PER_TOKEN = 0.00000060

    def __init__(self, api_key: str, model: str, base_url: str = "") -> None:
        self._client = OpenAI(api_key=api_key, base_url=base_url or self.DEFAULT_BASE_URL)
        self._model = model or self.DEFAULT_MODEL

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        text, _ = self.call_model_with_usage(prompt, system=system)
        return text

    def call_model_with_usage(self, prompt: str, *, system: str | None = None) -> tuple[str, dict]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.2,
            max_tokens=1024,
        )
        text = response.choices[0].message.content or ""
        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        estimated_cost = (
            prompt_tokens * self._PROMPT_COST_PER_TOKEN
            + completion_tokens * self._COMPLETION_COST_PER_TOKEN
        )
        return text, {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "estimated_cost_usd": round(estimated_cost, 6),
        }
