# Plan: Pydantic Migration for V1 Runtime

**Created:** 2026-02-22 03:49
**Status:** Ready for Implementation

## Summary

Migrate V1 LangGraph runtime from TypedDict to Pydantic BaseModel for:
- Runtime validation
- Better serialization with checkpointers
- Consistency with existing LangChain tools (already Pydantic)

## Goals

- [x] Research completed
- [ ] Convert state types to Pydantic BaseModel
- [ ] Update node access patterns
- [ ] Update runtime invocation
- [ ] Add/update tests

## Scope

### In Scope
- `src/multi_agent/runtime/states.py`
- `src/multi_agent/runtime/nodes.py`
- `src/multi_agent/runtime/runtime.py`
- `tests/test_langgraph_runtime.py`

### Out of Scope
- V2 implementation
- Tool definitions (already Pydantic)
- CLI changes

---

## Phase 1: Convert states.py to Pydantic

**Objective:** Convert TypedDict to Pydantic BaseModel

### Tasks

```python
# Before
from typing import Literal, TypedDict

class CoordinatorState(TypedDict, total=False):
    origin: Literal["cli"]
    user_input: str
    route: Literal["docker"]
    # ...

# After
from pydantic import BaseModel, ConfigDict
from typing import Literal

class CoordinatorState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: Literal["cli"] | None = None
    user_input: str | None = None
    route: Literal["docker"] | None = None
    # ...
```

### Verification
```bash
.venv/bin/python -c "from src.multi_agent.runtime.states import CoordinatorState; s = CoordinatorState(user_input='test'); print(s.user_input)"
```

---

## Phase 2: Update nodes.py Access Patterns

**Objective:** Replace `.get()` with attribute access

### Tasks

```python
# Before
user_input = state.get("user_input", "").strip()

# After
user_input = (state.user_input or "").strip()
```

### Key Changes
| Before | After |
|--------|-------|
| `state.get("field", default)` | `state.field or default` |
| `state["field"]` | `state.field` |
| `{"field": value}` (worker state) | `DockerWorkerState(field=value)` |

---

## Phase 3: Update runtime.py Invocation

**Objective:** Use model instantiation and attribute access

### Tasks

```python
# Before
initial_state: CoordinatorState = {
    "origin": "cli",
    "user_input": user_input,
    "thread_id": thread_id,
}
return result.get("final_response", "")

# After
initial_state = CoordinatorState(
    origin="cli",
    user_input=user_input,
    thread_id=thread_id,
)
return result.final_response or ""
```

---

## Phase 4: Update and Add Tests

**Objective:** Ensure tests work + add Pydantic validation tests

### New Tests

```python
def test_coordinator_state_rejects_extra_fields():
    """extra='forbid' rejects unknown fields."""
    with pytest.raises(ValidationError):
        CoordinatorState(user_input="test", unknown_field="value")

def test_state_optional_fields_default_to_none():
    """All fields are optional with None default."""
    state = CoordinatorState()
    assert state.user_input is None

def test_state_serializes_to_dict():
    """model_dump() returns dict."""
    state = CoordinatorState(user_input="test")
    assert state.model_dump()["user_input"] == "test"
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `states.py` | TypedDict → BaseModel, ConfigDict, defaults |
| `nodes.py` | `.get()` → `.field or default` |
| `runtime.py` | Dict init → Model init, attribute access |
| `test_langgraph_runtime.py` | Update + add validation tests |

## Access Pattern Reference

| TypedDict | Pydantic |
|-----------|----------|
| `state.get("field", default)` | `state.field or default` |
| `state["field"]` | `state.field` |
| `return {"field": value}` | `return {"field": value}` (unchanged) |
| `{"field": val}` (construction) | `Model(field=val)` |

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| LangGraph compatibility | Native BaseModel support confirmed |
| State access patterns | Use `state.field or default` |
| Test failures | Incremental migration with verification |

## Verification Commands

```bash
# Phase 1-3 verification
.venv/bin/python -m pytest tests/test_langgraph_runtime.py -v

# Full test suite
.venv/bin/python -m pytest tests/ -v

# Type check
mypy src/multi_agent/runtime/
```

---

## Next Steps

1. Review this plan
2. Run `/code plan/pydantic-migration-20260222-034922` to implement
3. Verify all tests pass after each phase
