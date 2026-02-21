# Phase 4: Update and Add Tests

## Objective

Update existing tests for Pydantic compatibility and add validation tests.

## Prerequisites

- Phase 1-3 completed
- All previous tests passing

## Tasks

- [ ] Update test assertions (if needed)
  - Most tests use dict access on results, may need attribute access
  - Files: `tests/test_langgraph_runtime.py`

- [ ] Add Pydantic validation test
  ```python
  from pydantic import ValidationError

  def test_coordinator_state_validates_types():
      """Pydantic validates field types."""
      state = CoordinatorState(user_input="test")
      assert state.user_input == "test"

  def test_coordinator_state_rejects_extra_fields():
      """extra='forbid' rejects unknown fields."""
      with pytest.raises(ValidationError):
          CoordinatorState(user_input="test", unknown_field="value")
  ```
  - Files: `tests/test_langgraph_runtime.py`

- [ ] Add optional field test
  ```python
  def test_state_optional_fields_default_to_none():
      """All fields are optional with None default."""
      state = CoordinatorState()
      assert state.origin is None
      assert state.user_input is None
      assert state.route is None
  ```
  - Files: `tests/test_langgraph_runtime.py`

- [ ] Add model_dump serialization test
  ```python
  def test_state_serializes_to_dict():
      """model_dump() returns dict for serialization."""
      state = CoordinatorState(user_input="test", route="docker")
      data = state.model_dump()
      assert data["user_input"] == "test"
      assert data["route"] == "docker"
  ```
  - Files: `tests/test_langgraph_runtime.py`

## Verification

```bash
.venv/bin/python -m pytest tests/test_langgraph_runtime.py -v

# All tests should pass
.venv/bin/python -m pytest tests/ -v
```

## Deliverables

- [ ] Existing tests updated and passing
- [ ] Validation tests added
- [ ] Optional field tests added
- [ ] Serialization tests added

## Notes

- Keep existing tests working (regression protection)
- Add new tests for Pydantic-specific behavior
- Test `extra="forbid"` behavior
