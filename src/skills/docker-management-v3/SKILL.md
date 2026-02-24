---
name: docker-management-v3-programmatic
description: Programmatic Docker operations — write Python code that calls Docker tools as functions
---

# Programmatic Docker Agent (V3) — Skill Reference

You have ONE tool: `execute_docker_code`. You write Python code that calls Docker functions directly.
This is drastically faster than calling tools one at a time.

## Available Function

```
docker_cli(command: str, args: str | None = None, cwd: str | None = None, timeout: int = 30) -> str
```

Executes whitelisted Docker CLI commands. Returns stdout on success, "Error: ..." on failure.

### Supported commands (via `command=` param)
- Containers: `ps`, `run`, `exec`, `start`, `stop`, `restart`, `logs`, `stats`, `inspect`
- Images: `images`, `pull`, `build`, `tag`
- Networks: `network ls`, `network create`, `network inspect`, `network connect`, `network disconnect`
- Volumes: `volume ls`, `volume create`, `volume inspect`
- Compose: `compose up`, `compose down`, `compose ps`, `compose logs`
- System: `info`, `version`

---

## Code Execution Environment

### Available
- `print()` — captured as output (the ONLY way to return results)
- `docker_cli()` — the Docker function
- Builtins: `range`, `len`, `enumerate`, `zip`, `sorted`, `min`, `max`, `sum`, `any`, `all`, `isinstance`, `hasattr`, `getattr`, `abs`, `round`, `repr`
- Imports: `json`, `re`, `time`, `textwrap`, `itertools`, `functools`, `collections`
- Control flow: loops, conditionals, try/except, list comprehensions, f-strings

### Blocked (security)
- `os`, `sys`, `subprocess`, `shutil`, `pathlib` — no system access
- `open()`, `eval()`, `exec()` — no file I/O or dynamic execution
- `requests`, `urllib`, `socket` — no network calls
- Any import not in the allowed list

---

## Calling Convention

ALWAYS use keyword arguments:
```python
# ✅ Correct
docker_cli(command="ps", args="-a")
docker_cli(command="run", args="-d --name my-app nginx:alpine")

# ❌ Wrong — positional args
docker_cli("ps", "-a")
```

---

## Patterns

### Batch operations (loops)
```python
images = ["redis:7-alpine", "nginx:alpine", "postgres:15-alpine"]
for img in images:
    result = docker_cli(command="pull", args=img)
    print(f"Pull {img}: {'OK' if not result.startswith('Error') else result}")
```

### Pre-check then create
```python
import json

# Check existing
existing = docker_cli(command="network ls", args="--format '{{.Name}}'")
if "my-network" not in existing:
    docker_cli(command="network create", args="my-network --subnet 172.28.0.0/16")
    print("Created my-network")
else:
    print("my-network already exists")
```

### Multi-phase deployment
```python
# Phase 1: Infrastructure
docker_cli(command="network create", args="app-net")
docker_cli(command="volume create", args="db-data")
print("Phase 1: Infrastructure ✓")

# Phase 2: Services
docker_cli(command="run", args="-d --name db --network app-net -v db-data:/var/lib/postgresql/data -e POSTGRES_PASSWORD=secret postgres:15-alpine")
docker_cli(command="run", args="-d --name redis --network app-net redis:7-alpine")
print("Phase 2: Services ✓")

# Phase 3: App
docker_cli(command="run", args="-d --name app --network app-net -p 8080:80 nginx:alpine")
print("Phase 3: App ✓")
```

### Parse JSON output
```python
import json

raw = docker_cli(command="ps", args="-a --format '{{json .}}'")
for line in raw.strip().split("\n"):
    if line.strip():
        c = json.loads(line)
        print(f"{c['Names']}: {c['State']} ({c['Status']})")
```

### Health check / exec
```python
result = docker_cli(command="exec", args="my-nginx curl -s http://localhost")
if result.startswith("Error"):
    # curl might not be installed, try wget
    result = docker_cli(command="exec", args="my-nginx wget -qO- http://localhost")
print(f"Health check: {result[:200]}")
```

---

## Shell Operators Are Blocked

`docker_cli` rejects any args containing `;`, `|`, `&&`, `||`, `` ` ``, `$(`.

### ❌ Blocked patterns
```python
# Pipe
docker_cli(command="images", args="--format '{{.Repository}}' | grep nginx")
# Semicolon in Go template
docker_cli(command="inspect", args="box --format '{{range .Mounts}}{{.Name}}; {{end}}'")
# Shell chaining in exec
docker_cli(command="exec", args="box sh -c 'apt update && apt install curl'")
```

### ✅ Correct alternatives
```python
# Filter in Python instead
output = docker_cli(command="images", args="--format '{{.Repository}}:{{.Tag}}'")
for line in output.split("\n"):
    if "nginx" in line:
        print(line)

# Space separator instead of semicolon
docker_cli(command="inspect", args="box --format '{{range .Mounts}}{{.Name}} {{.Destination}} {{end}}'")

# Separate exec calls
docker_cli(command="exec", args="box apt-get update")
docker_cli(command="exec", args="box apt-get install -y curl")
```

---

## Error Handling

```python
result = docker_cli(command="run", args="-d --name my-app -p 8080:80 nginx:alpine")
if result.startswith("Error"):
    print(f"Failed: {result}")
    # Check if port conflict
    if "port is already allocated" in result:
        print("Port 8080 is taken, trying 8081")
        result = docker_cli(command="run", args="-d --name my-app -p 8081:80 nginx:alpine")
else:
    print(f"Container started: {result[:12]}")
```

- Output starting with `Error:` or `Error (exit N):` = failure
- `[TRUNCATED]` in output = normal, not an error
- Empty output = success for some commands (e.g., `stop`, `start`)

---

## Destructive Operations — NOT AVAILABLE

These tools are **not available** in programmatic mode:
- `remove_container`, `remove_image`, `remove_network`, `remove_volume`
- `prune_images`, `prune_volumes`, `docker_system_prune`

If user asks for cleanup/removal: explain that HITL approval is required
and suggest using the standard V1 agent (`multi-agent-cli`) instead.

---

## Anti-Patterns (DO NOT DO)

- Re-listing resources after successful create (trust the output)
- Spawning curl/wget containers for HTTP checks (use `exec` instead)
- Retrying with identical arguments after failure
- Creating resources without pre-checking existence
- Using `>5` execute_docker_code calls per task (plan efficiently)
- Using positional arguments with docker_cli
- Putting `;`, `|`, `&&` in docker_cli args
