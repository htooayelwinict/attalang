# Phase 2: Update DockerAgent

## Objective
Replace ALL_DOCKER_TOOLS with subagents architecture.

## Prerequisites
- Phase 1 completed (subagents defined)

## Tasks

### 2.1 Update imports
- [ ] Import tool groups at module level

```python
from src.multi_agent.tools import (
    CONTAINER_TOOLS, IMAGE_TOOLS, NETWORK_TOOLS,
    VOLUME_TOOLS, SYSTEM_TOOLS, COMPOSE_TOOLS,
)
```

### 2.2 Modify __init__
- [ ] Add subagents parameter handling
- [ ] Call _build_subagents() when no tools specified

```python
def __init__(
    self,
    model: str | BaseChatModel | None = None,
    temperature: float = 0.0,
    instructions: str | None = None,
    tools: list[Any] | None = None,
    subagents: list[dict[str, Any]] | None = None,  # New param
    skills_dir: str | Path | None = None,
    workspace_dir: str | Path | None = None,
    app_title: str = "MultiAgentDocker",
):
    # ... existing LLM setup ...

    # If custom tools provided, use them (backward compat)
    # Otherwise use subagents architecture
    if tools is not None:
        self._tools = list(tools)
        self._subagents = subagents or []
    else:
        self._tools = []  # No direct tools in main agent
        self._subagents = subagents if subagents is not None else self._build_subagents()
```

### 2.3 Update _build_agent()
- [ ] Pass subagents to create_deep_agent
- [ ] Remove tools from main agent

```python
def _build_agent(self) -> Any:
    backend = FilesystemBackend(root_dir=str(self._workspace_dir), virtual_mode=True)
    checkpointer = MemorySaver()

    return create_deep_agent(
        model=self._model,
        tools=self._tools,  # Empty list for subagent mode
        subagents=self._subagents,  # Pass subagents
        system_prompt=self._instructions,
        backend=backend,
        skills=[SKILLS_VIRTUAL_ROOT] if self._skill_files else None,
        checkpointer=checkpointer,
    )
```

### 2.4 Update system prompt
- [ ] Change to routing-focused instructions

```python
DOCKER_AGENT_INSTRUCTIONS = """You are a Docker operations coordinator. You route Docker tasks to specialized subagents.

## Available Subagents

| Subagent | Use For |
|----------|---------|
| container-agent | Containers (run, stop, logs, etc.) |
| image-agent | Images (pull, build, tag, etc.) |
| network-agent | Networks |
| volume-agent | Volumes |
| compose-agent | Docker Compose |
| system-agent | System info, prune, version |

## Workflow

1. Analyze the user's request
2. Identify which subagent(s) can handle the task
3. Use the `task` tool to delegate to the appropriate subagent
4. Synthesize results and report to user

For multi-step operations, delegate to multiple subagents in sequence.
"""
```

## Files
| File | Action |
|------|--------|
| `src/multi_agent/agents/docker_agent.py` | Modify __init__, _build_agent, instructions |

## Verification
```bash
source .venv/bin/activate && python3 -c "
from src.multi_agent.agents import DockerAgent
agent = DockerAgent()
print(f'Tools: {len(agent._tools)}')
print(f'Subagents: {len(agent._subagents)}')
for s in agent._subagents:
    print(f'  - {s[\"name\"]}')
"
```

Expected output:
```
Tools: 0
Subagents: 6
  - container-agent
  - image-agent
  - network-agent
  - volume-agent
  - compose-agent
  - system-agent
```

## Estimate
1 hour (XS)
