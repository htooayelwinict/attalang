# Token Bloat Root Cause - v2

## Current State (After Your Changes)

**Tools exposed: 19** (down from 40+)
- 1 safe: `docker_bash`
- 11 SDK: complex operations
- 7 dangerous: HITL-controlled

**Progress:** ✅ Reduced tool count by 50%

## Remaining Problem: JSON Wrapper in `docker_bash`

### Current docker_bash output format:

```json
{
  "success": true,
  "command": "docker ps -a",
  "exit_code": 0,
  "stdout": "CONTAINER ID   IMAGE     COMMAND        CREATED       STATUS        PORTS    NAMES\n...",
  "stderr": ""
}
```

**Token cost:** ~200-250 per call

### OpenClaw output format:

```
CONTAINER ID   IMAGE     COMMAND        CREATED       STATUS        PORTS    NAMES
6e4b15946997   nginx     "/docker-..."   7 sec ago      Up 6 sec      8080->80  web-server
```

**Token cost:** ~50-80 per call

---

## The Problem

`docker_bash` at [docker_tools.py:498](src/multi_agent/tools/docker_tools.py#L498):

```python
payload = {
    "command": "docker " + " ".join(full_args),
    "exit_code": code,
    "stdout": stdout,
    "stderr": stderr,
}
return _ok(**payload)  # Wraps in {"success": true, ...payload}
```

This adds:
1. `"success": true`
2. `"command": "docker ..."`
3. `"exit_code": 0`
4. `"stdout":` + `"stderr":` keys

**Extra tokens:** ~100-150 per call

---

## Comparison Table

| Aspect | Your docker_bash | OpenClaw | Difference |
|--------|------------------|----------|------------|
| Output | JSON with wrapper | Raw stdout | +100 tokens |
| `docker ps` | ~220 tokens | ~70 tokens | **3x** |
| `docker images` | ~180 tokens | ~60 tokens | **3x** |
| `docker logs` | ~500+ tokens | ~150 tokens | **3x** |

---

## Fix Options

### Option 1: Return stdout directly (Recommended)

Change `docker_bash` to return raw stdout:

```python
@tool(args_schema=DockerBashInput)
def docker_bash(command: str, args: str | None = None, ...) -> str:
    """Execute whitelisted Docker CLI commands. Returns raw stdout."""
    code, stdout, stderr = _run_safe_docker_cli(full_args, ...)
    if code == 0:
        return stdout  # Direct return, no JSON wrapper
    return f"Error (exit {code}): {stderr}"  # Simple error format
```

**Result:** Matches OpenClaw exactly

---

### Option 2: Minimal error wrapper

Keep error handling but return raw stdout on success:

```python
if code == 0:
    return stdout  # Raw output
return _error(message)  # Only wrap errors
```

**Result:** ~90% of savings, keeps structured errors

---

### Option 3: Add `raw=True` parameter

```python
def docker_bash(command: str, args: str | None = None, raw: bool = True, ...) -> str:
    if raw:
        return stdout if code == 0 else f"Error: {stderr}"
    return _ok(**payload)
```

**Result:** Backward compatible, more complex

---

## Token Savings Estimate

| Operation | Current | With Fix | Savings |
|-----------|---------|---------|---------|
| `docker ps` | ~220 | ~70 | **68%** |
| `docker images` | ~180 | ~60 | **67%** |
| `docker logs 100` | ~400 | ~120 | **70%** |
| `docker inspect` | ~800 | ~300 | **63%** |

**Overall: ~65-70% additional savings** on top of tool reduction

---

## Combined Savings (Tool reduction + Output fix)

| Metric | Original | After tool cut | After output fix | Total |
|--------|----------|----------------|------------------|-------|
| Tools | 40+ | 19 (-53%) | 19 | **-53%** |
| Tokens/call | ~300 | ~200 | ~70 | **-77%** |

**Total token reduction: ~77%** (from ~300 to ~70 per call)

---

## Recommendation

**Implement Option 1** (return stdout directly):

1. Matches OpenClaw exactly
2. Maximum token savings
3. Simple implementation
4. Easier debugging (raw output)

**Change needed:** 1 line in `docker_bash` function
