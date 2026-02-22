# Phase 3: Update Agent Configuration

## Objective
Update `DockerAgent` to prefer bash-based tools while maintaining HITL for dangerous operations.

## Prerequisites
- Phase 2 complete: Safe tools migrated to bash

## Tasks

- [ ] Review `DANGEROUS_TOOLS` and `AUTO_REJECT_TOOLS` lists
- [ ] Update agent instructions to prefer `docker_bash()` for common ops
- [ ] Ensure HITL interrupt configuration unchanged
- [ ] Add `docker_bash` to `ALL_DOCKER_TOOLS` list
- [ ] Update exports in `__all__`

## Files to Create/Modify

| File | Action | Details |
|------|--------|---------|
| `src/multi_agent/tools/docker_tools.py` | Modify | Update ALL_DOCKER_TOOLS and __all__ |
| `src/multi_agent/agents/docker_agent.py` | Review | Verify HITL config intact |

## Configuration Updates

### Update ALL_DOCKER_TOOLS
```python
BASH_TOOLS = [docker_bash]

# Migrated tools (now bash-based internally)
BASH_BASED_TOOLS = [
    list_containers,
    list_images,
    list_networks,
    list_volumes,
    start_container,
    stop_container,
    restart_container,
    get_container_logs,
    get_container_stats,
    inspect_container,
    inspect_image,
    inspect_network,
    inspect_volume,
    docker_system_info,
    docker_version,
    compose_ps,
    compose_logs,
]

# SDK-based tools (complex operations)
SDK_TOOLS = [
    run_container,
    build_image,
    pull_image,
    tag_image,
    create_network,
    create_volume,
    connect_to_network,
    disconnect_from_network,
    exec_in_container,
    compose_up,
    compose_down,
]

# Dangerous tools (SDK + HITL)
DANGEROUS_SDK_TOOLS = [
    remove_image,
    prune_images,
    remove_container,
    remove_network,
    remove_volume,
    prune_volumes,
    docker_system_prune,
]

ALL_DOCKER_TOOLS = BASH_TOOLS + BASH_BASED_TOOLS + SDK_TOOLS + DANGEROUS_SDK_TOOLS
```

### Verify HITL Config Unchanged
```python
# In docker_agent.py - MUST remain unchanged
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

### Optional: Add to Agent Instructions
```python
DOCKER_AGENT_INSTRUCTIONS = """...
## TOOL PREFERENCES
- Use `docker_bash` for: ps, images, logs, start, stop, restart, inspect
- SDK tools available for: run, build, pull, create, exec
- Dangerous ops require approval: remove, prune
..."""
```

## Verification
```bash
# Run all tests
.venv/bin/python -m pytest tests/ -v

# Verify HITL still works
.venv/bin/python -m src.multi_agent.runtime.cli --prompt "remove nginx image"
# Should prompt for approval

# Verify auto-reject works
.venv/bin/python -m src.multi_agent.runtime.cli --prompt "prune all volumes"
# Should auto-reject
```

## Estimated Effort
**1-2 hours (S)**

## Deliverables
- Updated tool exports
- HITL configuration verified
- Agent instructions updated (optional)
