import pytest

from src.multi_agent_v2.runtime import runtime_v2 as runtime_module
from src.multi_agent_v2.runtime.runtime_v2 import DockerRuntimeV2


class StubWorker:
    def __init__(self, response: str = "ok", exc: Exception | None = None) -> None:
        self.response = response
        self.exc = exc
        self.calls: list[tuple[str, str | None]] = []

    def invoke(self, message: str, thread_id: str | None = None) -> str:
        self.calls.append((message, thread_id))
        if self.exc is not None:
            raise self.exc
        return self.response

    async def ainvoke(self, message: str, thread_id: str | None = None) -> str:
        self.calls.append((message, thread_id))
        if self.exc is not None:
            raise self.exc
        return self.response


def _build_runtime(worker: StubWorker) -> DockerRuntimeV2:
    return DockerRuntimeV2(worker=worker)  # type: ignore[arg-type]


def test_runtime_v2_routes_and_returns_response() -> None:
    worker = StubWorker(response="docker-v2-result")
    runtime = _build_runtime(worker)

    output = runtime.run_turn("list containers", thread_id="thread-1")

    assert output == "docker-v2-result"
    assert worker.calls == [("list containers", "thread-1")]


def test_runtime_v2_passes_thread_id() -> None:
    worker = StubWorker(response="ok")
    runtime = _build_runtime(worker)

    runtime.run_turn("docker ps", thread_id="thread-xyz")

    assert worker.calls[-1][1] == "thread-xyz"


def test_runtime_v2_handles_empty_input_without_worker_call() -> None:
    worker = StubWorker(response="should-not-run")
    runtime = _build_runtime(worker)

    output = runtime.run_turn("   ", thread_id="thread-empty")

    assert output == "Empty input."
    assert worker.calls == []


def test_runtime_v2_handles_worker_exception() -> None:
    worker = StubWorker(exc=RuntimeError("boom"))
    runtime = _build_runtime(worker)

    output = runtime.run_turn("run failing command", thread_id="thread-err")

    assert output.startswith("Docker worker error:")
    assert "boom" in output


@pytest.mark.asyncio
async def test_runtime_v2_async_run_turn() -> None:
    worker = StubWorker(response="async-ok")
    runtime = _build_runtime(worker)

    output = await runtime.arun_turn("docker version", thread_id="thread-async")

    assert output == "async-ok"
    assert worker.calls[-1] == ("docker version", "thread-async")


def test_runtime_v2_create_uses_factory(monkeypatch) -> None:
    worker = StubWorker(response="created")
    monkeypatch.setattr(runtime_module, "create_docker_agent_v2", lambda **_: worker)

    runtime = runtime_module.DockerRuntimeV2.create(model=None)

    assert runtime.worker is worker
    assert runtime.run_turn("hello", thread_id="thread-create") == "created"
