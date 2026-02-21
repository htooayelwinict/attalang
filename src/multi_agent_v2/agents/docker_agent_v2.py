import asyncio
import importlib
import inspect
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.multi_agent_v2.tools import ALL_DOCKER_TOOLS, create_docker_toolset

DEFAULT_WORKSPACE = "/tmp/multi-agent-docker-v2-workspace"
DEFAULT_SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills" / "docker-management-v2"
_DEFAULT_THREAD_KEY = "__default__"

DOCKER_AGENT_V2_INSTRUCTIONS = """You are a Docker operations agent with planning capabilities.

## PLANNING
For multi-step tasks, use docker_create_plan first:
- Input: JSON array of steps
- Example: docker_create_plan('["Create network", "Run container", "Verify"]')
- This creates a visible plan before execution

## MANDATORY PRE-CHECK
Before creating resources, check if they exist:
- Container: docker_list_containers
- Network: docker_list_networks
- Volume: docker_list_volumes

## EXECUTION
1. Success = JSON has "success": true
2. After success: STOP
3. Maximum 15 tool calls

## FORBIDDEN
- Spawning curl/wget containers
- Re-listing after success
"""


_INSTALL_HINT = 'DockerAgentV2 requires optional dependencies. Install with: pip install -e ".[agentv2,dev]"'


