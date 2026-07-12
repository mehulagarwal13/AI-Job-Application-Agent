"""
Provider abstraction for the LLM layer.

Every provider (OpenAI today; Anthropic/Ollama/Groq tomorrow) implements the
same minimal interface, so the rest of the application never imports a vendor
SDK directly. Application code talks to the LLMRouter only.
"""

from abc import ABC, abstractmethod


class LLMError(Exception):
    """Raised by providers on any completion failure (after their own handling)."""


class LLMProvider(ABC):
    """Minimal contract every LLM provider must fulfill."""

    name: str = "base"

    @abstractmethod
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
        """
        Runs a single completion and returns the raw text content.
        Must raise LLMError on failure — never a vendor-specific exception.
        """
        raise NotImplementedError
