# Pydantic-DeepAgents Research

## Overview

**Pydantic-DeepAgents** (package: `pydantic-deep`) is a lightweight, production-grade agent framework built on [pydantic-ai](https://github.com/pydantic/pydantic-ai). Inspired by LangChain's deepagents, it emphasizes type safety, minimal dependencies, and built-in Docker sandbox support.

- **GitHub**: https://github.com/vstorm-co/pydantic-deepagents
- **PyPI**: `pip install pydantic-deep`
- **Docs**: https://vstorm-co.github.io/pydantic-deepagents/
- **License**: MIT

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Planning** | TodoToolset for task decomposition, tracking, and self-correction |
| **Filesystem** | Full read/write/edit/glob/grep via FilesystemToolset |
| **Subagents** | Context-isolated task delegation via SubAgentToolset |
| **Skills** | Modular capability packages defined in Markdown |
| **Backends** | StateBackend (memory), FilesystemBackend, DockerSandbox, CompositeBackend |
| **Structured Output** | Type-safe responses via Pydantic models (`output_type`) |
| **Context Management** | Auto-summarization for long conversations |
| **HITL** | Human-in-the-loop approval workflows |
| **Streaming** | Token-level streaming support |
| **File Uploads** | `run_with_files()` or `deps.upload_file()` |

---

## Architecture

```
pydantic_deep/
├── __init__.py
├── agent.py           # create_deep_agent factory
├── deps.py            # DeepAgentDeps, create_default_deps
├── processors/
│   └── summarization.py
├── toolsets/
│   ├── filesystem.py  # FilesystemToolset
│   ├── skills.py      # SkillsToolset
│   └── subagents.py   # SubAgentToolset
└── types.py
```

### Modular Components

| Component | Package | Purpose |
|-----------|---------|---------|
| Backends | [pydantic-ai-backend](https://github.com/vstorm-co/pydantic-ai-backend) | File storage, Docker sandbox |
| Todo | [pydantic-ai-todo](https://github.com/vstorm-co/pydantic-ai-todo) | Task planning |
| Summarization | Built-in | Context management (migrating to pydantic-ai core) |

---

## Installation

```bash
pip install pydantic-deep

# Optional: Docker sandbox
pip install pydantic-deep[sandbox]
```

---

## Quick Start

```python
import asyncio
from pydantic_deep import create_deep_agent, create_default_deps
from pydantic_ai_backends import StateBackend

async def main():
    agent = create_deep_agent(
        model="openai:gpt-4.1",
        instructions="You are a helpful coding assistant.",
        include_todo=True,
        include_filesystem=True,
        include_subagents=True,
        include_skills=True,
    )
    
    deps = create_default_deps(StateBackend())
    result = await agent.run("Create a calculator module", deps=deps)
    print(result.output)

asyncio.run(main())
```

---

## Core Concepts

### 1. Backends

```python
from pydantic_ai_backends import StateBackend, FilesystemBackend, DockerSandbox, CompositeBackend

# In-memory
backend = StateBackend()

# Local filesystem
backend = FilesystemBackend(root_dir="./workspace", virtual_mode=True)

# Docker sandbox (isolated execution)
backend = DockerSandbox()

# Composite (layered)
backend = CompositeBackend([
    FilesystemBackend(root_dir="./readonly", read_only=True),
    DockerSandbox(),
])
```

### 2. Toolsets

```python
agent = create_deep_agent(
    include_todo=True,        # TodoToolset
    include_filesystem=True,  # FilesystemToolset
    include_subagents=True,   # SubAgentToolset
    include_skills=True,      # SkillsToolset
)
```

### 3. Structured Output

```python
from pydantic import BaseModel

class TaskAnalysis(BaseModel):
    summary: str
    priority: str
    estimated_hours: float

agent = create_deep_agent(output_type=TaskAnalysis)
result = await agent.run("Analyze: implement user auth", deps=deps)
print(result.output.priority)  # Type-safe
```

### 4. Subagents

```python
from pydantic_deep import SubAgentConfig

subagents = [
    SubAgentConfig(
        name="code-reviewer",
        instructions="Review code for quality and security...",
    ),
    SubAgentConfig(
        name="test-generator",
        instructions="Generate comprehensive tests...",
    ),
]

agent = create_deep_agent(subagents=subagents)
```

### 5. Skills (Markdown-defined)

```
skills/
├── code-review/
│   └── skill.md       # Instructions in Markdown
└── test-generator/
    └── skill.md
```

```python
agent = create_deep_agent(
    include_skills=True,
    skill_directories=[{"path": "./skills", "recursive": True}]
)
```

### 6. Context Management

```python
from pydantic_deep.processors import create_summarization_processor

processor = create_summarization_processor(
    trigger=("tokens", 100000),  # or ("messages", 50) or ("fraction", 0.8)
    keep=("messages", 20),
)

agent = create_deep_agent(history_processors=[processor])
```

### 7. File Uploads

```python
# Method 1: run_with_files
from pydantic_deep import run_with_files

result = await run_with_files(
    agent, "Analyze this data", deps,
    files=[("data.csv", file_bytes)]
)

# Method 2: deps.upload_file
deps.upload_file("config.json", b'{"key": "value"}')
```

---

## Comparison: Pydantic-DeepAgents vs LangChain DeepAgents

| Aspect | Pydantic-DeepAgents | LangChain DeepAgents |
|--------|---------------------|----------------------|
| Base Framework | pydantic-ai | LangGraph + LangChain |
| Dependencies | Minimal | Heavy (LangGraph ecosystem) |
| Type Safety | Native Pydantic | Requires extra setup |
| Sandbox | Built-in Docker | Manual configuration |
| Learning Curve | Lower | Steeper |
| Complexity | Simplified | Full-featured |

---

## Use Cases

1. **Deep Research** - Multi-step web search, doc reading, report generation
2. **Coding Assistants** - Code generation, refactoring, testing (like Claude Code)
3. **Data Analysis** - SQL queries, data pipelines, visualization
4. **DevOps Automation** - File operations, shell commands, server management
5. **Complex Workflows** - Multi-agent collaboration (PM → Dev → QA)

---

## API Reference Summary

### `create_deep_agent()`

```python
def create_deep_agent(
    model: str = "openai:gpt-4.1",
    instructions: str = "",
    output_type: type[BaseModel] | None = None,
    include_todo: bool = True,
    include_filesystem: bool = True,
    include_subagents: bool = True,
    include_skills: bool = True,
    include_execute: bool = False,
    subagents: list[SubAgentConfig] | None = None,
    skills: list[Skill] | None = None,
    skill_directories: list[SkillDirectory] | None = None,
    interrupt_on: dict[str, bool] | None = None,
    history_processors: list[HistoryProcessor] | None = None,
) -> Agent
```

### `create_default_deps()`

```python
def create_default_deps(
    backend: Backend | None = None,
) -> DeepAgentDeps
```

### `DeepAgentDeps`

```python
class DeepAgentDeps:
    backend: Backend
    files: dict[str, dict]
    
    def upload_file(self, path: str, content: bytes) -> None: ...
```

---

## Related Projects

- [pydantic-ai](https://github.com/pydantic/pydantic-ai) - Foundation framework
- [pydantic-ai-backend](https://github.com/vstorm-co/pydantic-ai-backend) - Storage backends
- [pydantic-ai-todo](https://github.com/vstorm-co/pydantic-ai-todo) - Todo toolset
- [fastapi-fullstack](https://github.com/vstorm-co/full-stack-fastapi-nextjs-llm-template) - Full-stack template

---

## LangChain DeepAgents (Original Inspiration)

- **GitHub**: https://github.com/langchain-ai/deepagents
- **Package**: `pip install deepagents`
- **Base**: LangGraph + LangChain

### Key Features

1. **Planning Tools** - `write_todos` for task decomposition
2. **Virtual Filesystem** - In-memory file operations via State
3. **Subagents** - Context-isolated task delegation
4. **Deep Prompts** - Detailed system instructions
5. **CLI** - `deepagents-cli` for terminal-based coding assistant

### Example (LangChain)

```python
from deepagents import create_deep_agent

research_subagent = {
    "name": "research-agent",
    "description": "Conducts web research",
    "system_prompt": "You are a great researcher",
    "tools": [internet_search],
    "model": "openai:gpt-4o",
}

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-20250514",
    subagents=[research_subagent],
    memory=["./AGENTS.md"],      # Persistent context
    skills=["./skills/"],        # Skill directories
)
```

### LangChain DeepAgents CLI

```bash
pip install deepagents-cli

# Set API keys
export ANTHROPIC_API_KEY=your_key
export TAVILY_API_KEY=your_key

# Run
deepagents

# With specific agent
deepagents --agent backend-dev

# Reset agent
deepagents --reset backend-dev
```

---

## Key Insights for G-4 Project

1. **Modular design** - Extracted components (backend, todo) are reusable independently
2. **Type safety** - Native Pydantic integration matches G-4 patterns
3. **Virtual filesystem** - `FilesystemBackend(virtual_mode=True)` prevents path traversal
4. **Skills as Markdown** - Simple extensibility pattern (consider for G-4)
5. **Summarization processor** - Similar to G-4's context management needs
6. **DockerSandbox** - Secure code execution (relevant for Froq project)
