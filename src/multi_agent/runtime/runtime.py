from dataclasses import dataclass, field
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.multi_agent.agents import create_docker_agent

from .docker_trajectory import DockerTrajectoryCallback
from .nodes import CoordinatorDockerNode, DockerWorkerNode, FinalizeNode, RouterNode
from .states import CoordinatorState


@dataclass
class DockerGraphRuntime:
    docker_node: DockerWorkerNode
    router_node: RouterNode
    coordinator_docker_node: CoordinatorDockerNode
    finalize_node: FinalizeNode
    graph: Any
    trajectory_callback: DockerTrajectoryCallback = field(default_factory=DockerTrajectoryCallback)

    @classmethod
    def create(
        cls,
        model: str | None = None,
        temperature: float = 0.0,
        workspace_dir: str | None = None,
        skills_dir: str | None = None,
        app_title: str = "MultiAgentDocker",
        enable_hitl: bool = False,
    ) -> "DockerGraphRuntime":
        trajectory_callback = DockerTrajectoryCallback(max_retries=3)

        worker = create_docker_agent(
            model=model,
            temperature=temperature,
            workspace_dir=workspace_dir,
            skills_dir=skills_dir,
            app_title=app_title,
            enable_hitl=enable_hitl,
        )
        docker_node = DockerWorkerNode(worker=worker, trajectory_callback=trajectory_callback)
        router_node = RouterNode()
        coordinator_docker_node = CoordinatorDockerNode(docker_node=docker_node)
        finalize_node = FinalizeNode()

        runtime = cls(
            docker_node=docker_node,
            router_node=router_node,
            coordinator_docker_node=coordinator_docker_node,
            finalize_node=finalize_node,
            graph=None,
            trajectory_callback=trajectory_callback,
        )
        runtime.graph = runtime._build_graph()
        return runtime

    def _route_after_router(self, state: CoordinatorState) -> str:
        if state.error:
            return "finalize_response"
        if state.route == "docker":
            return "run_docker"
        return "finalize_response"

    def _route_after_docker(self, state: CoordinatorState) -> str:
        """Route after docker execution - handle replan or finalize."""
        # If docker_request is set with LOOP DETECTED, it's a replan request
        if state.docker_request and "LOOP DETECTED" in state.docker_request:
            return "run_docker"  # Re-route to docker node with replan prompt
        if state.error:
            return "finalize_response"
        return "finalize_response"

    def _build_graph(self):
        builder = StateGraph(CoordinatorState)
        builder.add_node("route_request", self.router_node.invoke)
        builder.add_node("run_docker", self.coordinator_docker_node.invoke)
        builder.add_node("finalize_response", self.finalize_node.invoke)

        builder.add_edge(START, "route_request")
        builder.add_conditional_edges(
            "route_request",
            self._route_after_router,
            {
                "run_docker": "run_docker",
                "finalize_response": "finalize_response",
            },
        )
        builder.add_conditional_edges(
            "run_docker",
            self._route_after_docker,
            {
                "run_docker": "run_docker",  # Replan loop
                "finalize_response": "finalize_response",
            },
        )
        builder.add_edge("finalize_response", END)
        return builder.compile(checkpointer=MemorySaver())

    def run_turn(self, user_input: str, thread_id: str) -> str:
        initial_state = CoordinatorState(
            origin="cli",
            user_input=user_input,
            thread_id=thread_id,
        )
        result = self.graph.invoke(
            initial_state,
            config={"recursion_limit": 200, "configurable": {"thread_id": thread_id}},
        )
        return result.get("final_response", "") or ""


def create_docker_graph_runtime(
    model: str | None = None,
    temperature: float = 0.0,
    workspace_dir: str | None = None,
    skills_dir: str | None = None,
    app_title: str = "MultiAgentDocker",
    enable_hitl: bool = False,
) -> DockerGraphRuntime:
    return DockerGraphRuntime.create(
        model=model,
        temperature=temperature,
        workspace_dir=workspace_dir,
        skills_dir=skills_dir,
        app_title=app_title,
        enable_hitl=enable_hitl,
    )
