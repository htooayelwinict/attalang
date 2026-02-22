# Context Explosion Analysis

## Problem Summary

The hybrid plan at `plan/docker-tools-hybrid-20260222-183737/` was **partially implemented** but still causes context explosion.

## Root Causes

### 1. `docker_bash()` Not Exposed as Tool

**Location:** [docker_tools.py:478](src/multi_agent/tools/docker_tools.py#L478)

```python
def docker_bash(command: str, ...):  # ❌ Missing @tool decorator
    """Execute safe Docker CLI commands."""
    # ... implementation
```

**Impact:** Agent cannot call `docker_bash()` directly. It's not in the exported tools list.

**Fix:** Add `@tool` decorator and export in `__all__`.

---

### 2. Tools Still Restructure JSON Verbosely

**Example:** `list_containers` at [docker_tools.py:510](src/multi_agent/tools/docker_tools.py#L510)

Even though it uses bash (`_run_safe_docker_cli`), it:

1. Gets `docker ps --format json` (compact)
2. Parses each line
3. **Rebuilds** each item with MORE fields:
   ```python
   {
       "id": _short_id(...),
       "name": ...,
       "status": ...,
       "image": ...,
       "ports": _parse_ports_string(...),  # ⚠️ Adds nested dict
       "created": ...
   }
   ```
4. Returns `_ok(count=len(items), containers=items)` - even more wrapper

**Token cost:** ~200-300 per call vs OpenClaw's ~50

---

### 3. `ALL_DOCKER_TOOLS` Still Has 40+ Tools

The agent sees 40+ specialized tools. Each has verbose docstrings and schema definitions that add to context.

OpenClaw has: 1 bash tool.

---

## Comparison

| Aspect | OpenClaw | Our V1 (Post-"Migration") |
|--------|----------|---------------------------|
| Tools exposed | 1 generic bash | 40+ specialized tools |
| `docker ps` output | Raw text (~50 tokens) | Restructured JSON (~250 tokens) |
| Agent sees | `bash` command | `list_containers`, `start_container`, etc. |
| Implementation | Direct stdout passthrough | Parse → Transform → Return |

---

## Recommended Fix

**Option 1: Expose `docker_bash` as primary tool (Recommended)**

```python
@tool
def docker_bash(command: str, args: str | None = None) -> str:
    """Execute safe Docker CLI commands. Returns raw stdout."""
    # Return stdout directly, no JSON wrapping
```

Then:
1. Remove or deprecate 15+ redundant tools
2. Keep only SDK-based tools that NEED complex logic (`run_container`, etc.)

**Option 2: Make tools pass-through mode**

Add `--raw` flag to existing tools to skip JSON restructuring.

---

## Token Savings Estimate

| Tool | Current | With Fix | Savings |
|------|---------|---------|---------|
| `list_containers` | ~250 | ~50 | 80% |
| `list_images` | ~200 | ~40 | 80% |
| `get_container_logs` | ~500+ | ~100 | 80% |

**Overall: 70-80% token reduction** as originally planned.

---

## Implementation Checklist

- [ ] Add `@tool` to `docker_bash()`
- [ ] Add `docker_bash` to `__all__` exports
- [ ] Create passthrough version returning raw stdout
- [ ] Remove/deprecate redundant tools
- [ ] Update agent instructions to prefer `docker_bash`
- [ ] Test token reduction
