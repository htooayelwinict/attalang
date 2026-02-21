# Phase 1: Convert states.py to Pydantic

## Objective

Convert TypedDict state definitions to Pydantic BaseModel with proper ConfigDict and defaults.

## Prerequisites

- None (first phase)

## Tasks

- [ ] Add Pydantic imports
  ```python
  from pydantic import BaseModel, ConfigDict
  ```
  - Files: `src/multi_agent/runtime/states.py`

- [ ] Convert CoordinatorState
  ```python
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
  ```
  - Files: `src/multi_agent/runtime/states.py`

- [ ] Convert DockerWorkerState
  ```python
  class DockerWorkerState(BaseModel):
      model_config = ConfigDict(extra="forbid")

      request: str | None = None
      response: str | None = None
      thread_id: str | None = None
      error: str | None = None
  ```
  - Files: `src/multi_agent/runtime/states.py`

- [ ] Remove TypedDict import
  - Files: `src/multi_agent/runtime/states.py`

## Verification

```bash
.venv/bin/python -c "from src.multi_agent.runtime.states import CoordinatorState, DockerWorkerState; print('OK')"

# Verify model behavior
.venv/bin/python -c "
from src.multi_agent.runtime.states import CoordinatorState
s = CoordinatorState(user_input='test')
assert s.user_input == 'test'
assert s.route is None
print('Validation OK')
"
```

## Deliverables

- [ ] `states.py` converted to Pydantic
- [ ] All fields have `= None` defaults
- [ ] `extra="forbid"` configured

## Notes

- All fields optional (were `total=False`)
- `Literal` types preserved
- `ConfigDict(extra="forbid")` catches typos
