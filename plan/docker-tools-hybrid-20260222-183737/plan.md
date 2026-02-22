# Plan: Docker Tools Hybrid Optimization

## Context

V1 Docker agent uses Docker SDK with 40+ specialized tools returning verbose JSON, causing 150-300 tokens per tool call. This plan implements a hybrid approach: bash commands for safe operations, SDK tools with HITL for dangerous operations.

**Goal:** 70-80% token reduction for common operations while maintaining HITL security.

## Existing Code Patterns

### Tool Response Format (preserve)
```python
def _ok(**data: Any) -> str:
    return _json({"success": True, **data})

def _error(message: str, **data: Any) -> str:
    return _json({"success": False, "error": message, **data})
```

### HITL Configuration (preserve unchanged)
```python
# In docker_agent.py
DANGEROUS_TOOLS: tuple[str, ...] = ("remove_image", "prune_images")
AUTO_REJECT_TOOLS: tuple[str, ...] = ("remove_volume", "prune_volumes", "docker_system_prune")
```

### Truncation (preserve)
```python
MAX_TOOL_STRING_CHARS = int(os.getenv("DOCKER_TOOL_MAX_STRING_CHARS", "1200"))
MAX_TOOL_RESPONSE_CHARS = int(os.getenv("DOCKER_TOOL_MAX_RESPONSE_CHARS", "4000"))
```

## Phase Overview

| # | Name | Objective | Est. Effort |
|---|------|-----------|-------------|
| 1 | Create bash tool | Add `docker_bash()` with whitelist | 2-3h (S) |
| 2 | Migrate safe tools | Convert 15 tools to bash | 4-6h (M) |
| 3 | Update agent config | Verify exports, HITL intact | 1-2h (S) |
| 4 | Testing & validation | Verify token savings, security | 2-3h (S) |

---

## Phase 1: Create docker_bash() Tool

### Objective
Create single `docker_bash()` tool with command whitelist validation for safe Docker CLI execution.

### Tasks
- [ ] Add `SAFE_DOCKER_COMMANDS` whitelist constant in `src/multi_agent/tools/docker_tools.py`
- [ ] Create `_validate_docker_command()` security validation function
- [ ] Create `_run_docker_cli()` helper with timeout/error handling
- [ ] Implement `docker_bash()` tool with `DockerBashInput` schema
- [ ] Add unit tests for command validation

### Files
| File | Action |
|------|--------|
| `src/multi_agent/tools/docker_tools.py` | Modify - add bash tool after line 200 |

### Key Implementation
```python
SAFE_DOCKER_COMMANDS: tuple[str, ...] = (
    "ps", "images", "logs", "stats", "inspect",
    "start", "stop", "restart",
    "network ls", "network inspect",
    "volume ls", "volume inspect",
    "info", "version",
    "compose ps", "compose logs",
)

class DockerBashInput(BaseModel):
    command: str = Field(description="Docker subcommand (e.g., 'ps -a', 'logs nginx')")
    args: str | None = Field(default=None, description="Additional arguments")

@tool(args_schema=DockerBashInput)
def docker_bash(command: str, args: str | None = None) -> str:
    """Execute safe Docker CLI commands for common operations."""
    # ... implementation
```

### Verification
```bash
.venv/bin/python -m pytest tests/test_docker_bash.py -v
```

---

## Phase 2: Migrate Safe Tools to Bash

### Objective
Replace 15 safe SDK-based tools with bash equivalents, achieving 70%+ token reduction.

### Tasks
- [ ] Migrate `list_containers` -> `docker ps --format`
- [ ] Migrate `list_images` -> `docker images --format`
- [ ] Migrate `list_networks` -> `docker network ls --format`
- [ ] Migrate `list_volumes` -> `docker volume ls --format`
- [ ] Migrate `start_container` -> `docker start`
- [ ] Migrate `stop_container` -> `docker stop`
- [ ] Migrate `restart_container` -> `docker restart`
- [ ] Migrate `get_container_logs` -> `docker logs --tail`
- [ ] Migrate `get_container_stats` -> `docker stats --no-stream`
- [ ] Migrate `inspect_container` -> `docker inspect`
- [ ] Migrate `inspect_image` -> `docker image inspect`
- [ ] Migrate `inspect_network` -> `docker network inspect`
- [ ] Migrate `inspect_volume` -> `docker volume inspect`
- [ ] Migrate `docker_system_info` -> `docker info`
- [ ] Migrate `docker_version` -> `docker version`
- [ ] Migrate `compose_ps` -> `docker compose ps`
- [ ] Migrate `compose_logs` -> `docker compose logs`

### Files
| File | Action |
|------|--------|
| `src/multi_agent/tools/docker_tools.py` | Modify - replace 15 tool implementations |

### Tools to Keep (SDK)
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
| `exec_in_container` | Output handling better |
| `compose_up` | File resolution |
| `compose_down` | File resolution |

### Tools to Keep with HITL (SDK + approval)
| Tool | HITL Status |
|------|-------------|
| `remove_image` | Requires approval |
| `prune_images` | Requires approval |
| `remove_container` | Requires approval |
| `remove_network` | Requires approval |
| `remove_volume` | AUTO-REJECT |
| `prune_volumes` | AUTO-REJECT |
| `docker_system_prune` | AUTO-REJECT |

### Verification
```bash
.venv/bin/python -m pytest tests/test_langgraph_runtime.py -v
```

---

## Phase 3: Update Agent Configuration

### Objective
Update `DockerAgent` to include bash tool while maintaining HITL configuration.

### Tasks
- [ ] Add `docker_bash` to `ALL_DOCKER_TOOLS` list
- [ ] Update `__all__` exports
- [ ] Verify `DANGEROUS_TOOLS` and `AUTO_REJECT_TOOLS` unchanged
- [ ] Optional: Update agent instructions to prefer bash for common ops

### Files
| File | Action |
|------|--------|
| `src/multi_agent/tools/docker_tools.py` | Modify - update exports |
| `src/multi_agent/agents/docker_agent.py` | Review - verify HITL intact |

### Verification
```bash
.venv/bin/python -m pytest tests/ -v
.venv/bin/python -m src.multi_agent.runtime.cli --prompt "remove nginx image"
# Should prompt for approval
```

---

## Phase 4: Testing and Validation

### Objective
Validate token reduction and security preservation.

### Tasks
- [ ] Create `tests/test_token_reduction.py`
- [ ] Create `tests/test_docker_bash.py`
- [ ] Run baseline vs post-migration token comparison
- [ ] Verify 70%+ token reduction achieved
- [ ] Verify HITL security intact
- [ ] Document results

### Files
| File | Action |
|------|--------|
| `tests/test_token_reduction.py` | Create |
| `tests/test_docker_bash.py` | Create |

### Verification
```bash
.venv/bin/python -m pytest tests/test_token_reduction.py tests/test_docker_bash.py -v
```

### Success Criteria
| Metric | Target |
|--------|--------|
| Token reduction | 70%+ for common ops |
| All tests pass | 100% |
| HITL intact | Yes |
| No breaking changes | Verified via manual CLI test |

---

## Summary

- **Total Phases:** 4
- **Estimated Effort:** 9-14 hours (1-2 days)
- **Key Risks:**
  - HITL bypass (mitigated by strict whitelist)
  - Tool breakage (mitigated by full test coverage)
- **Dependencies:** None

## Unresolved Questions

1. Should `docker_bash()` be exposed directly to agent or only used internally by migrated tools?
2. Keep migrated tools' JSON output format or use raw bash output?
3. Add token logging to CLI for real-time monitoring?
4. Migrate V2 in parallel or defer?
