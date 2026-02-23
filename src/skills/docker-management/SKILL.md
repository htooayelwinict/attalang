---
name: docker-management
description: Docker operations with conflict-aware resource management
---

# Docker Tools Reference

## Primary Tool: `docker_cli`
Use `docker_cli` for ALL Docker operations — containers, images, networks, volumes, compose, exec, build, etc.

Supported commands (set via `command=` param):
- `ps`, `run`, `exec`, `start`, `stop`, `restart`, `logs`, `stats`, `inspect`, `build`, `pull`, `tag`, `images`
- `network ls`, `network create`, `network inspect`, `network connect`, `network disconnect`
- `volume ls`, `volume create`, `volume inspect`
- `compose up`, `compose down`, `compose ps`, `compose logs`
- `info`, `version`

Examples:
- `docker_cli(command="ps", args="-a")`
- `docker_cli(command="run", args="-d -p 8080:80 --name my-nginx nginx:latest")`
- `docker_cli(command="exec", args="my-nginx sh -c 'curl localhost'")`
- `docker_cli(command="compose up", args="-d --build", cwd="/workspace")`

## Dangerous Tools (HITL — require human approval)
- `remove_container`, `remove_image`, `remove_network`, `prune_images`

## Auto-Rejected Tools (always blocked — never call these)
- `remove_volume`, `prune_volumes`, `docker_system_prune`

---

# Workflow Rules

## 1. PRE-CHECK (MANDATORY)
Before creating any resource, verify it doesn't exist:
- `docker_cli(command="ps", args="-a")` before running a new container
- `docker_cli(command="network ls")` before creating a network
- `docker_cli(command="volume ls")` before creating a volume

## 2. PORT CONFLICTS
Check `docker_cli(command="ps", args="-a")` output for container/port conflicts.
- If port taken: report conflict, don't proceed

## 3. NAME CONFLICTS
- Container names must be unique
- Network names must be unique
- Volume names must be unique
- If exists: reuse or suggest alternative

## 4. EXECUTION PATTERN
```
1. ASSESS: docker_cli list/inspect commands to check current state
2. PLAN: identify what needs creating vs what already exists
3. EXECUTE: docker_cli to create only what's missing
4. DONE: report, don't re-verify
```

## 5. ERROR HANDLING
- `docker_cli` output starting with `Error:` = failure
- `docker_cli` output NOT starting with `Error:` = success
- Dangerous tool JSON with `"success": false` = failure
- Dangerous tool JSON with `"success": true` = success
- Output containing `[TRUNCATED]` = normal, not an error

## Shell Operators Are Blocked
`docker_cli` validates all args and **rejects** any token containing `;`, `|`, `&&`, `||`, `` ` ``, `$(`.
This affects two common patterns — avoid them:

### ❌ Go template with semicolon separator
```
# BLOCKED — semicolon inside {{range}} template
docker_cli(command="inspect", args="mybox --format '{{range .Mounts}}{{.Name}}; {{end}}'")
```
```
# OK — use a safe separator or plain format
docker_cli(command="inspect", args="mybox --format '{{range .Mounts}}{{.Name}} {{.Destination}} {{end}}'")
```

### ❌ Shell pipe after --format
```
# BLOCKED — pipe to grep is a shell operator
docker_cli(command="images", args="--format '{{.Repository}}:{{.Tag}}' | grep nginx")
```
```
# OK — drop the grep, inspect the raw output yourself
docker_cli(command="images", args="--format '{{.Repository}}:{{.Tag}}'")
```

### ❌ sh -c with semicolons
```
# BLOCKED — semicolon in exec payload
docker_cli(command="exec", args="mybox sh -c 'apt-get update; apt-get install -y curl'")
```
```
# OK — use && for sequential commands (also blocked) → split into separate exec calls
docker_cli(command="exec", args="mybox apt-get update")
docker_cli(command="exec", args="mybox apt-get install -y curl")
```

## Anti-Patterns (DO NOT DO)
- Re-listing after successful create
- Spawning containers for HTTP checks
- Retrying with identical arguments
- Creating without pre-checking
- Using `;` or `|` anywhere in args (even inside Go templates)
