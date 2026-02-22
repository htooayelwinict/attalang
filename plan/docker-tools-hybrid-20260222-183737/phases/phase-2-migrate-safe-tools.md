# Phase 2: Migrate Safe Tools to Bash

## Objective
Replace 15 safe SDK-based tools with bash equivalents using `docker_bash()` internally, reducing token usage by 70-80%.

## Prerequisites
- Phase 1 complete: `docker_bash()` tool exists

## Tasks

- [ ] Migrate `list_containers` → use `docker ps --format`
- [ ] Migrate `list_images` → use `docker images --format`
- [ ] Migrate `list_networks` → use `docker network ls --format`
- [ ] Migrate `list_volumes` → use `docker volume ls --format`
- [ ] Migrate `start_container` → use `docker start`
- [ ] Migrate `stop_container` → use `docker stop`
- [ ] Migrate `restart_container` → use `docker restart`
- [ ] Migrate `get_container_logs` → use `docker logs --tail`
- [ ] Migrate `get_container_stats` → use `docker stats --no-stream`
- [ ] Migrate `inspect_container` → use `docker inspect`
- [ ] Migrate `inspect_image` → use `docker image inspect`
- [ ] Migrate `inspect_network` → use `docker network inspect`
- [ ] Migrate `inspect_volume` → use `docker volume inspect`
- [ ] Migrate `docker_system_info` → use `docker info`
- [ ] Migrate `docker_version` → use `docker version`
- [ ] Migrate `compose_ps` → use `docker compose ps`
- [ ] Migrate `compose_logs` → use `docker compose logs`

## Files to Create/Modify

| File | Action | Details |
|------|--------|---------|
| `src/multi_agent/tools/docker_tools.py` | Modify | Replace 15 tool implementations |

## Migration Pattern

### Before (SDK-based)
```python
@tool
def list_containers(all_containers: bool = False, filters: str | None = None) -> str:
    """List containers with basic metadata."""
    try:
        client = _docker_client()
        parsed_filters = _parse_json(filters, "filters") if filters else None
        items = []
        for container in client.containers.list(all=all_containers, filters=parsed_filters):
            items.append({
                "id": container.short_id,
                "name": container.name,
                "status": container.status,
                "image": container.image.tags[0] if container.image.tags else container.image.short_id,
                "ports": container.ports,
                "created": container.attrs.get("Created"),
            })
        return _ok(count=len(items), containers=items)
    except Exception as exc:
        return _error(str(exc))
```

### After (Bash-based)
```python
@tool
def list_containers(all_containers: bool = False, filters: str | None = None) -> str:
    """List containers with basic metadata."""
    try:
        cmd_parts = ["ps", "--format", "{{.ID}}\\t{{.Names}}\\t{{.Status}}\\t{{.Image}}\\t{{.Ports}}"]
        if all_containers:
            cmd_parts.insert(1, "-a")
        # Note: filters not supported in simple bash, SDK fallback if needed
        success, output = _run_docker_cli(cmd_parts)
        if success:
            return _ok(output=_truncate_text(output))
        return _error(output)
    except Exception as exc:
        return _error(str(exc))
```

## Tools to Keep (SDK-based)

Keep these with their current SDK implementation:

| Tool | Reason |
|------|--------|
| `run_container` | Complex port/env/volume mapping |
| `build_image` | Build context handling |
| `pull_image` | Progress streaming |
| `tag_image` | SDK simpler |
| `create_network` | IPAM options complex |
| `create_volume` | Driver options |
| `connect_to_network` | SDK more reliable |
| `disconnect_from_network` | SDK more reliable |
| `exec_in_container` | Output handling better with SDK |
| `compose_up` | File resolution |
| `compose_down` | File resolution |

## Tools to Keep with HITL (SDK-based)

These dangerous tools keep SDK + HITL:

| Tool | HITL Status |
|------|-------------|
| `remove_image` | Requires approval |
| `prune_images` | Requires approval |
| `remove_container` | Requires approval |
| `remove_network` | Requires approval |
| `remove_volume` | AUTO-REJECT |
| `prune_volumes` | AUTO-REJECT |
| `docker_system_prune` | AUTO-REJECT |

## Verification
```bash
# Run existing tests
.venv/bin/python -m pytest tests/test_langgraph_runtime.py -v

# Manual token comparison
.venv/bin/python -c "
from src.multi_agent.tools.docker_tools import list_containers
import tiktoken
result = list_containers()
print(f'Output length: {len(result)} chars')
print(f'Estimated tokens: {len(result)//4}')
print(result[:500])
"
```

## Estimated Effort
**4-6 hours (M)**

## Deliverables
- 15 tools migrated to bash-based implementation
- Token reduction verified (70%+ improvement)
- All existing tests pass
