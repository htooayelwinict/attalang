from typing import cast

from langchain_core.callbacks import BaseCallbackHandler

from src.multi_agent.agents import DockerAgent
from src.multi_agent.runtime import runtime as runtime_module
from src.multi_agent.runtime.nodes import CoordinatorDockerNode, DockerWorkerNode, FinalizeNode
from src.multi_agent.runtime.runtime import DockerGraphRuntime


class StubWorker:
    def __init__(self, response: str = "ok", exc: Exception | None = None) -> None:
        self.response = response
        self.exc = exc
        self.calls: list[tuple[str, str | None]] = []

    def invoke(self, message: str, thread_id: str | None = None, callbacks: list | None = None) -> str:
        self.calls.append((message, thread_id))
        if self.exc is not None:
            raise self.exc
        return self.response


def _build_runtime(worker: StubWorker) -> DockerGraphRuntime:
    docker_node = DockerWorkerNode(worker=cast(DockerAgent, worker))
    runtime = DockerGraphRuntime(
        docker_node=docker_node,
        coordinator_docker_node=CoordinatorDockerNode(docker_node=docker_node),
        finalize_node=FinalizeNode(),
        graph=None,
    )
    runtime.graph = runtime._build_graph()
    return runtime


def test_runtime_routes_to_docker_and_returns_response() -> None:
    worker = StubWorker(response="docker-result")
    runtime = _build_runtime(worker)

    output = runtime.run_turn("list containers", thread_id="thread-1")

    assert output == "docker-result"
    assert worker.calls == [("list containers", "thread-1")]


def test_runtime_passes_thread_id_to_worker() -> None:
    worker = StubWorker(response="ok")
    runtime = _build_runtime(worker)

    runtime.run_turn("docker ps", thread_id="thread-xyz")

    assert worker.calls[-1][1] == "thread-xyz"


def test_runtime_handles_empty_input_without_worker_call() -> None:
    worker = StubWorker(response="should-not-run")
    runtime = _build_runtime(worker)

    output = runtime.run_turn("   ", thread_id="thread-empty")

    assert output == "Empty input."
    assert worker.calls == []


def test_runtime_handles_worker_exception() -> None:
    worker = StubWorker(exc=RuntimeError("boom"))
    runtime = _build_runtime(worker)

    output = runtime.run_turn("run failing command", thread_id="thread-err")

    assert output.startswith("Docker worker error:")
    assert "boom" in output


def test_create_uses_factory(monkeypatch) -> None:
    worker = StubWorker(response="factory-ok")
    monkeypatch.setattr(runtime_module, "create_docker_agent", lambda **_: worker)

    runtime = runtime_module.DockerGraphRuntime.create(model=None, temperature=0.0)

    assert isinstance(runtime, DockerGraphRuntime)
    assert runtime.run_turn("hello", thread_id="thread-create") == "factory-ok"


def test_callbacks_forwarded_to_agent() -> None:
    class Recorder:
        def __init__(self):
            self.received_callbacks = None

        def invoke(self, message, thread_id=None, callbacks=None):
            self.received_callbacks = callbacks
            return "cb-ok"

    recorder = Recorder()
    runtime = _build_runtime(cast(StubWorker, recorder))
    cb = BaseCallbackHandler()
    runtime.run_turn("test", thread_id="t", callbacks=[cb])
    assert recorder.received_callbacks == [cb]


def test_runtime_resets_error_state_for_same_thread() -> None:
    class FailThenSucceed:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str | None]] = []
            self._count = 0

        def invoke(
            self, message: str, thread_id: str | None = None, callbacks: list | None = None
        ) -> str:
            self.calls.append((message, thread_id))
            self._count += 1
            if self._count == 1:
                raise RuntimeError("boom")
            return "ok-after-error"

    worker = FailThenSucceed()
    runtime = _build_runtime(cast(StubWorker, worker))

    first = runtime.run_turn("first", thread_id="thread-1")
    second = runtime.run_turn("second", thread_id="thread-1")

    assert first.startswith("Docker worker error:")
    assert second == "ok-after-error"
    assert worker.calls == [("first", "thread-1"), ("second", "thread-1")]
