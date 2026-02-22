import os
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from src.multi_agent.tools import ALL_DOCKER_TOOLS
from src.multi_agent.utils import create_openrouter_llm

DEFAULT_WORKSPACE = "/tmp/multi-agent-docker-workspace"
DEFAULT_SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"

# Tools requiring human approval before execution
DANGEROUS_TOOLS: tuple[str, ...] = (
    "remove_image",
    "prune_images",
)

# Tools that are auto-rejected without user prompt
AUTO_REJECT_TOOLS: tuple[str, ...] = (
    "remove_volume",
    "prune_volumes",
    "docker_system_prune",
)

DOCKER_AGENT_INSTRUCTIONS = """You are a Docker operations agent. Execute tasks efficiently with minimal tool calls.

## MANDATORY PRE-CHECK RULE
Before creating ANY resource (container, network, volume), you MUST check if it already exists:
- Creating container: docker_bash command 'ps -a' first to check name/port conflicts
- Creating network: docker_bash command 'network ls' first to check name conflicts
- Creating volume: docker_bash command 'volume ls' first to check name conflicts

If resource exists and is suitable, USE IT. If conflict (e.g., port taken), report it.

## TOOL PREFERENCES
- Use docker_bash for all safe read/start/stop/restart/inspect/log/stat/version/info operations.
- Use SDK tools only when operation needs structured options:
  run_container, pull_image, build_image, tag_image,
  create_network, create_volume, connect_to_network, disconnect_from_network,
  exec_in_container, compose_up, compose_down.
- Dangerous SDK tools (remove/prune) are controlled by HITL rules.

## EXECUTION RULES
1. Success: Output doesn't start with "Error:" (docker_bash returns raw stdout, SDK tools return JSON with "success": true)
2. Truncated output ("[TRUNCATED]") is normal, not a failure
3. After success: STOP. Do not re-verify or re-list.
4. After failure: Read error, fix root cause. Do not retry identical args.
5. Maximum 15 tool calls per task. Plan before acting.

## CONFLICT HANDLING
- Port in use: Report which container uses it, suggest alternative or ask user
- Name exists: Either use existing or suggest new name
- Network exists: Connect to existing network
- Volume exists: Mount existing volume

## FORBIDDEN ACTIONS
- Spawning curl/wget containers for HTTP checks
- Re-listing resources after successful operations
- Creating resources without checking existence first
- More than 2 retries on same operation

## WORKFLOW
1. ASSESS: List relevant resources to understand current state
2. PLAN: Identify what needs creation vs what exists
3. EXECUTE: Create only what's missing
4. REPORT: Summary of what was done and access info
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
        enable_hitl: bool = False,
        dangerous_tools: tuple[str, ...] | None = None,
        auto_reject_tools: tuple[str, ...] | None = None,
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
        self._enable_hitl = enable_hitl
        self._dangerous_tools = dangerous_tools if dangerous_tools is not None else DANGEROUS_TOOLS
        self._auto_reject_tools = (
            auto_reject_tools if auto_reject_tools is not None else AUTO_REJECT_TOOLS
        )

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
        backend = FilesystemBackend(root_dir=str(self._workspace_dir), virtual_mode=True)
        checkpointer = MemorySaver()

        # Configure interrupt for dangerous tools if HITL enabled
        interrupt_on: dict[str, dict[str, list[str]]] | None = None
        if self._enable_hitl:
            interrupt_on = {}
            # Approval-required tools
            for tool in self._dangerous_tools:
                interrupt_on[tool] = {"allowed_decisions": ["approve", "reject"]}
            # Auto-reject tools (only reject allowed)
            for tool in self._auto_reject_tools:
                interrupt_on[tool] = {"allowed_decisions": ["reject"]}

        return create_deep_agent(
            model=self._model,
            tools=self._tools,
            system_prompt=self._instructions,
            skills=[str(self._skills_dir)] if self._skills_dir else None,
            backend=backend,
            checkpointer=checkpointer,
            interrupt_on=interrupt_on or None,  # type: ignore[arg-type]
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

    def _make_config(self, thread_id: str | None, recursion_limit: int = 200) -> dict[str, Any]:
        config: dict[str, Any] = {"recursion_limit": recursion_limit}
        if thread_id:
            config["configurable"] = {"thread_id": thread_id}
        return config

    def invoke(self, message: str, thread_id: str | None = None) -> str:
        config = self._make_config(thread_id)
        result = self._agent.invoke(
            {"messages": [{"role": "user", "content": message}]},
            config=config,
        )

        # Handle HITL interrupts
        while result.get("__interrupt__"):
            if not self._enable_hitl:
                break

            decisions = []
            for interrupt in result["__interrupt__"]:
                interrupt_value = getattr(interrupt, "value", interrupt)

                # Structure: {"action_requests": [...], "review_configs": [...]}
                action_requests = (
                    interrupt_value.get("action_requests", [])
                    if isinstance(interrupt_value, dict)
                    else []
                )

                for action in action_requests:
                    tool_name = (
                        action.get("name", "unknown") if isinstance(action, dict) else "unknown"
                    )
                    tool_args = action.get("args", {}) if isinstance(action, dict) else {}

                    # Auto-reject tools - no user prompt
                    if tool_name in self._auto_reject_tools:
                        print(f"\n🚫 BLOCKED: {tool_name} - {tool_args}")
                        decisions.append(
                            {
                                "type": "reject",
                                "message": f"Operation {tool_name} is not allowed by system administrator! STOP immediately and do not retry.",
                            }
                        )
                    else:
                        # Prompt user for approval
                        print(f"\n⚠️  DANGEROUS OPERATION: {tool_name}")
                        print(f"   Arguments: {tool_args}")
                        response = input("Approve? [y/n]: ").strip().lower()
                        decisions.append(
                            {
                                "type": "approve" if response in ("y", "yes") else "reject",
                            }
                        )

            result = self._agent.invoke(
                Command(resume={"decisions": decisions}),
                config=config,
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
    def enable_hitl(self) -> bool:
        return self._enable_hitl

    @property
    def dangerous_tools(self) -> tuple[str, ...]:
        return self._dangerous_tools

    @property
    def auto_reject_tools(self) -> tuple[str, ...]:
        return self._auto_reject_tools

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
    enable_hitl: bool = False,
    dangerous_tools: tuple[str, ...] | None = None,
    auto_reject_tools: tuple[str, ...] | None = None,
) -> DockerAgent:
    return DockerAgent(
        model=model,
        temperature=temperature,
        instructions=instructions,
        tools=tools,
        skills_dir=skills_dir,
        workspace_dir=workspace_dir,
        app_title=app_title,
        enable_hitl=enable_hitl,
        dangerous_tools=dangerous_tools,
        auto_reject_tools=auto_reject_tools,
    )
