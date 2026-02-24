"""Programmatic Docker Agent — writes Python code that calls Docker tools directly.

Instead of N LLM round-trips for N tools, the LLM writes a single Python script
that calls docker_cli() as a function. The CodeExecutor runs it and returns
all captured output in one shot.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain.tools import tool
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field

from src.multi_agent.tools.docker_tools import docker_cli as _v1_docker_cli
from src.multi_agent.utils.llm import create_openrouter_llm
from src.multi_agent_v3.tools.bridge import ProgrammaticToolBridge
from src.multi_agent_v3.tools.executor import CodeExecutor

DEFAULT_WORKSPACE = "/tmp/multi-agent-docker-workspace"
DEFAULT_SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"

# Only expose safe tools programmatically — HITL tools are excluded
PROGRAMMATIC_TOOLS = [_v1_docker_cli]


def _build_bridge() -> ProgrammaticToolBridge:
    bridge = ProgrammaticToolBridge()
    bridge.register_many(PROGRAMMATIC_TOOLS)
    return bridge


# Module-level bridge + executor (shared across invocations)
_BRIDGE = _build_bridge()
_EXECUTOR = CodeExecutor(
    tool_namespace=_BRIDGE.make_namespace(),
    timeout_seconds=int(os.getenv("PROGRAMMATIC_TIMEOUT_SECONDS", "120")),
    max_output_chars=int(os.getenv("PROGRAMMATIC_MAX_OUTPUT_CHARS", "8000")),
)

# Generate API reference once
_API_REFERENCE = _BRIDGE.get_api_reference()


class ExecuteDockerCodeInput(BaseModel):
    code: str = Field(
        description=(
            "Python code that calls Docker tool functions directly. "
            "Use print() to output results. Available functions are listed in your instructions."
        )
    )
    explanation: str = Field(
        description="Brief explanation of what this code does (for audit trail)"
    )


@tool(args_schema=ExecuteDockerCodeInput)
def execute_docker_code(code: str, explanation: str = "") -> str:
    """Execute Python code that calls Docker tool functions directly.

    Write Python code using the available Docker functions. All functions accept keyword arguments
    and return strings. Use print() to output results you want to see.

    IMPORTANT:
    - Call functions with KEYWORD arguments: docker_cli(command="ps", args="-a")
    - Use print() to see results
    - You can use loops, conditionals, variables, string formatting
    - json, re, time modules are available via import
    - No file I/O, no network, no subprocess — only the provided functions
    """
    return _EXECUTOR.execute(code)


PROGRAMMATIC_AGENT_INSTRUCTIONS = f"""You are a Docker operations agent with PROGRAMMATIC tool calling.

Instead of calling tools one at a time, you write Python code that calls Docker functions directly.
This is faster, uses fewer tokens, and allows loops/conditionals.

## AVAILABLE FUNCTIONS

{_API_REFERENCE}

## HOW TO CALL

Use the execute_docker_code tool with Python code. Call functions with KEYWORD arguments:

```python
# Single operation
result = docker_cli(command="ps", args="-a")
print(result)

# Multiple operations in one call
docker_cli(command="network create", args="my-network --subnet 172.28.0.0/16")
docker_cli(command="volume create", args="my-volume")

# Loops
for img in ["redis:7-alpine", "nginx:alpine", "postgres:15-alpine"]:
    result = docker_cli(command="pull", args=img)
    print(f"Pulled {{img}}: {{result[:80]}}")

# Conditionals
result = docker_cli(command="ps", args="-a --filter name=my-app --format '{{{{.Names}}}}'")
if "my-app" not in result:
    docker_cli(command="run", args="-d --name my-app nginx:alpine")
    print("Created my-app")
else:
    print("my-app already exists")
```

## RULES

1. ALWAYS use keyword arguments: docker_cli(command="ps", args="-a")
2. Use print() to show results — only printed output is returned to you
3. Available imports: json, re, time, textwrap, itertools, functools, collections
4. NO file I/O, NO subprocess, NO network calls — only the provided functions
5. Check resource existence before creating (use docker_cli to list first)
6. Group related operations into a single execute_docker_code call
7. For multi-phase tasks: use one execute_docker_code per phase, print status
8. Maximum 5 execute_docker_code calls per task (plan your code efficiently)

