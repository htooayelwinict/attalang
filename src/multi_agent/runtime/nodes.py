from dataclasses import dataclass

from src.multi_agent.agents import DockerAgent

from .states import CoordinatorState, DockerWorkerState


@dataclass
class RouterNode:
    def invoke(self, state: CoordinatorState) -> CoordinatorState:
        user_input = state.get("user_input", "").strip()
        if not user_input:
            return {
                "route": "docker",
                "error": "Empty input.",
                "final_response": "Empty input.",
            }

        return {
            "route": "docker",
            "docker_request": user_input,
        }


@dataclass
class DockerWorkerNode:
    worker: DockerAgent

    def invoke(self, state: DockerWorkerState) -> DockerWorkerState:
        try:
            response = self.worker.invoke(
                state.get("request", ""),
                thread_id=state.get("thread_id"),
            )
            return {"response": response}
        except Exception as exc:
            return {"error": f"Docker worker error: {exc}"}


@dataclass
class CoordinatorDockerNode:
    docker_node: DockerWorkerNode

    def invoke(self, state: CoordinatorState) -> CoordinatorState:
        worker_state: DockerWorkerState = {
            "request": state.get("docker_request", ""),
            "thread_id": state.get("thread_id", ""),
        }
        result = self.docker_node.invoke(worker_state)
        if result.get("error"):
            return {"error": result["error"]}
        return {"docker_response": result.get("response", "")}


@dataclass
class FinalizeNode:
    def invoke(self, state: CoordinatorState) -> CoordinatorState:
        if state.get("error"):
            return {"final_response": state["error"]}
        return {"final_response": state.get("docker_response", "")}
