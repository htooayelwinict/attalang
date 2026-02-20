# AGENTS.md

Guide for agentic coding agents operating in this repository.

---

## Project Overview

Multi-agent orchestration system using LangChain, LangGraph, and DeepAgents. Sample Python projects:
- **Froq**: Docker automation agent
- **bot**: Facebook automation with Playwright, RAG-based learning, Qdrant storage
- **B-31/P-2**: Multi-agent supervisor-bridge-customer architecture with state isolation

---

## Build/Lint/Test Commands

```bash
# Install (CRITICAL: always use .venv)
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# Tests
.venv/bin/python -m pytest tests/                    # All tests
.venv/bin/python -m pytest tests/test_file.py       # Single file
.venv/bin/python -m pytest tests/test_file.py::test_name  # Single test
.venv/bin/python -m pytest tests/ -v --asyncio-mode=auto  # Verbose + async

# Lint/Format/Type
ruff check src/ --fix && ruff format src/ && mypy src/
```

---

## Environment Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[agent,dev,memory]"
.venv/bin/python -m playwright install chromium  # bot project only
```

Required env vars (`.env` or `config/.env`): `OPENROUTER_API_KEY`, `OPENAI_API_KEY`

---

## Code Style

### Imports

```python
import json
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.session import get_current_page
```

### Formatting

- Line length: 100 chars | Python: 3.11+ | Quotes: double | No comments unless requested

### Types

```python
def func(name: str | None) -> list[dict[str, Any]]: ...  # Modern syntax
```

### Naming

| Element | Convention | Example |
|---------|------------|---------|
| Files | snake_case | `facebook_surfer.py` |
| Classes | PascalCase | `FacebookSurferAgent` |
| Functions | snake_case | `create_openrouter_llm` |
| Constants | UPPER_SNAKE_CASE | `BLOCKED_TOOLS` |
| Private | `_prefix` | `_execute` |

### Error Handling

```python
return ToolResult(success=False, content=f"Error: {e}")  # Don't raise
```

---

## Architecture Patterns

### Agent

```python
@dataclass
class MyAgent:
    scope_name: str
    model: BaseChatModel
    agent: Any

    @classmethod
    def create(cls, scope_name: str, model: BaseChatModel, system_prompt: str):
        agent = create_deep_agent(model=model, system_prompt=system_prompt, checkpointer=False)
        return cls(scope_name=scope_name, model=model, agent=agent)
```

### Tool

```python
class MyInputSchema(BaseModel):
    query: str = Field(description="Search query")

registry.register(ToolSpec(
    name="my_tool",
    category=ToolCategory.utilities,
    description="Brief description",
    func=my_func,
    args_schema=MyInputSchema,
))
```

### Shared Utils

```python
from src.agents.utils import create_openrouter_llm, parse_json_with_fallback
llm = create_openrouter_llm(model="openrouter/x-ai/grok-4.1-fast", temperature=0.0)
```

---

## Security

- `GlobalState` holds secrets; `UnsafeState` cannot
- Bridge strips secrets when projecting state
- Read-only nodes: `interrupt_config = {tool: {"allowed_decisions": ["reject"]} for tool in BLOCKED_TOOLS}`
- Path traversal: `FilesystemBackend(root_dir=scope_root, virtual_mode=True)`

---

## Structure

```
sample-srcs/
├── Froq/src/froq/           # Docker agent
├── bot/src/{agents,tools,session,storage,metrics}/
├── B-31/src/agents/         # Multi-agent orchestrator
└── P-2/src/multi_agent_app/ # Runtime patterns
```

---

## Testing

```python
def test_tool_register_spec():
    class DummyArgs(BaseModel):
        name: str

    spec = ToolSpec(name="dummy", category=ToolCategory.interaction, func=lambda x: x, args_schema=DummyArgs)
    registry.register(spec)
    assert "dummy" in registry.list_names()
```

---

## Pitfalls

| Issue | Fix |
|-------|-----|
| Interrupt doesn't resume | Add `MemorySaver()` |
| KeyError 'decisions' | Use `{"decisions": [{"type": "reject", ...}]}` |
| Secrets in UnsafeState | Use separate graphs |
| Path traversal | Use `virtual_mode=True` |
| Import errors | Always use `.venv/bin/python` |
| Click fails | Call `browser_get_snapshot()` after actions |
