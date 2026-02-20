# Research: DeepAgents Structured Output Support

**Date:** 2026-02-21
**Query:** Does create_deep_agent() support response_format or structured output?
**Context:** DeepAgents 0.4.1 + LangChain

## Executive Summary

YES - `create_deep_agent()` directly supports `response_format` parameter. It accepts three strategies from `langchain.agents.structured_output`: `ToolStrategy`, `ProviderStrategy`, and `AutoStrategy`. Pass a Pydantic model to get typed JSON output.

## Key Findings

### 1. Native Support via `response_format` Parameter

The `create_deep_agent()` function signature includes:

```python
response_format: Union[
    ToolStrategy[SchemaT],
    ProviderStrategy[SchemaT],
    AutoStrategy[SchemaT],
    NoneType
] = None
```

### 2. Three Strategy Options

| Strategy | How It Works | Best For |
|----------|--------------|----------|
| `ToolStrategy` | Uses tool-calling to get structured output | Models with good tool support |
| `ProviderStrategy` | Uses model's native structured output (e.g., OpenAI `response_format`) | OpenAI/Anthropic native support |
| `AutoStrategy` | Auto-selects best strategy for the model | Default choice, most flexible |

### 3. Usage Pattern

```python
from pydantic import BaseModel, Field
from typing import Literal, Any
from deepagents import create_deep_agent
from langchain.agents.structured_output import AutoStrategy

class DockerResponse(BaseModel):
    status: Literal["success", "error"] = Field(description="Operation status")
    data: dict[str, Any] | None = Field(default=None, description="Response data")
    message: str | None = Field(default=None, description="Human-readable message")
    actions: list[str] | None = Field(default=None, description="Actions taken")

agent = create_deep_agent(
    model="openai:gpt-4o",
    system_prompt="You are a Docker operations agent.",
    response_format=AutoStrategy(DockerResponse),  # <-- HERE
)

# Invoke returns structured response
result = agent.invoke({"messages": [{"role": "user", "content": "List containers"}]})
# result contains validated DockerResponse
```

### 4. Strategy Details

**ToolStrategy:**
```python
ToolStrategy(
    schema=MyModel,
    tool_message_content="Optional content for tool message",
    handle_errors=True  # Auto-retry on validation errors
)
```

**ProviderStrategy:**
```python
ProviderStrategy(
    schema=MyModel,
    strict=None  # Set True for strict JSON schema validation
)
```

**AutoStrategy:**
```python
AutoStrategy(schema=MyModel)  # Picks best strategy automatically
```

## Recommended Approach

### For DockerAgent

```python
from langchain.agents.structured_output import AutoStrategy

# In _build_agent():
return create_deep_agent(
    model=self._model,
    tools=self._tools,
    system_prompt=self._instructions,
    subagents=self._subagents,
    backend=backend,
    skills=[SKILLS_VIRTUAL_ROOT] if self._skill_files else None,
    checkpointer=checkpointer,
    response_format=AutoStrategy(DockerResponse),  # <-- ADD THIS
)
```

### Strategy Selection Guide

| Use Case | Recommended Strategy |
|----------|---------------------|
| OpenAI models (gpt-4o, etc.) | `ProviderStrategy` or `AutoStrategy` |
| Anthropic models | `ToolStrategy` or `AutoStrategy` |
| OpenRouter (multiple providers) | `AutoStrategy` (safest choice) |
| Custom/unknown models | `ToolStrategy` (most compatible) |

## Security Considerations

- Schema validation prevents unexpected output structure
- No sensitive data should be in schema definitions
- Handle validation errors gracefully (use `handle_errors=True` in ToolStrategy)

## Performance Considerations

- `ProviderStrategy` is fastest for supported models (native JSON mode)
- `ToolStrategy` adds an extra tool call roundtrip
- Structured output may increase token usage slightly

## References

- `deepagents.graph.create_deep_agent` function signature (verified via `help()`)
- `langchain.agents.structured_output` module (verified via inspection)
- DeepAgents 0.4.1 installed package

## Unresolved Questions

None - the feature exists and is documented in the function signature.

