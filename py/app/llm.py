"""LLM providers behind the LLMClient interface.

Currently: Gemini, via Google's google-genai SDK and its Interactions API
with a JSON schema response format. The key is read from GEMINI_API_KEY
(loaded from py/.env). Never commit that file.

To add a provider, write a class with `model_name` and
`generate_json(prompt, schema) -> str`, then register it in make_llm().
"""

import os

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"  # cheapest current Flash tier


class GeminiClient:
    def __init__(self, model_name: str | None = None) -> None:
        from google import genai  # imported here so tests don't need the SDK

        if not os.environ.get("GEMINI_API_KEY"):
            raise RuntimeError("GEMINI_API_KEY is not set. Add it to py/.env")
        self.model_name = model_name or os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        self._client = genai.Client()

    def generate_json(self, prompt: str, schema: dict) -> str:
        interaction = self._client.interactions.create(
            model=self.model_name,
            input=prompt,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": schema,
            },
        )
        return interaction.output_text


def make_llm(provider: str = "gemini", model: str | None = None):
    if provider == "gemini":
        return GeminiClient(model)
    raise ValueError(f"Unknown LLM provider '{provider}'. Supported: gemini")
