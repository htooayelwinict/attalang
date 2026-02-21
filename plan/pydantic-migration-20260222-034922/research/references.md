# References

## Documentation

### Pydantic v2
- [Pydantic Docs](https://docs.pydantic.dev/latest/)
- [ConfigDict](https://docs.pydantic.dev/latest/api/config/)
- [Field](https://docs.pydantic.dev/latest/api/fields/)
- [Validation](https://docs.pydantic.dev/latest/concepts/validators/)

### LangGraph
- [StateGraph](https://langchain-ai.github.io/langgraph/reference/graphs/#stategraph)
- [State Concepts](https://langchain-ai.github.io/langgraph/concepts/state/)
- [Checkpointers](https://langchain-ai.github.io/langgraph/concepts/persistence/)

## Code Examples

### Pydantic State Model

```python
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
```

### Node with Pydantic State

```python
from dataclasses import dataclass

@dataclass
class RouterNode:
    def invoke(self, state: CoordinatorState) -> dict:
        user_input = (state.user_input or "").strip()
        if not user_input:
            return {
                "route": "docker",
                "error": "Empty input.",
                "final_response": "Empty input.",
            }
        return {
            "route": "docker",
            "docker_request": user_input,
        }
```

### Runtime with Pydantic

```python
# StateGraph accepts BaseModel directly
builder = StateGraph(CoordinatorState)

# Invoke with model instance or dict
initial_state = CoordinatorState(origin="cli", user_input="list", thread_id="t1")
result = graph.invoke(initial_state, config=config)

# Access result
response = result.final_response or ""
```

## Best Practices

1. **Return dicts from nodes** - LangGraph merges updates
2. **Use `or default` for optional access** - Cleaner than `.get()`
3. **Add `extra="forbid"`** - Catch typos early
4. **Use `Field(default_factory=...)`** - For mutable defaults (lists, dicts)
5. **Keep @dataclass for nodes** - Works well with Pydantic state

## Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| `str \| None` still required | Add `= None` for truly optional |
| Shared mutable defaults | Use `Field(default_factory=list)` |
| State mutation | Return updates, don't mutate |
| Type coercion | Add `strict=True` to ConfigDict |
