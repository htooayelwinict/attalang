# Existing Code Analysis

## Files to Modify

### 1. `src/multi_agent/runtime/states.py`
**Current:** TypedDict with `total=False`

```python
class CoordinatorState(TypedDict, total=False):
    origin: Literal["cli"]
    user_input: str
    route: Literal["docker"]
    docker_request: str
    docker_response: str
    final_response: str
    thread_id: str
    error: str

class DockerWorkerState(TypedDict, total=False):
    request: str
    response: str
    thread_id: str
    error: str
```

**Changes:**
- Convert to Pydantic BaseModel
- Add ConfigDict with `extra="forbid"`
- Add `= None` defaults for all optional fields

### 2. `src/multi_agent/runtime/nodes.py`
**Current:** @dataclass with dict access patterns

```python
@dataclass
class RouterNode:
    def invoke(self, state: CoordinatorState) -> CoordinatorState:
        user_input = state.get("user_input", "").strip()
        return {"route": "docker", "docker_request": user_input}
```

**Changes:**
- Keep @dataclass (works with Pydantic state)
- Change `state.get()` → `state.field` or `state.field or default`
- Return dict (LangGraph merges) or BaseModel instance

### 3. `src/multi_agent/runtime/runtime.py`
**Current:** StateGraph with TypedDict

```python
builder = StateGraph(CoordinatorState)
initial_state: CoordinatorState = {"origin": "cli", ...}
result.get("final_response", "")
```

**Changes:**
- StateGraph accepts BaseModel directly (no change needed)
- Initial state: `CoordinatorState(origin="cli", ...)`
- Result access: `result.final_response`

### 4. `tests/test_langgraph_runtime.py`
**Changes:**
- Update assertions to use attribute access
- Add Pydantic validation tests

## Dependencies

| Package | Version | Notes |
|---------|---------|-------|
| `pydantic` | v2.x | Already in deps (tools use it) |
| `langgraph` | v1.0.9 | Native BaseModel support |
| `langchain` | v1.2.10 | Uses Pydantic for tools |

## Access Pattern Changes

| Before (TypedDict) | After (Pydantic) |
|--------------------|------------------|
| `state.get("field", default)` | `state.field or default` |
| `state["field"]` | `state.field` |
| `return {"field": value}` | `return {"field": value}` (dict still works) |
| `result.get("field", "")` | `result.field or ""` |

## Risk Areas

1. **State mutation** - Nodes return dicts, LangGraph merges. Ensure no direct mutation.
2. **Optional fields** - All currently optional. Must add `= None` explicitly.
3. **Type coercion** - Pydantic may coerce types. Use `strict=True` if needed.
