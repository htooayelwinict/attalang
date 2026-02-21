from typing import cast

from src.multi_agent.agents import DockerAgent
from src.multi_agent.runtime import runtime as runtime_module
from src.multi_agent.runtime.nodes import (
    CoordinatorDockerNode,
    DockerWorkerNode,
    FinalizeNode,
    RouterNode,
)
from src.multi_agent.runtime.runtime import DockerGraphRuntime


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


def _build_runtime(worker: StubWorker) -> DockerGraphRuntime:
    docker_node = DockerWorkerNode(worker=cast(DockerAgent, worker))
    runtime = DockerGraphRuntime(
        docker_node=docker_node,
        router_node=RouterNode(),
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


def test_graph_compiles_with_expected_entry_behavior(monkeypatch) -> None:
    worker = StubWorker(response="compiled-ok")
    monkeypatch.setattr(runtime_module, "create_docker_agent", lambda **_: worker)

    runtime = runtime_module.DockerGraphRuntime.create(model=None, temperature=0.0)

    assert runtime.graph.__class__.__name__ == "CompiledStateGraph"
    assert runtime.run_turn("hello", thread_id="thread-create") == "compiled-ok"
