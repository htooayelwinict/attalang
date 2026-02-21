---
name: docker-management-v2
description: Docker operations with conflict-aware resource management for DockerAgentV2
---

# Docker Tools Reference (V2)

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

# Workflow Rules

## 1. PRE-CHECK (MANDATORY)
Before creating any resource, verify it doesn't exist:
- `list_containers(all_containers=True)` before `run_container`
- `list_networks()` before `create_network`
- `list_volumes()` before `create_volume`

## 2. PORT CONFLICTS
Check `list_containers` output for port bindings.
If port is taken, report conflict and do not proceed with same port.

## 3. NAME CONFLICTS
Container, network, and volume names must be unique.
Reuse existing resources when valid.

## 4. EXECUTION PATTERN
1. ASSESS: list resources
2. PLAN: identify gaps
3. CREATE: create only missing parts
4. DONE: report without redundant re-checks

## 5. ERROR HANDLING
- `"success": false` means failure
- `"success": true` means success
- Truncated output is normal and should not be treated as failure
