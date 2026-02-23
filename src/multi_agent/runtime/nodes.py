from dataclasses import dataclass
from typing import Any

from src.multi_agent.agents import DockerAgent

from .states import CoordinatorState, DockerWorkerState


@dataclass
class DockerWorkerNode:
    worker: DockerAgent
    verbose_callbacks: list[Any] | None = None

    def invoke(self, state: DockerWorkerState) -> dict[str, str]:
        try:
            callbacks = self.verbose_callbacks
            response = self.worker.invoke(
                state.request or "",
                thread_id=state.thread_id,
                callbacks=callbacks,
            )
            return {"response": response}
        except Exception as exc:
            return {"error": f"Docker worker error: {exc}"}


@dataclass
class CoordinatorDockerNode:
    docker_node: DockerWorkerNode

    def invoke(self, state: CoordinatorState) -> dict[str, str]:
        worker_state = DockerWorkerState(
            request=state.docker_request or state.user_input or "",
            thread_id=state.thread_id,
        )
        result = self.docker_node.invoke(worker_state)

        if result.get("error"):
            return {"error": result.get("error", "")}

        return {"docker_response": result.get("response", "")}


@dataclass
class FinalizeNode:
    def invoke(self, state: CoordinatorState) -> dict[str, str]:
        if state.error:
            return {"final_response": state.error}
        return {"final_response": state.docker_response or ""}
