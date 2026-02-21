# Plan: Docker Agent V2 (Pydantic-DeepAgents)

**Created:** 2026-02-21
**Status:** Planning
**Branch:** pydantic

---

## Summary

Migrate Docker management agent from LangChain-based `deepagents` to Pydantic-based `pydantic-deep` for improved type safety, async-first design, and built-in sandboxing.

---

## Goals

- [ ] Create parallel `docker-agentv2` using `pydantic-deep` package
- [ ] Achieve type-safe agent with Pydantic models
- [ ] Enable `virtual_mode=True` for secure filesystem sandboxing
- [ ] Maintain feature parity with existing Docker agent
- [ ] Async-first design throughout

---

## Architecture Comparison

| Aspect | Current (LangChain) | Target (Pydantic) |
|--------|---------------------|-------------------|
| Package | `deepagents` | `pydantic-deep` |
| Base | LangGraph + LangChain | pydantic-ai |
| Type Safety | Manual | Native Pydantic |
| Async | Mixed | Async-first |
| Sandbox | Manual config | `virtual_mode=True` |
| State | MemorySaver | StateBackend |
| Invoke | `agent.invoke()` | `await agent.run()` |

---

## Files to Create/Modify

### New Files (docker-agentv2/)
```
src/multi_agent/
├── agents_v2/
│   ├── __init__.py
│   └── docker_agent_v2.py      # Pydantic-based agent
├── tools_v2/
│   ├── __init__.py
│   └── docker_tools_v2.py      # Pydantic-compatible tools
└── runtime_v2/
    ├── __init__.py
    ├── cli_v2.py               # New CLI entrypoint
    └── runtime_v2.py           # Pydantic runtime
```

### Modified Files
- `pyproject.toml` — Add `pydantic-deep`, `pydantic-ai-backend` deps
- `src/skills/docker-management/SKILL.md` — Minor updates for v2

---

## Phases Overview

| Phase | Description | Key Deliverables |
|-------|-------------|------------------|
| 1 | Setup & Infrastructure | Package install, folder structure, basic agent |
| 2 | Tool Migration | Convert Docker tools to pydantic-ai format |
| 3 | Agent Implementation | DockerAgentV2 class with async patterns |
| 4 | Runtime & CLI | New runtime and CLI entrypoint |
| 5 | Testing & Validation | Tests, comparison with v1 |

---

## Phase 1: Setup & Infrastructure

### Objective
Establish project foundation with pydantic-deep dependencies and folder structure.

### Tasks
- [ ] Add dependencies to `pyproject.toml`
  ```toml
  dependencies = [
    # ... existing ...
    "pydantic-deep>=0.1.0",
    "pydantic-ai-backend>=0.1.0",
  ]
  ```
- [ ] Create folder structure
  ```bash
  mkdir -p src/multi_agent/agents_v2
  mkdir -p src/multi_agent/tools_v2
  mkdir -p src/multi_agent/runtime_v2
  ```
- [ ] Create basic `docker_agent_v2.py` with `create_deep_agent`
- [ ] Verify import works: `from pydantic_deep import create_deep_agent`

### Verification
```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -c "from pydantic_deep import create_deep_agent; print('OK')"
```

---

## Phase 2: Tool Migration

### Objective
Convert existing Docker tools to pydantic-ai compatible format.

### Key Changes
| LangChain Tool | Pydantic-AI Tool |
|----------------|------------------|
| `@tool` decorator | `@agent.tool` or function |
| `BaseModel` args | Pydantic models (same) |
| Returns `str` | Returns typed output |

### Tasks
- [ ] Create `docker_tools_v2.py`
- [ ] Migrate container tools (list, run, stop, etc.)
- [ ] Migrate image tools (list, pull, build, etc.)
- [ ] Migrate network tools
- [ ] Migrate volume tools
- [ ] Migrate compose tools
- [ ] Migrate system tools

