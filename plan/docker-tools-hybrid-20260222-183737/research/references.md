# References and Best Practices

## OpenClaw Bash Patterns

OpenClaw achieves 70-80% token efficiency by using direct bash commands instead of SDK wrappers.

### Key Patterns

1. **Simple Table Output**
   ```bash
   docker ps --format "table {{.ID}}\t{{.Names}}\t{{.Status}}"
   ```
   Output: 50-80 tokens vs 200-300 with SDK JSON

2. **One-Shot Commands**
   ```bash
   docker start nginx  # vs SDK client.containers.get("nginx").start()
   ```
   Output: 20 tokens vs 100+ with SDK

3. **Output Truncation**
   ```bash
   docker logs --tail 100 nginx | head -c 2000
   ```
   Built-in limits prevent token explosion

## Docker CLI Best Practices

### Safe Commands (read-only, no side effects)
- `docker ps`, `docker images`, `docker network ls`, `docker volume ls`
- `docker logs`, `docker stats`, `docker inspect`
- `docker info`, `docker version`
- `docker compose ps`, `docker compose logs`

### Commands Requiring Caution
- `docker start`, `docker stop`, `docker restart` - Safe but state-changing
- `docker rm` - Destructive but container-specific
- `docker network rm`, `docker volume rm` - Can break other resources

### Commands Requiring Approval
- `docker rmi`, `docker image prune` - Can break running containers
- `docker volume prune` - DATA LOSS
- `docker system prune` - DESTRUCTIVE

## Token Comparison Examples

### list_containers (5 containers)

**SDK Approach (~250 tokens):**
```json
{
  "success": true,
  "count": 5,
  "containers": [
    {"id": "abc123", "name": "nginx", "status": "running", "image": "nginx:latest", "ports": {"80/tcp": 8000}, "created": "2024-01-15T10:00:00Z"},
    {"id": "def456", "name": "redis", "status": "running", "image": "redis:alpine", "ports": {"6379/tcp": 6379}, "created": "2024-01-15T10:05:00Z"},
    // ... 3 more
  ]
}
```

**Bash Approach (~60 tokens):**
```
CONTAINER ID   NAME     STATUS    IMAGE           PORTS
abc123         nginx    running   nginx:latest    0.0.0.0:8000->80/tcp
def456         redis    running   redis:alpine    0.0.0.0:6379->6379/tcp
xyz789         app      running   myapp:v1        0.0.0.0:3000->3000/tcp
```

### get_container_logs

**SDK Approach (~180 tokens):**
```json
{
  "success": true,
  "container_id": "abc123",
  "container_name": "nginx",
  "logs": "2024-01-15 10:00:00 Server started\n2024-01-15 10:00:01 Listening on port 80\n..."
}
```

**Bash Approach (~40 tokens):**
```
2024-01-15 10:00:00 Server started
2024-01-15 10:00:01 Listening on port 80
```

## Implementation References

### subprocess.run Pattern
```python
result = subprocess.run(
    ["docker", "ps", "--format", "{{.ID}}\t{{.Names}}\t{{.Status}}"],
    capture_output=True,
    text=True,
    timeout=30
)
if result.returncode == 0:
    return _ok(output=result.stdout)
return _error(result.stderr)
```

### Command Whitelist Pattern
```python
ALLOWED_COMMANDS = {
    "ps", "images", "logs", "stats", "inspect",
    "start", "stop", "restart",
    "network ls", "network inspect",
    "volume ls", "volume inspect",
    "info", "version",
    "compose ps", "compose logs"
}
```

### Argument Validation
```python
def _validate_docker_command(cmd: str) -> str:
    """Validate docker command is safe."""
    parts = shlex.split(cmd)
    if not parts or parts[0] != "docker":
        raise ValueError("Only docker commands allowed")

    # Check against whitelist
    subcommand = " ".join(parts[1:3]) if len(parts) > 2 else parts[1] if len(parts) > 1 else ""
    if not any(subcommand.startswith(allowed) for allowed in ALLOWED_COMMANDS):
        raise ValueError(f"Command not in whitelist: {subcommand}")

    return cmd
```

## Error Handling

Docker CLI returns:
- Exit code 0 = success
- Exit code 1+ = error
- stderr contains error message

```python
def _run_docker_command(args: list[str], timeout: int = 30) -> tuple[bool, str]:
    result = subprocess.run(
        ["docker"] + args,
        capture_output=True,
        text=True,
        timeout=timeout
    )
    if result.returncode == 0:
        return True, result.stdout
    return False, result.stderr or f"Exit code {result.returncode}"
```

## Related Files

- `src/multi_agent/tools/docker_tools.py` - Current SDK implementation
- `src/multi_agent/agents/docker_agent.py` - HITL configuration
- `src/multi_agent_v2/tools/docker_tools_v2.py` - V2 reference (similar patterns)
