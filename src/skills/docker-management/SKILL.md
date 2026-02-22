---
name: docker-management
description: Docker operations with conflict-aware resource management
---

# Docker Tools Reference

## Primary Tool
- `docker_bash` for safe read/start/stop/restart/inspect/log/stat/version/info operations.

## SDK Tools (structured operations)
- `run_container`, `pull_image`, `build_image`, `tag_image`
- `create_network`, `create_volume`, `connect_to_network`, `disconnect_from_network`
- `exec_in_container`, `compose_up`, `compose_down`

## Dangerous SDK Tools (HITL controlled)
- `remove_image`, `prune_images`, `remove_container`
- `remove_network`, `remove_volume`, `prune_volumes`, `docker_system_prune`

---

# Workflow Rules

## 1. PRE-CHECK (MANDATORY)
Before creating any resource, verify it doesn't exist:
- `docker_bash(command="ps", args="-a")` before `run_container`
- `docker_bash(command="network ls")` before `create_network`
- `docker_bash(command="volume ls")` before `create_volume`

## 2. PORT CONFLICTS
Check `docker_bash(command="ps", args="-a")` output for container/port conflicts.
- If port taken: report conflict, don't proceed

## 3. NAME CONFLICTS
- Container names must be unique
- Network names must be unique
- Volume names must be unique
- If exists: reuse or suggest alternative

## 4. EXECUTION PATTERN
```
1. ASSESS: use docker_bash read/list commands to check current state
2. PLAN: identify gaps
3. EXECUTE: create only what's missing
4. DONE: report, don't re-verify
```

## 5. ERROR HANDLING
- `docker_bash` output starting with `Error:` = failure
- `docker_bash` output not starting with `Error:` = success
- SDK tool JSON with `"success": false` = failure
- SDK tool JSON with `"success": true` = success
- Truncated output = normal, not error

## Anti-Patterns (DO NOT DO)
- Re-listing after successful create
- Spawning containers for HTTP checks
- Retrying with identical arguments
- Creating without pre-checking