### Pattern
```python
# OLD (LangChain)
from langchain.tools import tool

@tool
def list_containers(all_containers: bool = False) -> str:
    """List containers."""
    ...

# NEW (Pydantic-AI)
from pydantic_ai import Agent

@agent.tool
def list_containers(ctx, all_containers: bool = False) -> str:
    """List containers."""
    ...
```

---

## Phase 3: Agent Implementation

### Objective
Implement DockerAgentV2 class with pydantic-deep patterns.

### Tasks
- [ ] Create `DockerAgentV2` class
- [ ] Configure with `create_deep_agent()`
- [ ] Use `FilesystemBackend(virtual_mode=True)`
- [ ] Implement `invoke()` async method
- [ ] Implement `stream()` async method
- [ ] Add system prompt (reuse existing)

### Key Code
```python
from pydantic_deep import create_deep_agent, DeepAgentDeps
from pydantic_ai_backends import FilesystemBackend

class DockerAgentV2:
    def __init__(self, model: str = "openai:gpt-4.1", ...):
        self._agent = create_deep_agent(
            model=model,
            instructions=DOCKER_AGENT_INSTRUCTIONS,
            include_filesystem=True,
            include_todo=True,
            toolsets=[DockerToolset()],
        )

    async def invoke(self, message: str) -> str:
        deps = DeepAgentDeps(
            backend=FilesystemBackend(root_dir=str(self._workspace), virtual_mode=True)
        )
        result = await self._agent.run(message, deps=deps)
        return result.output
```

---

## Phase 4: Runtime & CLI

### Objective
Create new runtime and CLI for v2 agent.

### Tasks
- [ ] Create `runtime_v2.py` with `DockerGraphRuntimeV2`
- [ ] Create `cli_v2.py` with Click commands
- [ ] Add CLI script to `pyproject.toml`
  ```toml
  [project.scripts]
  docker-agent-v2 = "src.multi_agent.runtime_v2.cli_v2:main"
  ```
- [ ] Support same CLI options as v1

### CLI Pattern
```python
# cli_v2.py
import asyncio
import click

@click.command()
@click.option("--prompt", default=None)
def main(prompt: str | None):
    agent = DockerAgentV2()
    if prompt:
        result = asyncio.run(agent.invoke(prompt))
        click.echo(result)
```

---

## Phase 5: Testing & Validation

### Objective
Comprehensive testing and comparison with v1.

### Tasks
- [ ] Create `tests/test_docker_agent_v2.py`
- [ ] Test basic container operations
- [ ] Test conflict detection (same as v1)
- [ ] Test blue-green deployment scenario
- [ ] Compare performance v1 vs v2
- [ ] Document differences

### Test Scenarios
1. List containers → verify JSON output
2. Create network (conflict handling)
3. Run container with port conflict
4. Multi-tier deployment
5. Cleanup operations

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| pydantic-deep API changes | High | Pin version, monitor releases |
| Tool incompatibility | Medium | Phase 2 dedicated to migration |
| Async patterns unfamiliar | Low | Follow pydantic-ai docs |
| Feature parity gaps | Medium | Maintain v1 during transition |
| Performance regression | Low | Benchmark in Phase 5 |

---

## Rollback Strategy

- v1 agent remains unchanged in `agents/`
- v2 is parallel implementation in `agents_v2/`
- Can delete v2 folder if migration fails
- No shared state between v1 and v2

---

## Dependencies

```toml
[project]
dependencies = [
    # ... existing (v1) ...
    "deepagents>=0.4.1",

    # New (v2)
    "pydantic-deep>=0.1.0",
    "pydantic-ai-backend>=0.1.0",
]

[project.optional-dependencies]
dev = [
    # ... existing ...
    "pytest-asyncio>=0.23.0",  # For async tests
]
```

---

## Next Steps

1. Review this plan
2. Run `/code plan/docker-agentv2-pydantic-20260221-173856` to start Phase 1
3. Or modify plan as needed