def _create_openrouter_model() -> Any:
    """Create OpenAIChatModel configured for OpenRouter."""
    try:
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider
    except ImportError as exc:
        raise RuntimeError(_INSTALL_HINT) from exc

    api_key = os.getenv("OPENROUTER_API_KEY")
    model_name = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set in environment")

    provider = OpenAIProvider(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
    return OpenAIChatModel(model_name, provider=provider)


def _resolve_v1_model(model: Any) -> Any:
    if model is not None:
        return model
    return _create_openrouter_model()


load_dotenv()


def _filter_supported_kwargs(fn: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    signature = inspect.signature(fn)
    parameters = signature.parameters
    has_var_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in parameters.values())
    if has_var_kwargs:
        return kwargs
    return {key: value for key, value in kwargs.items() if key in parameters}


def _call_with_supported_kwargs(fn: Any, kwargs: dict[str, Any]) -> Any:
    filtered = _filter_supported_kwargs(fn, kwargs)
    return fn(**filtered)


def _load_pydantic_modules() -> dict[str, Any]:
    try:
        deep_module = importlib.import_module("pydantic_deep")
    except ImportError as exc:
        raise RuntimeError(_INSTALL_HINT) from exc

    try:
        backend_module = importlib.import_module("pydantic_ai_backends")
    except ImportError as exc:
        raise RuntimeError(_INSTALL_HINT) from exc

    create_deep_agent = getattr(deep_module, "create_deep_agent", None)
    if create_deep_agent is None:
        raise RuntimeError("pydantic_deep.create_deep_agent is unavailable.")

    filesystem_backend = getattr(backend_module, "LocalBackend", None)
    if filesystem_backend is None:
        raise RuntimeError("pydantic_ai_backends.LocalBackend is unavailable.")

    return {
        "create_deep_agent": create_deep_agent,
        "create_default_deps": getattr(deep_module, "create_default_deps", None),
        "DeepAgentDeps": getattr(deep_module, "DeepAgentDeps", None),
        "FilesystemBackend": filesystem_backend,
    }


class DockerAgentV2:
    def __init__(
        self,
        model: Any = None,
        temperature: float = 0.0,
        instructions: str | None = None,
        tools: list[Any] | None = None,
        skills_dir: str | Path | None = None,
        workspace_dir: str | Path | None = None,
    ):
        self._model = _resolve_v1_model(model)
        self._temperature = temperature
        self._tools = list(tools) if tools is not None else list(ALL_DOCKER_TOOLS)
        self._instructions = instructions or DOCKER_AGENT_V2_INSTRUCTIONS

        self._workspace_dir = (
            Path(workspace_dir)
            if workspace_dir
            else Path(os.getenv("MULTI_AGENT_DOCKER_V2_WORKSPACE", DEFAULT_WORKSPACE))
        ).expanduser()
        self._workspace_dir.mkdir(parents=True, exist_ok=True)

        if skills_dir is None:
            self._skills_dir = DEFAULT_SKILLS_DIR if DEFAULT_SKILLS_DIR.exists() else None
        else:
            parsed = Path(skills_dir).expanduser()
            self._skills_dir = parsed if parsed.exists() else None

        self._agent: Any | None = None
        self._deps_by_thread: dict[str, Any] = {}
        self._modules: dict[str, Any] | None = None
        self._registered_tools: list[str] = []

    def _get_modules(self) -> dict[str, Any]:
        if self._modules is None:
            self._modules = _load_pydantic_modules()
        return self._modules

    def _build_agent(self) -> Any:
        modules = self._get_modules()
        create_deep_agent = modules["create_deep_agent"]

        skill_directories: list[dict[str, Any]] | None = None
        if self._skills_dir is not None:
            skill_directories = [{"path": str(self._skills_dir), "recursive": False}]

        agent_kwargs: dict[str, Any] = {
            "model": self._model,
            "instructions": self._instructions,
            "toolsets": [create_docker_toolset()],
            "include_todo": False,  # Using custom docker_create_plan instead
            "include_filesystem": False,
            "include_subagents": False,
            "include_skills": bool(skill_directories),
            "skill_directories": skill_directories,
        }

        agent = _call_with_supported_kwargs(create_deep_agent, agent_kwargs)
        self._registered_tools = [getattr(t, "__name__", str(t)) for t in self._tools]
        return agent

    def _get_agent(self) -> Any:
        if self._agent is None:
            self._agent = self._build_agent()
        return self._agent

    def _build_deps(self) -> Any:
        modules = self._get_modules()
        filesystem_backend = modules["FilesystemBackend"]
        backend = _call_with_supported_kwargs(
            filesystem_backend,
            {
                "root_dir": str(self._workspace_dir),
                "allowed_directories": [str(self._workspace_dir)],
            },
        )

        create_default_deps = modules.get("create_default_deps")
        if callable(create_default_deps):
            return _call_with_supported_kwargs(create_default_deps, {"backend": backend})

        deep_agent_deps = modules.get("DeepAgentDeps")
        if deep_agent_deps is not None:
            return _call_with_supported_kwargs(deep_agent_deps, {"backend": backend})

        return {"backend": backend}

    def _deps_for_thread(self, thread_id: str | None) -> Any:
        key = thread_id or _DEFAULT_THREAD_KEY
        deps = self._deps_by_thread.get(key)
        if deps is None:
            deps = self._build_deps()
            self._deps_by_thread[key] = deps
        return deps

    @staticmethod
    def _extract_output(result: Any) -> str:
        if result is None:
            return ""

        output = getattr(result, "output", None)
        if output is not None:
            return str(output)

        if isinstance(result, str):
            return result

        if isinstance(result, dict):
            for key in ("output", "content", "text", "message"):
                value = result.get(key)
                if value is not None:
                    return str(value)

        return str(result)

    async def ainvoke(self, message: str, thread_id: str | None = None) -> str:
        agent = self._get_agent()
        deps = self._deps_for_thread(thread_id)

        run = getattr(agent, "run", None)
        if run is None:
            raise RuntimeError("Pydantic agent instance does not expose run().")

        try:
            result_or_awaitable = run(message, deps=deps)
        except TypeError:
            result_or_awaitable = run(message)

        if inspect.isawaitable(result_or_awaitable):
            result = await result_or_awaitable
        else:
            result = result_or_awaitable

        return self._extract_output(result)

    def invoke(self, message: str, thread_id: str | None = None) -> str:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.ainvoke(message, thread_id=thread_id))
        raise RuntimeError(
            "DockerAgentV2.invoke() cannot run inside an active event loop. "
            "Use await DockerAgentV2.ainvoke()."
        )

    @staticmethod
    def _extract_stream_event(event: Any) -> str:
        if isinstance(event, str):
            return event

        for attr in ("text", "content", "output"):
            value = getattr(event, attr, None)
            if value is not None:
                return str(value)

        if isinstance(event, dict):
            for key in ("text", "content", "output"):
                value = event.get(key)
                if value is not None:
                    return str(value)

        return str(event)

    def stream(self, message: str, thread_id: str | None = None):
        """Stream agent execution with verbose output."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(
                "DockerAgentV2.stream() cannot run inside an active event loop. "
                "Use await DockerAgentV2.ainvoke()."
            )

        agent = self._get_agent()
        deps = self._deps_for_thread(thread_id)

        # Use iter() for streaming with node-level access
        iter_method = getattr(agent, "iter", None)

        if callable(iter_method):
            async def _collect_events() -> list[str]:
                events: list[str] = []
                try:
                    async with iter_method(message, deps=deps) as run:
                        async for node in run:
                            # Check for tool calls
                            node_type = type(node).__name__

                            if node_type == "CallToolsNode":
                                model_resp = getattr(node, "model_response", None)
                                if model_resp:
                                    parts = getattr(model_resp, "parts", [])
                                    for part in parts:
                                        if hasattr(part, "tool_name"):
                                            tool_name = part.tool_name
                                            args = getattr(part, "args", {})
                                            events.append(f"[Tool] {tool_name}({args})")

                            elif node_type == "ModelRequestNode":
                                events.append("[Model] Calling LLM...")

                            elif node_type == "UserPromptNode":
                                events.append("[User] Processing prompt...")

                            elif node_type == "End":
                                events.append("[Done] Execution complete")

                        # Get final result
                        result = run.result
                        if hasattr(result, "output"):
                            events.append(f"\n{result.output}")

                except TypeError:
                    # Fallback if iter() doesn't support context manager
                    result = await agent.run(message, deps=deps)
                    events.append(self._extract_output(result))

                return events

            for event in asyncio.run(_collect_events()):
                yield event
            return

        # Fallback to invoke if no streaming available
        yield self.invoke(message, thread_id=thread_id)

    @property
    def agent(self) -> Any:
        return self._agent

    @property
    def tools(self) -> list[Any]:
        return self._tools

    @property
    def workspace_dir(self) -> Path:
        return self._workspace_dir

    def get_todos(self, thread_id: str | None = None) -> list[Any]:
        """Get the todo list from the deps."""
        deps = self._deps_by_thread.get(thread_id or _DEFAULT_THREAD_KEY)
        if deps is None:
            return []
        return getattr(deps, "todos", [])

    @property
    def registered_tools(self) -> list[str]:
        return list(self._registered_tools)

    @property
    def deps_by_thread(self) -> dict[str, Any]:
        return self._deps_by_thread


def create_docker_agent_v2(
    model: Any = None,
    temperature: float = 0.0,
    instructions: str | None = None,
    tools: list[Any] | None = None,
    skills_dir: str | Path | None = None,
    workspace_dir: str | Path | None = None,
) -> DockerAgentV2:
    return DockerAgentV2(
        model=model,
        temperature=temperature,
        instructions=instructions,
        tools=tools,
        skills_dir=skills_dir,
        workspace_dir=workspace_dir,
    )
