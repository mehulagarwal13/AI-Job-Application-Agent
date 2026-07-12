import pytest

from app.ai.llm.base import LLMProvider, LLMError
from app.ai.llm.registry import TASK_ROUTES, PROVIDER_FACTORIES, TaskRoute
from app.ai.llm.router import LLMRouter, LLMRouterError


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, fail_times: int = 0):
        self.fail_times = fail_times
        self.calls = 0

    def complete(self, *, model, prompt, system=None, temperature=0.0,
                 max_tokens=1000, json_mode=False) -> str:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise LLMError("transient failure")
        return f"response-from-{model}"


@pytest.fixture
def fake_route(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setitem(PROVIDER_FACTORIES, "fake", lambda: provider)
    monkeypatch.setitem(TASK_ROUTES, "test_task", TaskRoute(provider="fake", model="fake-model"))
    return provider


def test_unknown_task_raises():
    router = LLMRouter()
    with pytest.raises(LLMRouterError, match="Unknown LLM task"):
        router.run(task="does_not_exist", prompt="hi")


def test_routes_to_configured_provider(fake_route):
    router = LLMRouter(backoff_base_seconds=0)
    assert router.run(task="test_task", prompt="hi") == "response-from-fake-model"


def test_retries_transient_failures(monkeypatch):
    provider = FakeProvider(fail_times=2)  # fails twice, succeeds third
    monkeypatch.setitem(PROVIDER_FACTORIES, "flaky", lambda: provider)
    monkeypatch.setitem(TASK_ROUTES, "flaky_task", TaskRoute(provider="flaky", model="m"))

    router = LLMRouter(max_attempts=3, backoff_base_seconds=0)
    assert router.run(task="flaky_task", prompt="hi") == "response-from-m"
    assert provider.calls == 3


def test_gives_up_after_max_attempts(monkeypatch):
    provider = FakeProvider(fail_times=99)
    monkeypatch.setitem(PROVIDER_FACTORIES, "dead", lambda: provider)
    monkeypatch.setitem(TASK_ROUTES, "dead_task", TaskRoute(provider="dead", model="m"))

    router = LLMRouter(max_attempts=2, backoff_base_seconds=0)
    with pytest.raises(LLMRouterError, match="failed after 2 attempts"):
        router.run(task="dead_task", prompt="hi")


def test_model_override(fake_route):
    router = LLMRouter(backoff_base_seconds=0)
    assert router.run(task="test_task", prompt="hi", model="other") == "response-from-other"
