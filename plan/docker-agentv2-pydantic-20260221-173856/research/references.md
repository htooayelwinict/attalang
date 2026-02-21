# Research: Pydantic-DeepAgents References

## Official Resources

| Resource | URL |
|----------|-----|
| GitHub | https://github.com/vstorm-co/pydantic-deepagents |
| PyPI | `pip install pydantic-deep` |
| Docs | https://vstorm-co.github.io/pydantic-deepagents/ |
| pydantic-ai | https://github.com/pydantic/pydantic-ai |
| pydantic-ai-backend | https://github.com/vstorm-co/pydantic-ai-backend |

## Key API Patterns

### create_deep_agent
```python
from pydantic_deep import create_deep_agent

agent = create_deep_agent(
    model="openai:gpt-4.1",
    instructions="...",
    include_todo=True,
    include_filesystem=True,
    include_subagents=True,
    include_skills=True,
)
```

### Backends
```python
from pydantic_ai_backends import StateBackend, FilesystemBackend

# In-memory
backend = StateBackend()

# Filesystem with sandbox
backend = FilesystemBackend(root_dir="./ws", virtual_mode=True)
```

### Running Agent
```python
from pydantic_deep import DeepAgentDeps

deps = DeepAgentDeps(backend=backend)
result = await agent.run("task", deps=deps)
print(result.output)
```

### Custom Tools
```python
@agent.tool
def my_tool(ctx, arg: str) -> str:
    """Tool description."""
    return "result"
```

## Differences from LangChain

| Aspect | LangChain | Pydantic |
|--------|-----------|----------|
| Decorator | `@tool` | `@agent.tool` |
| Invoke | `agent.invoke()` | `await agent.run()` |
| State | `MemorySaver()` | `StateBackend()` |
| Context | `config={"thread_id": ...}` | `deps` parameter |
