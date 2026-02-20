# Phase 1: Define Subagents

## Objective
Create 6 subagent configurations with embedded system_prompt guidance.

## Prerequisites
- None

## Tasks

### 1.1 Create _build_subagents() method
- [ ] Add method to DockerAgent class
- [ ] Return list of subagent dicts

**File:** `src/multi_agent/agents/docker_agent.py`

```python
def _build_subagents(self) -> list[dict]:
    """Build subagent configurations for each tool group."""
    return [
        self._build_container_subagent(),
        self._build_image_subagent(),
        self._build_network_subagent(),
        self._build_volume_subagent(),
        self._build_compose_subagent(),
        self._build_system_subagent(),
    ]
```

### 1.2 Define container-agent
- [ ] Import CONTAINER_TOOLS
- [ ] Create subagent dict with embedded guidance

```python
def _build_container_subagent(self) -> dict:
    return {
        "name": "container-agent",
        "description": "Manages Docker containers: list, run, start, stop, restart, remove, logs, stats, exec, inspect",
        "system_prompt": """Docker container specialist.

## Guardrails
- Report impact before destructive operations (remove, stop)
- Don't repeat identical failing calls more than twice
- Verify with inspect after operations

## Workflow
1. Identify container and safety impact
2. Execute operation
3. Verify result with inspect/list
4. Report outcome concisely
""",
        "tools": list(CONTAINER_TOOLS),
    }
```

### 1.3 Define image-agent
```python
{
    "name": "image-agent",
    "description": "Manages Docker images: list, pull, build, tag, remove, inspect, prune",
    "system_prompt": """Docker image specialist.

## Guardrails
- Report impact before prune operations
- Use workspace paths for build_image
- Don't repeat failing pull/build commands

## Workflow
1. Identify image requirements
2. Execute operation (pull/build/tag)
3. Verify with inspect/list
4. Report outcome
""",
    "tools": list(IMAGE_TOOLS),
}
```

### 1.4 Define network-agent
```python
{
    "name": "network-agent",
    "description": "Manages Docker networks: list, create, remove, connect, disconnect, inspect",
    "system_prompt": """Docker network specialist.

## Guardrails
- Check connected containers before removing networks
- Verify connectivity after connect/disconnect

## Workflow
1. Identify network and affected containers
2. Execute operation
3. Verify with inspect
4. Report outcome
""",
    "tools": list(NETWORK_TOOLS),
}
```

### 1.5 Define volume-agent
```python
{
    "name": "volume-agent",
    "description": "Manages Docker volumes: list, create, remove, inspect, prune",
    "system_prompt": """Docker volume specialist.

## Guardrails
- Check volume usage before removing
- Report impact before prune

## Workflow
1. Identify volume and usage
2. Execute operation
3. Verify with inspect/list
4. Report outcome
""",
    "tools": list(VOLUME_TOOLS),
}
```

### 1.6 Define compose-agent
```python
{
    "name": "compose-agent",
    "description": "Manages Docker Compose: up, down, ps, logs",
    "system_prompt": """Docker Compose specialist.

## Guardrails
- Use workspace paths for compose files
- Report service status after up/down
- Check logs on failure

## Workflow
1. Identify compose file and services
2. Execute operation
3. Verify with compose_ps
4. Report service status
""",
    "tools": list(COMPOSE_TOOLS),
}
```

### 1.7 Define system-agent
```python
{
    "name": "system-agent",
    "description": "Docker system operations: info, prune, version",
    "system_prompt": """Docker system specialist.

## Guardrails
- Report impact before prune operations
- Show version info when requested

## Workflow
1. Execute system operation
2. Report results
""",
    "tools": list(SYSTEM_TOOLS),
}
```

## Files
| File | Action |
|------|--------|
| `src/multi_agent/agents/docker_agent.py` | Add _build_subagents() and helper methods |
| `src/multi_agent/tools/__init__.py` | Verify tool group imports |

## Verification
```bash
source .venv/bin/activate && python3 -c "
from src.multi_agent.agents.docker_agent import DockerAgent
agent = DockerAgent()
subs = agent._build_subagents()
print(f'Subagents: {len(subs)}')
for s in subs:
    print(f'  - {s[\"name\"]}: {len(s[\"tools\"])} tools')
"
```

## Estimate
2 hours (S)
