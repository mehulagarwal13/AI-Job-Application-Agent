"""OpenAI provider — the only file in the codebase allowed to import the openai SDK."""

from openai import OpenAI, OpenAIError

from app.ai.llm.base import LLMProvider, LLMError
from app.core.config import OPENAI_API_KEY


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self) -> None:
        # One client per provider instance; reused across all requests.
        # timeout: without it the SDK waits up to 10 minutes on a stuck
        # connection — the router's retry logic should kick in far sooner.
        # max_retries=0: retrying is the router's job, not the SDK's.
        self._client = OpenAI(api_key=OPENAI_API_KEY, timeout=60.0, max_retries=0)

    def complete(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1000,
        json_mode: bool = False,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {
            "model": model,
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
            "messages": messages,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = self._client.chat.completions.create(**kwargs)
        except OpenAIError as e:
            raise LLMError(f"OpenAI completion failed (model={model}): {e}") from e

        content = response.choices[0].message.content
        if content is None:
            raise LLMError(f"OpenAI returned empty content (model={model})")
        return content