## CRITICAL: SHELL OPERATORS ARE BLOCKED IN docker_cli args
docker_cli REJECTS any args containing these characters: ; | && || ` $( 
This means you CANNOT use:
- Shell arithmetic: `$((1+2))` — blocked because of `$(`
- Command substitution: `$(cmd)` or `` `cmd` `` — blocked
- Pipe: `cmd | grep` — blocked
- Chaining: `cmd1 && cmd2` or `cmd1; cmd2` — blocked

### CORRECT ALTERNATIVES:
- For **arithmetic/computation**: do it in Python directly with print(), NOT in a container
- For **exec with shell**: split into separate docker_cli calls, one per command
- For **filtering output**: get raw output, filter in Python

```python
# ❌ WRONG — will fail with "Shell control operators are not allowed"
docker_cli(command="run", args="--rm alpine sh -c 'echo $((23497+233249))'")
docker_cli(command="exec", args="box sh -c 'apt update && apt install curl'")

# ✅ RIGHT — compute in Python
result = 23497 + 233249
print(f"Result: {{result}}")

# ✅ RIGHT — split exec calls
docker_cli(command="exec", args="box apt-get update")
docker_cli(command="exec", args="box apt-get install -y curl")
```

## ANTI-LOOP RULE (CRITICAL)
If you get the SAME error twice in a row:
1. STOP calling execute_docker_code
2. Explain the error to the user
3. Suggest an alternative approach
NEVER retry the same code or approach more than once after an error.

## MANDATORY PRE-CHECK
Before creating ANY resource, check if it exists first in the same code block:
```python
import json
existing = docker_cli(command="ps", args="-a --format '{{{{json .}}}}'")
# parse and check before creating
```

## DESTRUCTIVE OPERATIONS
You CANNOT remove containers, images, networks, or volumes programmatically.
If the user asks for cleanup/removal, explain that those require HITL approval
and cannot be done in programmatic mode. Suggest using the standard agent instead.

## WORKFLOW
1. Assess current state (one code block to list resources)
2. Execute operations (one code block per phase for complex tasks)
3. Verify + report (one final code block)
"""


class ProgrammaticDockerAgent:
    """Docker agent that uses programmatic tool calling (code execution)."""

    def __init__(
        self,
        model: str | BaseChatModel | None = None,
        temperature: float = 0.0,
        instructions: str | None = None,
        skills_dir: str | Path | None = None,
        workspace_dir: str | Path | None = None,
        app_title: str = "MultiAgentDockerProg",
        provider_sort: str | None = None,
    ):
        if isinstance(model, BaseChatModel):
            self._model = model
        else:
            self._model = create_openrouter_llm(
                model=model,
                temperature=temperature,
                app_title=app_title,
                provider_sort=provider_sort,
            )

        self._instructions = instructions or PROGRAMMATIC_AGENT_INSTRUCTIONS
        self._tools = [execute_docker_code]

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
                elif isinstance(item, dict):
                    text_value = item.get("text") or item.get("content")
                    if text_value:
                        parts.append(str(text_value))
                else:
                    parts.append(str(item))
            return "\n".join(parts).strip()

        if content is not None:
            return str(content)

        return str(last)

    def _make_config(self, thread_id: str | None, recursion_limit: int = 200) -> dict[str, Any]:
        """Config with lower recursion limit — programmatic calls need fewer rounds."""
        config: dict[str, Any] = {"recursion_limit": recursion_limit}
        if thread_id:
            config["configurable"] = {"thread_id": thread_id}
        return config

    def invoke(
        self,
        message: str,
        thread_id: str | None = None,
        callbacks: list[Any] | None = None,
    ) -> str:
        config = self._make_config(thread_id)
        if callbacks:
            config["callbacks"] = callbacks
        result = self._agent.invoke(
            {"messages": [{"role": "user", "content": message}]},
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
    def agent(self) -> Any:
        return self._agent

    @property
    def tools(self) -> list[Any]:
        return self._tools

    @property
    def workspace_dir(self) -> Path:
        return self._workspace_dir


def create_programmatic_docker_agent(
    model: str | BaseChatModel | None = None,
    temperature: float = 0.0,
    instructions: str | None = None,
    skills_dir: str | Path | None = None,
    workspace_dir: str | Path | None = None,
    app_title: str = "MultiAgentDockerProg",
    provider_sort: str | None = None,
) -> ProgrammaticDockerAgent:
    return ProgrammaticDockerAgent(
        model=model,
        temperature=temperature,
        instructions=instructions,
        skills_dir=skills_dir,
        workspace_dir=workspace_dir,
        app_title=app_title,
        provider_sort=provider_sort,
    )
