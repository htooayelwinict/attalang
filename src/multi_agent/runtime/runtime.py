from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.multi_agent.agents import create_docker_agent

from .nodes import CoordinatorDockerNode, DockerWorkerNode, FinalizeNode, RouterNode
from .states import CoordinatorState


@dataclass
class DockerGraphRuntime:
    docker_node: DockerWorkerNode
    router_node: RouterNode
    coordinator_docker_node: CoordinatorDockerNode
    finalize_node: FinalizeNode
    graph: Any

    @classmethod
    def create(
        cls,
        model: str | None = None,
        temperature: float = 0.0,
        workspace_dir: str | None = None,
        skills_dir: str | None = None,
        app_title: str = "MultiAgentDocker",
    ) -> "DockerGraphRuntime":
        worker = create_docker_agent(
            model=model,
            temperature=temperature,
            workspace_dir=workspace_dir,
            skills_dir=skills_dir,
            app_title=app_title,
        )
        docker_node = DockerWorkerNode(worker=worker)
        router_node = RouterNode()
        coordinator_docker_node = CoordinatorDockerNode(docker_node=docker_node)
        finalize_node = FinalizeNode()

        runtime = cls(
            docker_node=docker_node,
            router_node=router_node,
            coordinator_docker_node=coordinator_docker_node,
            finalize_node=finalize_node,
            graph=None,
        )
        runtime.graph = runtime._build_graph()
        return runtime

    def _route_after_router(self, state: CoordinatorState) -> str:
        if state.get("error"):
            return "finalize_response"
        if state.get("route") == "docker":
            return "run_docker"
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
        builder.add_edge("run_docker", "finalize_response")
        builder.add_edge("finalize_response", END)
        return builder.compile(checkpointer=MemorySaver())

    def run_turn(self, user_input: str, thread_id: str) -> str:
        initial_state: CoordinatorState = {
            "origin": "cli",
            "user_input": user_input,
            "thread_id": thread_id,
        }
        result = self.graph.invoke(
            initial_state,
            config={"recursion_limit": 200, "configurable": {"thread_id": thread_id}},
        )
        return result.get("final_response", "")


def create_docker_graph_runtime(
    model: str | None = None,
    temperature: float = 0.0,
    workspace_dir: str | None = None,
    skills_dir: str | None = None,
    app_title: str = "MultiAgentDocker",
) -> DockerGraphRuntime:
    return DockerGraphRuntime.create(
        model=model,
        temperature=temperature,
        workspace_dir=workspace_dir,
        skills_dir=skills_dir,
        app_title=app_title,
    )
