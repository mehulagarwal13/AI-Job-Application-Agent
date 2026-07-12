"""
LLMRouter — the only entry point application code uses to talk to any LLM.

    from app.ai.llm import llm_router
    text = llm_router.run(task="resume_parse", prompt=..., system=...)

Responsibilities:
- Resolve the task to a (provider, model, params) route from the registry.
- Lazily instantiate and cache providers.
- Retry transient failures with exponential backoff (call sites stay clean).
- Raise a single, predictable exception type (LLMRouterError).
"""

import logging
import time

from app.ai.llm.base import LLMProvider, LLMError
from app.ai.llm.registry import TASK_ROUTES, PROVIDER_FACTORIES

logger = logging.getLogger(__name__)


class LLMRouterError(Exception):
    """Raised when a task cannot be completed after all retries."""


class LLMRouter:
    def __init__(self, max_attempts: int = 3, backoff_base_seconds: float = 1.0):
        self._providers: dict[str, LLMProvider] = {}
        self._max_attempts = max_attempts
        self._backoff_base = backoff_base_seconds

    def _get_provider(self, name: str) -> LLMProvider:
        if name not in self._providers:
            factory = PROVIDER_FACTORIES.get(name)
            if factory is None:
                raise LLMRouterError(f"Unknown LLM provider: '{name}'")
            self._providers[name] = factory()
        return self._providers[name]

    def run(
        self,
        *,
        task: str,
        prompt: str,
        system: str | None = None,
        **overrides,
    ) -> str:
        """
        Executes `task` with its configured route. Keyword overrides
        (temperature, max_tokens, json_mode, model) apply per call.
        """
        route = TASK_ROUTES.get(task)
        if route is None:
            raise LLMRouterError(
                f"Unknown LLM task: '{task}'. Register it in app/ai/llm/registry.py"
            )

        provider = self._get_provider(route.provider)
        params = {
            "model": overrides.get("model", route.model),
            "temperature": overrides.get("temperature", route.temperature),
            "max_tokens": overrides.get("max_tokens", route.max_tokens),
            "json_mode": overrides.get("json_mode", route.json_mode),
        }

        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                return provider.complete(prompt=prompt, system=system, **params)
            except LLMError as e:
                last_error = e
                if attempt < self._max_attempts:
                    delay = self._backoff_base * (2 ** (attempt - 1))
                    logger.warning(
                        "LLM task '%s' attempt %d/%d failed: %s — retrying in %.1fs",
                        task, attempt, self._max_attempts, e, delay,
                    )
                    time.sleep(delay)

        raise LLMRouterError(
            f"LLM task '{task}' failed after {self._max_attempts} attempts: {last_error}"
        ) from last_error


# Module-level singleton — providers and their HTTP clients are reused app-wide.
llm_router = LLMRouter()
