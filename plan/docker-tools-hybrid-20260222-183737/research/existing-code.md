# Existing Code Analysis

## Key Files

### 1. `src/multi_agent/tools/docker_tools.py`

**Structure:**
- Lines 1-200: Utility functions (`_truncate_text`, `_ok`, `_error`, `_docker_client`)
- Lines 204-540: Container tools (10 tools)
- Lines 542-718: Image tools (7 tools)
- Lines 720-870: Network tools (6 tools)
- Lines 872-966: Volume tools (5 tools)
- Lines 968-1035: System tools (3 tools)
- Lines 1036-1330: Compose tools (4 tools)
- Lines 1331+: Tool collections and exports

**Patterns to Preserve:**
- `_ok()` and `_error()` response formatters
- `_truncate_text()` for output limits
- `RunContainerInput`, `ExecInContainerInput` Pydantic schemas
- JSON parsing with `_parse_json()`
- Truncation env vars (`DOCKER_TOOL_MAX_STRING_CHARS`, etc.)

### 2. `src/multi_agent/agents/docker_agent.py`

**HITL Configuration:**
```python
DANGEROUS_TOOLS: tuple[str, ...] = (
    "remove_image",
    "prune_images",
)

AUTO_REJECT_TOOLS: tuple[str, ...] = (
    "remove_volume",
    "prune_volumes",
    "docker_system_prune",
)
```

**Interrupt Pattern (Lines 116-135):**
```python
interrupt_on: dict[str, dict[str, list[str]]] | None = None
if self._enable_hitl:
    interrupt_on = {}
    for tool in self._dangerous_tools:
        interrupt_on[tool] = {"allowed_decisions": ["approve", "reject"]}
    for tool in self._auto_reject_tools:
        interrupt_on[tool] = {"allowed_decisions": ["reject"]}
```

## Tool Categories

### CONTAINER_TOOLS (10)
| Tool | Safety | Migration |
|------|--------|-----------|
| list_containers | SAFE | → bash |
| run_container | SDK | Keep |
| start_container | SAFE | → bash |
| stop_container | SAFE | → bash |
| restart_container | SAFE | → bash |
| remove_container | CAUTION | Keep SDK + HITL |
| get_container_logs | SAFE | → bash |
| get_container_stats | SAFE | → bash |
| exec_in_container | SDK | Keep |
| inspect_container | SAFE | → bash |

### IMAGE_TOOLS (7)
| Tool | Safety | Migration |
|------|--------|-----------|
| list_images | SAFE | → bash |
| pull_image | SDK | Keep |
| build_image | SDK | Keep |
| remove_image | DANGEROUS | Keep SDK + HITL |
| tag_image | SDK | Keep |
| inspect_image | SAFE | → bash |
| prune_images | DANGEROUS | Keep SDK + HITL |

### NETWORK_TOOLS (6)
| Tool | Safety | Migration |
|------|--------|-----------|
| list_networks | SAFE | → bash |
| create_network | SDK | Keep |
| remove_network | CAUTION | Keep SDK + HITL |
| connect_to_network | SDK | Keep |
| disconnect_from_network | SDK | Keep |
| inspect_network | SAFE | → bash |

### VOLUME_TOOLS (5)
| Tool | Safety | Migration |
|------|--------|-----------|
| list_volumes | SAFE | → bash |
| create_volume | SDK | Keep |
| remove_volume | DANGEROUS | Keep SDK + AUTO-REJECT |
| inspect_volume | SAFE | → bash |
| prune_volumes | DANGEROUS | Keep SDK + AUTO-REJECT |

### SYSTEM_TOOLS (3)
| Tool | Safety | Migration |
|------|--------|-----------|
| docker_system_info | SAFE | → bash |
| docker_system_prune | DANGEROUS | Keep SDK + AUTO-REJECT |
| docker_version | SAFE | → bash |

### COMPOSE_TOOLS (4)
| Tool | Safety | Migration |
|------|--------|-----------|
| compose_up | SDK | Keep |
| compose_down | SDK | Keep |
| compose_ps | SAFE | → bash |
| compose_logs | SAFE | → bash |

## Summary

- **15 tools** can migrate to bash (SAFE)
- **11 tools** keep SDK (complex operations)
- **5 tools** keep SDK with HITL (DANGEROUS)
- **2 tools** keep SDK with AUTO-REJECT

## Bash Command Mappings

| Current Tool | Bash Equivalent |
|--------------|-----------------|
| list_containers | `docker ps -a --format "{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Ports}}"` |
| start_container | `docker start <id>` |
| stop_container | `docker stop <id>` |
| restart_container | `docker restart <id>` |
| get_container_logs | `docker logs --tail N <id>` |
| get_container_stats | `docker stats --no-stream <id>` |
| inspect_container | `docker inspect <id>` |
| list_images | `docker images --format "{{.ID}}\t{{.Repository}}:{{.Tag}}\t{{.Size}}"` |
| inspect_image | `docker image inspect <image>` |
| list_networks | `docker network ls --format "{{.ID}}\t{{.Name}}\t{{.Driver}}"` |
| inspect_network | `docker network inspect <id>` |
| list_volumes | `docker volume ls --format "{{.Name}}\t{{.Driver}}"` |
| inspect_volume | `docker volume inspect <name>` |
| docker_system_info | `docker info --format "{{json .}}"` |
| docker_version | `docker version --format "{{json .}}"` |
| compose_ps | `docker compose ps` |
| compose_logs | `docker compose logs --tail N` |
