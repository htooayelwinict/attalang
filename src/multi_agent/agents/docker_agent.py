import os
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver

from src.multi_agent.tools import ALL_DOCKER_TOOLS
from src.multi_agent.utils import create_openrouter_llm

DEFAULT_WORKSPACE = "/tmp/multi-agent-docker-workspace"
DEFAULT_SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"

DOCKER_AGENT_INSTRUCTIONS = """You are an expert DevOps orchestration agent responsible for
managing Docker environments.

You have access to tools for creating networks, volumes, and running containers.

CRITICAL EXECUTION RULES:
1. Tool outputs are actively truncated to save context space. If you see
"... [TRUNCATED] ..." or "... [TRUNCATED N chars of logs] ..." in a tool response,
DO NOT assume the command failed.
2. A command is successful unless the tool output explicitly indicates an error.
Treat any of these as explicit failure signals:
- JSON includes `"success": false`
- text includes `"Error (Exit Code"`
3. Do not re-run a command simply because the output was truncated.
4. If a container fails to start, use the returned error. If more context is needed,
do not re-run the same container command; inspect the environment with focused tools.

OPERATIONAL RULES:
- Use as few tool calls as possible to complete the task.
- If a task requires enumerating resources first (e.g. "stop all containers"),
  list once then act; do NOT list again after.
- Never re-inspect or re-list after a successful operation just to verify success.
- Do not retry a failed call with identical arguments.
- If a response includes "_truncated_items" or "_truncated_keys", treat collections as
  partial summaries and continue with focused follow-up only when required.
- "Ensure accessible" means: container is running with the correct port mapping.
  Do not spawn curl/wget containers or check HTTP connectivity.
- Keep compose/build file paths within the workspace root.
- In the final answer, explicitly note when conclusions are based on truncated output.
"""


class DockerAgent:
    def __init__(
        self,
        model: str | BaseChatModel | None = None,
        temperature: float = 0.0,
        instructions: str | None = None,
        tools: list[Any] | None = None,
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

        self._tools = list(tools) if tools is not None else list(ALL_DOCKER_TOOLS)
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

        self._agent = self._build_agent()

    def _build_agent(self) -> Any:
        backend = FilesystemBackend(root_dir=str(self._workspace_dir))
        checkpointer = MemorySaver()

        return create_deep_agent(
            model=self._model,
            tools=self._tools,
            system_prompt=self._instructions,
            skills=[str(self._skills_dir)] if self._skills_dir else None,
            backend=backend,
            checkpointer=checkpointer,
        )

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
        result = self._agent.invoke(
            {"messages": [{"role": "user", "content": message}]},
            config=self._make_config(thread_id),
        )
        return self._extract_text(result)

    async def ainvoke(self, message: str, thread_id: str | None = None) -> str:
        result = await self._agent.ainvoke(
            {"messages": [{"role": "user", "content": message}]},
            config=self._make_config(thread_id),
        )
        return self._extract_text(result)

    def stream(self, message: str, thread_id: str | None = None):
        for event in self._agent.stream(
            {"messages": [{"role": "user", "content": message}]},
            config=self._make_config(thread_id),
        ):
            yield event

    @property
    def agent(self) -> Any:
        return self._agent

    @property
    def tools(self) -> list[Any]:
        return self._tools

    @property
    def workspace_dir(self) -> Path:
        return self._workspace_dir


def create_docker_agent(
    model: str | BaseChatModel | None = None,
    temperature: float = 0.0,
    instructions: str | None = None,
    tools: list[Any] | None = None,
    skills_dir: str | Path | None = None,
    workspace_dir: str | Path | None = None,
    app_title: str = "MultiAgentDocker",
) -> DockerAgent:
    return DockerAgent(
        model=model,
        temperature=temperature,
        instructions=instructions,
        tools=tools,
        skills_dir=skills_dir,
        workspace_dir=workspace_dir,
        app_title=app_title,
    )
