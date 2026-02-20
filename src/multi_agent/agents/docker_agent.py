import os
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver

from src.multi_agent.tools import (
    COMPOSE_TOOLS,
    CONTAINER_TOOLS,
    IMAGE_TOOLS,
    NETWORK_TOOLS,
    SYSTEM_TOOLS,
    VOLUME_TOOLS,
)
from src.multi_agent.utils import create_openrouter_llm

DEFAULT_WORKSPACE = "/tmp/multi-agent-docker-workspace"
DEFAULT_SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"
SKILLS_VIRTUAL_ROOT = "/skills/"

DOCKER_AGENT_INSTRUCTIONS = """You are a Docker operations coordinator. Route Docker requests to specialized subagents and return a clear final response.

Available subagents:
- container-agent: containers (list/run/start/stop/restart/remove/logs/stats/exec/inspect)
- image-agent: images (list/pull/build/tag/remove/inspect/prune)
- network-agent: networks (list/create/connect/disconnect/remove/inspect)
- volume-agent: volumes (list/create/remove/inspect/prune)
- compose-agent: Docker Compose (up/down/ps/logs)
- system-agent: daemon/system (info/prune/version)

Workflow:
1. Identify the correct subagent for the task.
2. Delegate once with the full task description — let the subagent handle enumeration and execution together.
3. For multi-domain requests, delegate to each subagent once in dependency order.
4. Return the subagent result directly without re-verification.

Guardrails:
- Do NOT pre-list resources before delegating — include listing as part of the single delegation.
- Do not repeat identical failed delegations.
- Keep compose/build paths within the workspace root.
- When the user says "ensure accessible" or "verify it works": delegate only the run/start operation. Accessibility means the container is running with the correct port mapping — do NOT delegate any connectivity or curl check.
"""


