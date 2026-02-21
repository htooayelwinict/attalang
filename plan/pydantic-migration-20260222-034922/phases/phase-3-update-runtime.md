# Phase 3: Update runtime.py Invocation

## Objective

Update runtime to use Pydantic model instantiation and attribute access.

## Prerequisites

- Phase 1 completed (states converted to Pydantic)
- Phase 2 completed (nodes updated)

## Tasks

- [ ] Update _route_after_router
  ```python
  # Before
  if state.get("error"):
      return "finalize_response"
  if state.get("route") == "docker":
      return "run_docker"

  # After
  if state.error:
      return "finalize_response"
  if state.route == "docker":
      return "run_docker"
  ```
  - Files: `src/multi_agent/runtime/runtime.py`

- [ ] Update run_turn initial state
  ```python
  # Before
  initial_state: CoordinatorState = {
      "origin": "cli",
      "user_input": user_input,
      "thread_id": thread_id,
  }

  # After
  initial_state = CoordinatorState(
      origin="cli",
      user_input=user_input,
      thread_id=thread_id,
  )
  ```
  - Files: `src/multi_agent/runtime/runtime.py`

- [ ] Update run_turn result access
  ```python
  # Before
  return result.get("final_response", "")

  # After
  return result.final_response or ""
  ```
  - Files: `src/multi_agent/runtime/runtime.py`

## Verification

```bash
.venv/bin/python -m pytest tests/test_langgraph_runtime.py -v
```

## Deliverables

- [ ] Initial state uses model instantiation
- [ ] Result uses attribute access
- [ ] Router uses attribute access

## Notes

- StateGraph accepts BaseModel directly (no changes to `_build_graph`)
- Can pass model instance or dict to `graph.invoke()`
- MemorySaver handles Pydantic serialization
