# Research: Migrating V1 TypedDict to Pydantic

**Date:** 2026-02-22
**Query:** Migrating all Types in V1 to Pydantic

## Summary

Pydantic BaseModel is recommended over TypedDict for LangGraph state management. Benefits include runtime validation, better serialization with checkpointers, and unified type system with existing LangChain tools (already using Pydantic). Migration is straightforward with LangGraph's native BaseModel support.

## Key Findings

1. **LangGraph natively supports Pydantic BaseModel** as `state_schema`
2. **TypedDict offers no runtime validation** - silent failures for invalid state
3. **Checkpointers work better with Pydantic** - `.model_dump()` for serialization
4. **Unified type system** - tools already use Pydantic, reduces cognitive load
5. **Overhead negligible** - ~0.1ms per transition vs tool call latency

## Migration Strategy

### Step-by-Step Approach

1. **Define new models with Pydantic** - Start fresh components with BaseModel
2. **Hybrid interim** - Validate TypedDict at entry points with Pydantic
3. **Phased refactoring** - Replace TypedDicts incrementally
4. **Update StateGraph** - Pass BaseModel as `state_schema`
5. **Refactor node signatures** - Update type hints

### Handling `total=False` in Pydantic

TypedDict `total=False` makes all fields optional. Pydantic equivalent:

```python
# TypedDict (before)
class CoordinatorState(TypedDict, total=False):
    route: Literal["docker"]
    request: str
    error: str

# Pydantic (after) - explicit defaults
class CoordinatorState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: Literal["docker"] | None = None
    request: str | None = None
    error: str | None = None
```

**Key difference:** `str | None` means required but None allowed. Add `= None` for truly optional.

## Best Practices

### ConfigDict Settings

```python
from pydantic import BaseModel, ConfigDict, Field

class CoordinatorState(BaseModel):
    model_config = ConfigDict(
        extra="forbid",           # Reject unknown fields
        validate_assignment=True,  # Re-validate on mutation
    )

    route: Literal["docker"] | None = None
    request: str | None = None
    history: list[str] = Field(default_factory=list)  # Mutable default
```

### Node Pattern

```python
from dataclasses import dataclass

@dataclass
class RouterNode:
    def invoke(self, state: CoordinatorState) -> CoordinatorState:
        # Pydantic validates on construction
        if not state.request:
            return CoordinatorState(
                route="docker",
                error="Empty input."
            )
        return CoordinatorState(
            route="docker",
            request=state.request
        )
```

### StateGraph Integration

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

# Pass Pydantic model directly
builder = StateGraph(CoordinatorState)
builder.add_node("route_request", router_node.invoke)
builder.add_edge(START, "route_request")
# ...

graph = builder.compile(checkpointer=MemorySaver())
```

## Before/After Comparison

### Before (TypedDict)

```python
# states.py
from typing import Literal, TypedDict

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

### After (Pydantic)

```python
# states.py
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

class CoordinatorState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: Literal["cli"] | None = None
    user_input: str | None = None
    route: Literal["docker"] | None = None
    docker_request: str | None = None
    docker_response: str | None = None
    final_response: str | None = None
    thread_id: str | None = None
    error: str | None = None

class DockerWorkerState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: str | None = None
    response: str | None = None
    thread_id: str | None = None
    error: str | None = None
```

## Common Pitfalls

| Pitfall | Issue | Solution |
|---------|-------|----------|
| **Mutable defaults** | Shared state between instances | Use `Field(default_factory=list)` |
| **State mutation** | LangGraph expects return updates | Return new model with updates, don't mutate |
| **Missing defaults** | `str \| None` still required | Add `= None` for optional fields |
| **Serialization** | Non-deterministic caching | Use `model_dump_json()` for stable output |
| **Extra fields** | LangGraph may add internal fields | Use `extra="allow"` if needed |

## Security Considerations

- **Input validation:** Pydantic validates on construction - catches malformed state early
- **Type coercion:** Use `strict=True` in ConfigDict to prevent coercion (e.g., `"1"` → `1`)
- **Field constraints:** Use `Field(ge=0, le=100)` for value bounds

## Testing Approach

### Unit Tests for State Models

```python
import pytest
from pydantic import ValidationError

def test_coordinator_state_valid():
    state = CoordinatorState(user_input="list containers")
    assert state.user_input == "list containers"
    assert state.route is None

def test_coordinator_state_extra_field_forbidden():
    with pytest.raises(ValidationError) as exc:
        CoordinatorState(user_input="test", unknown_field="value")
    assert "Extra inputs are not permitted" in str(exc.value)

def test_docker_worker_state_defaults():
    state = DockerWorkerState()
    assert state.request is None
    assert state.response is None
```

### Integration Tests

```python
def test_graph_with_pydantic_state():
    runtime = DockerGraphRuntime.create()
    result = runtime.run_turn("list containers", thread_id="test-1")
    assert result  # Non-empty response
```

## Performance Notes

| Metric | TypedDict | Pydantic |
|--------|-----------|----------|
| Validation | None | ~0.1ms per transition |
| Serialization | Manual | `.model_dump()` built-in |
| Memory | Minimal | Slightly higher (validators) |

**Verdict:** Overhead negligible compared to LLM/tool latency.

## Recommended Stack

| Purpose | Package | Why |
|---------|---------|-----|
| State models | `pydantic` v2 | Runtime validation, serialization |
| Config | `ConfigDict` | Modern Pydantic v2 config |
| Defaults | `Field(default_factory=...)` | Safe mutable defaults |
| Testing | `pytest` + `ValidationError` | Standard testing pattern |

## References

- [Pydantic v2 Docs](https://docs.pydantic.dev/latest/)
- [LangGraph State Guide](https://langchain-ai.github.io/langgraph/concepts/state/)
- [LangGraph StateGraph](https://langchain-ai.github.io/langgraph/reference/graphs/#stategraph)

---

## Raw Gemini Response

<details>
<summary>Full response</summary>

Key points from Gemini research:

1. **Migration Strategy**
   - Gradual phased approach recommended
   - Start with new components, then refactor existing
   - Hybrid interim: validate TypedDict at entry points

2. **Handling `total=False`**
   - No direct equivalent in Pydantic
   - Must explicitly add `= None` for truly optional fields
   - `Type | None` means required but None is valid value

3. **LangGraph Compatibility**
   - StateGraph accepts BaseModel directly as `state_schema`
   - Checkpointers handle Pydantic serialization
   - Nodes should return updates, not mutate state

4. **Best Practices**
   - Use `extra='forbid'` for strict state
   - Use `validate_assignment=True` for re-validation
   - Use `Field(default_factory=...)` for mutable defaults

5. **Common Pitfalls**
   - Direct state mutation (LangGraph expects return updates)
   - Mutable defaults without `default_factory`
   - Non-deterministic serialization for caching

6. **Testing**
   - Unit test Pydantic models directly
   - Test ValidationError for invalid data
   - Mock LLMs and tools for integration tests

</details>
