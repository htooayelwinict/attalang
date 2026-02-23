from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.multi_agent.agents import create_docker_agent

from .nodes import CoordinatorDockerNode, DockerWorkerNode, FinalizeNode
from .states import CoordinatorState


@dataclass
class DockerGraphRuntime:
    docker_node: DockerWorkerNode
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
        enable_hitl: bool = False,
        provider_sort: str | None = None,
    ) -> "DockerGraphRuntime":
        worker = create_docker_agent(
            model=model,
            temperature=temperature,
            workspace_dir=workspace_dir,
            skills_dir=skills_dir,
            app_title=app_title,
            enable_hitl=enable_hitl,
            provider_sort=provider_sort,
        )
        docker_node = DockerWorkerNode(worker=worker)
        coordinator_docker_node = CoordinatorDockerNode(docker_node=docker_node)
        finalize_node = FinalizeNode()

        runtime = cls(
            docker_node=docker_node,
            coordinator_docker_node=coordinator_docker_node,
            finalize_node=finalize_node,
            graph=None,
        )
        runtime.graph = runtime._build_graph()
        return runtime

    def _route_from_start(self, state: CoordinatorState) -> str:
        if state.error:
            return "finalize_response"
        return "docker_v1_node"

    def _build_graph(self):
        builder = StateGraph(CoordinatorState)
        builder.add_node("docker_v1_node", self.coordinator_docker_node.invoke)
        builder.add_node("finalize_response", self.finalize_node.invoke)

        builder.add_conditional_edges(
            START,
            self._route_from_start,
            {
                "docker_v1_node": "docker_v1_node",
                "finalize_response": "finalize_response",
            },
        )
        builder.add_edge("docker_v1_node", "finalize_response")
        builder.add_edge("finalize_response", END)
        return builder.compile(checkpointer=MemorySaver())

    def run_turn(self, user_input: str, thread_id: str, callbacks: list[Any] | None = None) -> str:
        normalized_input = user_input.strip()
        empty_input_error = "Empty input." if not normalized_input else None
        initial_state = CoordinatorState(
            origin="cli",
            user_input=user_input,
            route=None,
            docker_request=normalized_input or None,
            docker_response=None,
            final_response=None,
            thread_id=thread_id,
            error=empty_input_error,
        )
        config: dict[str, Any] = {"recursion_limit": 200, "configurable": {"thread_id": thread_id}}

        if callbacks:
            config["callbacks"] = callbacks
            self.docker_node.verbose_callbacks = callbacks
        else:
            self.docker_node.verbose_callbacks = None

        result = self.graph.invoke(initial_state, config=config)
        return result.get("final_response", "") or ""


def create_docker_graph_runtime(
    model: str | None = None,
    temperature: float = 0.0,
    workspace_dir: str | None = None,
    skills_dir: str | None = None,
    app_title: str = "MultiAgentDocker",
    enable_hitl: bool = False,
    provider_sort: str | None = None,
) -> DockerGraphRuntime:
    return DockerGraphRuntime.create(
        model=model,
        temperature=temperature,
        workspace_dir=workspace_dir,
        skills_dir=skills_dir,
        app_title=app_title,
        enable_hitl=enable_hitl,
        provider_sort=provider_sort,
    )
