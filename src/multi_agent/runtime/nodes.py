from dataclasses import dataclass
from typing import Any

from src.multi_agent.agents import DockerAgent

from .docker_trajectory import DockerLoopException
from .states import CoordinatorState, DockerWorkerState


@dataclass
class RouterNode:
    def invoke(self, state: CoordinatorState) -> dict[str, str]:
        user_input = (state.user_input or "").strip()
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
    trajectory_callback: Any = None  # DockerTrajectoryCallback

    def invoke(self, state: DockerWorkerState) -> dict[str, str]:
        try:
            callbacks = [self.trajectory_callback] if self.trajectory_callback else None
            response = self.worker.invoke(
                state.request or "",
                thread_id=state.thread_id,
                callbacks=callbacks,
            )
            return {"response": response}
        except DockerLoopException as exc:
            # Pass loop alert as error for replan handling
            return {"error": str(exc)}
        except Exception as exc:
            return {"error": f"Docker worker error: {exc}"}


@dataclass
class CoordinatorDockerNode:
    docker_node: DockerWorkerNode
    replan_attempts: int = 0
    max_replan_attempts: int = 2

    def invoke(self, state: CoordinatorState) -> dict[str, str]:
        worker_state = DockerWorkerState(
            request=state.docker_request or "",
            thread_id=state.thread_id,
        )
        result = self.docker_node.invoke(worker_state)

        # Handle loop detection - trigger replan
        if result.get("error"):
            error_msg = result.get("error", "")
            if "LOOP DETECTED" in error_msg and self.replan_attempts < self.max_replan_attempts:
                self.replan_attempts += 1
                # Clear trajectory after loop detection
                if self.docker_node.trajectory_callback:
                    self.docker_node.trajectory_callback.clear()
                # Inject alert as new request with original context
                replan_request = f"""{error_msg}

ORIGINAL TASK: {state.docker_request}

ATTEMPT: {self.replan_attempts}/{self.max_replan_attempts}

Please execute a revised plan to complete the original task."""
                return {"docker_request": replan_request, "docker_response": ""}

            return {"error": error_msg}

        self.replan_attempts = 0  # Reset on success
        return {"docker_response": result.get("response", "")}


@dataclass
class FinalizeNode:
    def invoke(self, state: CoordinatorState) -> dict[str, str]:
        if state.error:
            return {"final_response": state.error}
        return {"final_response": state.docker_response or ""}
