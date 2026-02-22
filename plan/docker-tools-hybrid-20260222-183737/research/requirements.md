# Requirements Analysis

## Problem Statement

V1 Docker agent uses Docker SDK with 40+ specialized tools returning verbose JSON, causing 150-300 tokens per tool call. Need hybrid approach to achieve 70-80% token reduction for common operations.

## Current State

- **File:** `src/multi_agent/tools/docker_tools.py` (1379 lines)
- **40+ Tools** using Docker SDK Python package
- **Categories:** CONTAINER_TOOLS (10), IMAGE_TOOLS (7), NETWORK_TOOLS (6), VOLUME_TOOLS (5), SYSTEM_TOOLS (3), COMPOSE_TOOLS (4)

### Current Tool Output Pattern
```json
{
  "success": true,
  "container_id": "abc123",
  "container_name": "nginx",
  "status": "running",
  "image": "nginx:latest",
  "ports": {"80/tcp": 8000},
  "created": "2024-01-15T10:00:00Z"
}
```

### Token Cost Analysis (Current SDK Approach)

| Operation | SDK Tool Output | Est. Tokens |
|-----------|-----------------|-------------|
| list_containers (5 items) | Full JSON with all fields | ~200-300 |
| get_container_logs | {"success": true, "logs": "...", ...} | ~150-250 |
| run_container | Full container metadata | ~150-200 |
| inspect_container | Nested state/config/host_config/network | ~400-600 |

## Target State

Hybrid approach:
1. **Safe operations** → `docker_bash()` tool (direct CLI, concise output)
2. **Dangerous operations** → Keep SDK tools with HITL (security)

### Bash-Based Output Pattern
```text
CONTAINER ID   NAME    STATUS    PORTS
abc123         nginx   running   0.0.0.0:8000->80/tcp
```

### Expected Token Savings

| Operation | Current | Bash Approach | Savings |
|-----------|---------|---------------|---------|
| list_containers | 200-300 | 50-80 | ~70% |
| get_container_logs | 150-250 | 30-50 | ~80% |
| start/stop/restart | 100-150 | 20-30 | ~80% |
| docker ps, images, etc | 150-300 | 40-60 | ~75% |

## Safe vs Dangerous Classification

### SAFE (can use bash)
- list_containers (docker ps)
- list_images (docker images)
- list_networks (docker network ls)
- list_volumes (docker volume ls)
- get_container_logs (docker logs)
- get_container_stats (docker stats --no-stream)
- inspect_container (docker inspect)
- inspect_image (docker image inspect)
- inspect_network (docker network inspect)
- inspect_volume (docker volume inspect)
- start_container (docker start)
- stop_container (docker stop)
- restart_container (docker restart)
- docker_system_info (docker info)
- docker_version (docker version)
- compose_ps (docker compose ps)
- compose_logs (docker compose logs)

### DANGEROUS (keep SDK + HITL)
- remove_image - can break running containers
- prune_images - deletes images
- remove_volume - DATA LOSS RISK
- prune_volumes - DATA LOSS RISK
- docker_system_prune - deletes everything
- remove_container - less critical but still needs caution
- remove_network - can break connectivity

### NEEDS SDK (complex operations)
- run_container - port mapping, env, volumes need SDK
- build_image - complex build args
- create_network - needs SDK for options
- create_volume - needs SDK for options
- connect_to_network - SDK more reliable
- disconnect_from_network - SDK more reliable
- exec_in_container - SDK better for output handling
- tag_image - SDK simpler
- pull_image - SDK handles progress
- compose_up - needs file handling
- compose_down - needs file handling

## Acceptance Criteria

1. `docker_bash()` tool created with safety validation
2. 15+ safe tools migrated to bash equivalents
3. HITL maintained for all dangerous operations
4. Token reduction of 70%+ for common operations (verify with test)
5. All existing tests pass
6. No breaking changes to agent behavior