class DockerAgent:
    def __init__(
        self,
        model: str | BaseChatModel | None = None,
        temperature: float = 0.0,
        instructions: str | None = None,
        tools: list[Any] | None = None,
        subagents: list[dict[str, Any]] | None = None,
        skills_dir: str | Path | None = None,
        workspace_dir: str | Path | None = None,
        app_title: str = "MultiAgentDocker",
    ):
        if isinstance(model, BaseChatModel):
            self._model = model
        else:
            self._model = create_openrouter_llm(
                model=model,
                temperature=temperature,
                app_title=app_title,
            )

        if tools is not None:
            self._tools = list(tools)
            self._subagents = list(subagents) if subagents is not None else []
        else:
            self._tools = []
            self._subagents = list(subagents) if subagents is not None else self._build_subagents()
        self._instructions = instructions or DOCKER_AGENT_INSTRUCTIONS

        self._workspace_dir = (
            Path(workspace_dir)
            if workspace_dir
            else Path(os.getenv("MULTI_AGENT_DOCKER_WORKSPACE", DEFAULT_WORKSPACE))
        ).expanduser()
        self._workspace_dir.mkdir(parents=True, exist_ok=True)

        if skills_dir is None:
            default_dir = DEFAULT_SKILLS_DIR
            self._skills_dir = default_dir if default_dir.exists() else None
        else:
            parsed = Path(skills_dir).expanduser()
            self._skills_dir = parsed if parsed.exists() else None

        self._skill_files = self._load_skill_files()
        self._agent = self._build_agent()

    def _load_skill_files(self) -> dict[str, dict[str, Any]]:
        if self._skills_dir is None:
            return {}

        from deepagents.backends.utils import create_file_data

        virtual_files: dict[str, dict[str, Any]] = {}
        for file_path in sorted(self._skills_dir.rglob("*")):
            if not file_path.is_file():
                continue
            relative = file_path.relative_to(self._skills_dir)
            virtual_path = f"{SKILLS_VIRTUAL_ROOT}{relative.as_posix()}"
            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            virtual_files[virtual_path] = create_file_data(content)

        return virtual_files

    def _build_subagents(self) -> list[dict[str, Any]]:
        return [
            self._build_container_subagent(),
            self._build_image_subagent(),
            self._build_network_subagent(),
            self._build_volume_subagent(),
            self._build_compose_subagent(),
            self._build_system_subagent(),
        ]

    def _build_container_subagent(self) -> dict[str, Any]:
        return {
            "name": "container-agent",
            "description": "Manages Docker containers: list, run, start, stop, restart, remove, logs, stats, exec, inspect.",
            "system_prompt": """You are a Docker container specialist.

Rules:
- Use as few tool calls as possible to complete the task.
- If a task requires knowing existing containers first (e.g. "stop all"), list once then act — do NOT list again after.
- Never re-inspect or re-list after a successful operation to "verify" it worked.
- Return a concise summary: what was done and the result. No prose explanations.
- Do not retry a failed call with identical arguments.

Strict prohibitions:
- NEVER spawn a curl, wget, ping, or any test/helper container to check connectivity or HTTP responses.
- NEVER use exec_in_container on a container started with remove=True — it will have auto-removed.
- A container that is "running" with the correct port mapping IS accessible. Do not verify network reachability.
- If told to "ensure accessible", interpret that as: container is running + port mapping is set. Stop there.""",
            "tools": list(CONTAINER_TOOLS),
        }

    def _build_image_subagent(self) -> dict[str, Any]:
        return {
            "name": "image-agent",
            "description": "Manages Docker images: list, pull, build, tag, remove, inspect, prune.",
            "system_prompt": """You are a Docker image specialist.

Rules:
- Use as few tool calls as possible to complete the task.
- If a task requires knowing existing images first (e.g. "remove all unused"), list once then act — do NOT list again after.
- Never re-inspect or re-list after a successful operation to "verify" it worked.
- Return a concise summary: what was done and the result. No prose explanations.
- Do not retry a failed call with identical arguments.""",
            "tools": list(IMAGE_TOOLS),
        }

    def _build_network_subagent(self) -> dict[str, Any]:
        return {
            "name": "network-agent",
            "description": "Manages Docker networks: list, create, remove, connect, disconnect, inspect.",
            "system_prompt": """You are a Docker network specialist.

Rules:
- Use as few tool calls as possible to complete the task.
- If a task requires knowing existing networks first, list once then act — do NOT list again after.
- Never re-inspect or re-list after a successful operation to "verify" it worked.
- Return a concise summary: what was done and the result. No prose explanations.
- Do not retry a failed call with identical arguments.""",
            "tools": list(NETWORK_TOOLS),
        }

    def _build_volume_subagent(self) -> dict[str, Any]:
        return {
            "name": "volume-agent",
            "description": "Manages Docker volumes: list, create, remove, inspect, prune.",
            "system_prompt": """You are a Docker volume specialist.

Rules:
- Use as few tool calls as possible to complete the task.
- If a task requires knowing existing volumes first, list once then act — do NOT list again after.
- Never re-inspect or re-list after a successful operation to "verify" it worked.
- Return a concise summary: what was done and the result. No prose explanations.
- Do not retry a failed call with identical arguments.""",
            "tools": list(VOLUME_TOOLS),
        }

    def _build_compose_subagent(self) -> dict[str, Any]:
        return {
            "name": "compose-agent",
            "description": "Manages Docker Compose: up, down, ps, logs.",
            "system_prompt": """You are a Docker Compose specialist.

Rules:
- Use as few tool calls as possible to complete the task.
- Never run compose_ps after up/down to verify — only check status if the operation returned an error.
- Return a concise summary: what was done and the result. No prose explanations.
- Do not retry a failed call with identical arguments.""",
            "tools": list(COMPOSE_TOOLS),
        }

    def _build_system_subagent(self) -> dict[str, Any]:
        return {
            "name": "system-agent",
            "description": "Docker system operations: info, prune, version.",
            "system_prompt": """You are a Docker system specialist.

Rules:
- Execute the requested operation in a single tool call.
- Return a concise summary of the result. No prose explanations.""",
            "tools": list(SYSTEM_TOOLS),
        }

    def _build_agent(self) -> Any:
        backend = FilesystemBackend(root_dir=str(self._workspace_dir), virtual_mode=True)
        checkpointer = MemorySaver()

        return create_deep_agent(
            model=self._model,
            tools=self._tools,
            system_prompt=self._instructions,
            subagents=self._subagents,
            backend=backend,
            skills=[SKILLS_VIRTUAL_ROOT] if self._skill_files else None,
            checkpointer=checkpointer,
        )

    def _prepare_input(self, message: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "messages": [{"role": "user", "content": message}],
        }
        if self._skill_files:
            payload["files"] = self._skill_files
        return payload

    @staticmethod
    def _extract_text(result: dict[str, Any]) -> str:
        messages = result.get("messages", [])
        if not messages:
            return str(result)

        last = messages[-1]
        content = getattr(last, "content", None)
        if content is None and isinstance(last, dict):
            content = last.get("content")

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                    continue
                if isinstance(item, dict):
                    text_value = item.get("text") or item.get("content")
                    if text_value:
                        parts.append(str(text_value))
                    continue
                parts.append(str(item))
            return "\n".join(parts).strip()

        if content is not None:
            return str(content)

        return str(last)

    def _make_config(self, thread_id: str | None, recursion_limit: int = 100) -> dict[str, Any]:
        config: dict[str, Any] = {"recursion_limit": recursion_limit}
        if thread_id:
            config["configurable"] = {"thread_id": thread_id}
        return config

    def invoke(self, message: str, thread_id: str | None = None) -> str:
        result = self._agent.invoke(self._prepare_input(message), config=self._make_config(thread_id))
        return self._extract_text(result)

    async def ainvoke(self, message: str, thread_id: str | None = None) -> str:
        result = await self._agent.ainvoke(self._prepare_input(message), config=self._make_config(thread_id))
        return self._extract_text(result)

    def stream(self, message: str, thread_id: str | None = None):
        config = self._make_config(thread_id)

        for event in self._agent.stream(self._prepare_input(message), config=config):
            yield event

    @property
    def agent(self) -> Any:
        return self._agent

    @property
    def tools(self) -> list[Any]:
        return self._tools

    @property
    def subagents(self) -> list[dict[str, Any]]:
        return self._subagents

    @property
    def workspace_dir(self) -> Path:
        return self._workspace_dir


def create_docker_agent(
    model: str | BaseChatModel | None = None,
    temperature: float = 0.0,
    instructions: str | None = None,
    tools: list[Any] | None = None,
    subagents: list[dict[str, Any]] | None = None,
    skills_dir: str | Path | None = None,
    workspace_dir: str | Path | None = None,
    app_title: str = "MultiAgentDocker",
) -> DockerAgent:
    return DockerAgent(
        model=model,
        temperature=temperature,
        instructions=instructions,
        tools=tools,
        subagents=subagents,
        skills_dir=skills_dir,
        workspace_dir=workspace_dir,
        app_title=app_title,
    )
