"""
Task routing table — the single place where "which model handles which task" lives.

Changing a model, temperature, or provider for any task is a one-line edit here.
No application code references model names or vendor SDKs.

Routing philosophy (cost-aware):
- Cheap/structured extraction tasks -> small, fast models.
- Reasoning/generation tasks (tailoring, cover letters, career advice) -> premium models.
- Non-LLM work (embeddings, skill taxonomy matching) never enters this table —
  it stays on local open-source models (sentence-transformers) or plain Python.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskRoute:
    provider: str          # key in PROVIDER_FACTORIES
    model: str
    temperature: float = 0.0
    max_tokens: int = 1000
    json_mode: bool = False


TASK_ROUTES: dict[str, TaskRoute] = {
    # --- structured extraction (cheap, deterministic) ---
    "resume_parse": TaskRoute(
        provider="openai",
        model="gpt-4.1-mini",
        temperature=0.0,
        max_tokens=2000,
        json_mode=True,
    ),
    "job_fit_analysis": TaskRoute(
        provider="openai",
        model="gpt-4.1-mini",
        temperature=0.0,
        max_tokens=500,
        json_mode=True,
    ),
}


def _openai_factory():
    # Imported lazily so the vendor SDK only loads when actually needed.
    from app.ai.llm.providers.openai_provider import OpenAIProvider
    return OpenAIProvider()


# Adding a provider (Anthropic, Ollama, Groq...) = one provider file + one line here.
PROVIDER_FACTORIES = {
    "openai": _openai_factory,
}
