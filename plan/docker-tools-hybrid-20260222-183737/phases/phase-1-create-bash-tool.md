# Phase 1: Create docker_bash() Tool

## Objective
Create a single `docker_bash()` tool that executes safe Docker CLI commands with proper validation and output truncation.

## Prerequisites
- None (foundation phase)

## Tasks

- [ ] Add command whitelist constant `SAFE_DOCKER_COMMANDS` in `src/multi_agent/tools/docker_tools.py`
- [ ] Create `_validate_docker_command()` function with security checks
- [ ] Create `_run_docker_cli()` helper function with timeout and error handling
- [ ] Implement `docker_bash()` tool with `DockerBashInput` schema
- [ ] Add unit tests for command validation

## Files to Create/Modify

| File | Action | Details |
|------|--------|---------|
| `src/multi_agent/tools/docker_tools.py` | Modify | Add bash tool implementation (after line 200) |

## Implementation Details

### SAFE_DOCKER_COMMANDS Whitelist
```python
SAFE_DOCKER_COMMANDS: tuple[str, ...] = (
    "ps",
    "images",
    "logs",
    "stats",
    "inspect",
    "start",
    "stop",
    "restart",
    "network ls",
    "network inspect",
    "volume ls",
    "volume inspect",
    "info",
    "version",
    "compose ps",
    "compose logs",
)
```

### DockerBashInput Schema
```python
class DockerBashInput(BaseModel):
    command: str = Field(description="Docker subcommand (e.g., 'ps -a', 'logs nginx')")
    args: str | None = Field(default=None, description="Additional arguments")
```

### docker_bash() Tool
```python
@tool(args_schema=DockerBashInput)
def docker_bash(command: str, args: str | None = None) -> str:
    """Execute safe Docker CLI commands for common operations.

    Allowed commands: ps, images, logs, stats, inspect, start, stop, restart,
    network ls, network inspect, volume ls, volume inspect, info, version,
    compose ps, compose logs.
    """
    try:
        full_cmd = _validate_docker_command(command, args)
        success, output = _run_docker_cli(full_cmd)
        if success:
            return _ok(output=_truncate_text(output))
        return _error(output)
    except Exception as exc:
        return _error(str(exc))
```

## Verification
```bash
# Run unit tests
.venv/bin/python -m pytest tests/test_docker_bash.py -v

# Manual test
.venv/bin/python -c "
from src.multi_agent.tools.docker_tools import docker_bash
print(docker_bash('ps'))
print(docker_bash('images'))
"
```

## Estimated Effort
**2-3 hours (S)**

## Deliverables
- `docker_bash()` tool with whitelist validation
- Helper functions for command validation and execution
- Unit tests for validation logic
