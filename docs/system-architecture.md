# System Architecture

## Overview

AttaLang provides two parallel single-agent implementations for Docker management:

```
┌─────────────────────────────────────────────────────────────┐
│                        User Input                            │
│                   (Natural Language)                         │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│  V1: LangChain          │     │    V2: Pydantic-AI      │
│  DeepAgents             │     │                         │
│                         │     │                         │
│  ┌─────────────────┐    │     │  ┌─────────────────┐   │
│  │ DockerAgent     │    │     │  │ DockerAgentV2   │   │
│  │ (Single Agent)  │    │     │  │ (Single Agent)  │   │
│  └────────┬────────┘    │     │  └────────┬────────┘   │
│           │             │     │           │            │
│           ▼             │     │           ▼            │
│  ┌─────────────────┐    │     │  ┌─────────────────┐   │
│  │ ALL_DOCKER_TOOLS│    │     │  │ PrefixedToolset │   │
│  │ (direct access) │    │     │  │ (docker_*)      │   │
│  └────────┬────────┘    │     │  └────────┬────────┘   │
│           │             │     │           │            │
│           ▼             │     │           ▼            │
│  ┌─────────────────┐    │     │  ┌─────────────────┐   │
│  │ Docker SDK      │    │     │  │ Docker SDK      │   │
│  └─────────────────┘    │     │  └─────────────────┘   │
└─────────────────────────┘     └─────────────────────────┘
```

## V1 Architecture (LangChain DeepAgents)

### Request Flow
```
User Prompt → CLI → DockerRuntime → DockerAgent
                                       ↓
                              Parse prompt with LLM
                                       ↓
                              Select tool from ALL_DOCKER_TOOLS
                                       ↓
                              Execute tool directly
                                       ↓
                              Return result via MemorySaver
```

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| `DockerAgent` | `agents/docker_agent.py` | Single agent with direct tools |
| `DockerRuntime` | `runtime/runtime.py` | Runtime wrapper |
| `docker_tools.py` | `tools/docker_tools.py` | 40+ Docker SDK wrappers |
| `create_openrouter_llm` | `utils/llm.py` | OpenRouter LLM factory |
| `MemorySaver` | langgraph | Checkpointer for state |

### Agent Building
```python
backend = FilesystemBackend(root_dir=str(workspace))
checkpointer = MemorySaver()

agent = create_deep_agent(
    model=model,
    tools=ALL_DOCKER_TOOLS,      # Direct tool list
    system_prompt=instructions,
    skills=[skills_dir],
    backend=backend,
    checkpointer=checkpointer,
)
```

## V2 Architecture (Pydantic-DeepAgents)

### Request Flow
```
User Prompt → CLI → DockerRuntimeV2 → DockerAgentV2
                                          ↓
                              Parse prompt with LLM
                                          ↓
                              Select tool from PrefixedToolset
                                          ↓
                              Execute tool with RunContext
                                          ↓
                              Stream result (verbose mode)
```

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| `DockerAgentV2` | `agents/docker_agent_v2.py` | Single agent with prefixed tools |
| `DockerRuntimeV2` | `runtime/runtime_v2.py` | Runtime wrapper + verbose |
| `create_docker_toolset` | `tools/docker_tools_v2.py` | PrefixedToolset factory |
| `docker_create_plan` | `tools/docker_tools_v2.py` | Planning tool |

### Tool Wrapping
```
Raw Function → _wrap_tool_for_context() → FunctionToolset → PrefixedToolset
                      │                        │                   │
                Add RunContext         Group tools        Add "docker_" prefix
```

### Verbose Streaming
```
agent.iter() → UserPromptNode → ModelRequestNode → CallToolsNode → End
                      │                │                  │
                 "Processing..."   "Calling LLM..."   "[Tool] docker_run_container({...})"
```

## Comparison

| Aspect | V1 (LangChain) | V2 (Pydantic) |
|--------|----------------|---------------|
| Architecture | Single agent | Single agent |
| Tool access | Direct list | Prefixed toolset |
| Tool prefix | None | `docker_` |
| Planning | Built-in todos | docker_create_plan |
| Verbose mode | LangSmith tracing | -v flag |
| State | MemorySaver | Thread deps |
| Dependencies | langchain, langgraph | pydantic-deep |

## Data Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│  .env    │────▶│   LLM    │────▶│ Response │
└──────────┘     └──────────┘     └──────────┘
                      │
                      ▼
               ┌──────────┐
               │  Tools   │
               └────┬─────┘
                    │
                    ▼
               ┌──────────┐
               │ Docker   │
               │ Socket   │
               └──────────┘
```

## Threading & State

| Version | State Management |
|---------|-----------------|
| V1 | MemorySaver checkpointer with thread_id |
| V2 | `deps_by_thread` dict per thread_id |

Each thread has isolated workspace and todo state.
