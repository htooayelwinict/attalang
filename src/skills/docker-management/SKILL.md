---
name: docker-management
description: Docker operations with conflict-aware resource management
---

# Docker Tools Reference

## Container Tools
list_containers, run_container, start_container, stop_container, restart_container,
remove_container, get_container_logs, get_container_stats, exec_in_container, inspect_container

## Image Tools
list_images, pull_image, build_image, tag_image, remove_image, inspect_image, prune_images

## Network Tools
list_networks, create_network, remove_network, connect_to_network, disconnect_from_network, inspect_network

## Volume Tools
list_volumes, create_volume, remove_volume, inspect_volume, prune_volumes

## Compose Tools
compose_up, compose_down, compose_ps, compose_logs

## System Tools
docker_system_info, docker_system_prune, docker_version

---

# Workflow Rules

## 1. PRE-CHECK (MANDATORY)
Before creating any resource, verify it doesn't exist:
- `list_containers(all_containers=True)` before `run_container`
- `list_networks()` before `create_network`
- `list_volumes()` before `create_volume`

## 2. PORT CONFLICTS
Check `list_containers` output for port bindings:
- Format: `{"80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}]}`
- If port taken: report conflict, don't proceed

## 3. NAME CONFLICTS
- Container names must be unique
- Network names must be unique
- Volume names must be unique
- If exists: reuse or suggest alternative

## 4. EXECUTION PATTERN
```
1. ASSESS: list_* to check current state
2. PLAN: identify gaps
3. CREATE: only what's missing
4. DONE: report, don't re-verify
```

## 5. ERROR HANDLING
- `"success": false` = failure, read error message
- `"success": true` = success, move on
- Truncated output = normal, not error

## Anti-Patterns (DO NOT DO)
- Re-listing after successful create
- Spawning containers for HTTP checks
- Retrying with identical arguments
- Creating without pre-checking
