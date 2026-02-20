# Existing Code Analysis

## Files to Modify

| File | Purpose | Change |
|------|---------|--------|
| `src/multi_agent/agents/docker_agent.py` | Main agent class | Add subagents config |
| `src/multi_agent/tools/__init__.py` | Tool exports | Already has groups |
| `src/skills/docker-management/SKILL.md` | Routing skill | Simplify to routing only |

## Current Architecture

```
DockerAgent
├── _tools: ALL_DOCKER_TOOLS (37 tools, 4924 tokens)
├── _instructions: System prompt
├── _skill_files: SKILL.md content
└── _agent: create_deep_agent(tools=ALL_DOCKER_TOOLS)
```

## Target Architecture

```
DockerAgent
├── _tools: [] (empty - no direct tools)
├── _instructions: Routing-focused prompt
├── _skill_files: Minimal routing skill
├── _subagents: [
│   container-agent (CONTAINER_TOOLS)
│   image-agent (IMAGE_TOOLS)
│   network-agent (NETWORK_TOOLS)
│   volume-agent (VOLUME_TOOLS)
│   compose-agent (COMPOSE_TOOLS)
│   system-agent (SYSTEM_TOOLS)
│ ]
└── _agent: create_deep_agent(tools=[], subagents=_subagents)
```

## Existing Patterns

### From Froq sample (`sample-srcs/Froq/src/froq/agents/docker_agent.py`)

```python
# Already supports subagents parameter
def __init__(
    self,
    ...
    subagents: list[dict] | None = None,  # ← Already exists!
    ...
):
    self._subagents = subagents or []
```

### DeepAgents SubAgent Schema

```python
class SubAgent(TypedDict):
    name: str
    description: str
    system_prompt: str
    tools: Sequence[BaseTool | Callable | dict[str, Any]]
    model: NotRequired[str | BaseChatModel]
    middleware: NotRequired[list[AgentMiddleware]]
```

## Dependencies

- `deepagents` - already installed
- `langchain_core.tools` - already used
- Tool groups already defined in `tools/__init__.py`:
  - CONTAINER_TOOLS, IMAGE_TOOLS, NETWORK_TOOLS, VOLUME_TOOLS, SYSTEM_TOOLS, COMPOSE_TOOLS

## No Breaking Changes

- `DockerAgent.invoke()` signature unchanged
- `create_docker_agent()` still works
- CLI (`multi-agent-cli`) unchanged
