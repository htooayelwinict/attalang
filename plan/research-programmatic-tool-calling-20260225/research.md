# Research: Programmatic Tool Calling for V1 Docker Agent

**Date:** 2026-02-25
**Query:** How to implement Claude-style programmatic tool calling on top of existing LangGraph V1 Docker agent

## Summary

Programmatic tool calling allows agents to write Python code that calls tools directly, rather than requiring LLM round-trips for each tool invocation. This reduces latency, saves tokens, and enables complex workflows (loops, filters, conditionals) without model sampling.

## Key Concepts

### Traditional vs Programmatic Tool Calling

| Aspect | Traditional (Current V1) | Programmatic |
|--------|--------------------------|--------------|
| Tool invocation | LLM outputs tool call | Agent writes Python code |
| Round-trips | N tools = N LLM calls | N tools = 1 LLM call |
| Context | All tool results in context | Only final output in context |
| Logic | Requires LLM reasoning | Pure Python (loops, filters) |

### How Claude's `code_execution_20260120` Works

1. Claude writes Python code (not tool calls)
2. Code runs in sandboxed container
3. Tools become callable async functions inside sandbox
4. Tool calls pause execution, return to host
5. Host executes tool, injects result back
6. Only final stdout goes to Claude's context

## Python Sandbox Options

| Option | Security | Latency | Complexity | Recommendation |
|--------|----------|---------|------------|----------------|
| **Docker Container** | High | Medium (warm pools help) | Medium | ✅ Best for Docker agent |
| RestrictedPython | Low | Very Low | Low | ❌ Security risks |
| Pyodide (Wasm) | Medium | Low | High | ❌ Limited OS access |
| Custom (chroot/seccomp) | Variable | Low | Very High | ❌ Too complex |

**Recommendation:** Docker containerization - aligns with existing infrastructure, strong isolation.

## Tool-to-Async-Function Bridge Pattern

Convert LangChain `@tool` decorated functions to callable async functions:

```python
class ProgrammaticToolBridge:
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._tool_schemas: Dict[str, Type[BaseModel]] = {}

    def register_tool(self, tool_func: Callable, args_schema: Type[BaseModel] = None):
        tool_name = tool_func.__name__
        self._tools[tool_name] = tool_func
        self._tool_schemas[tool_name] = args_schema

    async def call_tool_async(self, tool_name: str, **kwargs) -> Any:
        tool_func = self._tools[tool_name]
        args_schema = self._tool_schemas.get(tool_name)

        # Pydantic validation
        if args_schema:
            model_instance = args_schema(**kwargs)
            validated_kwargs = model_instance.model_dump()

        # Handle sync vs async
        if inspect.iscoroutinefunction(tool_func):
            return await tool_func(**validated_kwargs)
        else:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                self._executor,
                lambda: tool_func(**validated_kwargs)
            )
```

## Implementation Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Main Agent Process (LangGraph)               │
│                                                                 │
│  ┌──────────────┐     ┌────────────────────────────────────┐   │
│  │ Current Mode │     │   NEW: Programmatic Mode           │   │
│  │              │     │                                    │   │
│  │ LLM → Tool   │     │  LLM → code_execution tool         │   │
│  │ → LLM → Tool │     │  → Sandbox runs Python             │   │
│  │ → LLM ...    │     │  → Tools called from code          │   │
│  │              │     │  → Only final output to context    │   │
│  └──────────────┘     └────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Tool Router/Dispatcher (NEW NODE)           │  │
│  │  - Checks if tool is programmatic vs traditional         │  │
│  │  - Routes to sandbox executor or direct tool call        │  │
│  │  - Enforces HITL for dangerous tools                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│                              │ HTTP/gRPC                        │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         Sandbox Executor Service (Docker Container)      │  │
│  │                                                          │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  ProgrammaticToolBridge                            │  │  │
│  │  │  - Tool registry                                   │  │  │
│  │  │  - Pydantic validation                             │  │  │
│  │  │  - Async/sync adaptation                           │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  │                                                          │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  Tool Implementations (docker_tools.py)            │  │  │
│  │  │  - docker_cli, remove_container, etc.              │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## File Structure (After Changes)

```
src/multi_agent/
├── agents/
│   └── docker_agent.py        # MODIFY: add programmatic prompt
├── tools/
│   ├── docker_tools.py        # KEEP: same tools
│   └── code_execution.py      # NEW: code_execution tool
├── runtime/
│   ├── runtime.py             # MODIFY: add sandbox integration
│   ├── nodes.py               # MODIFY: add tool_dispatcher node
│   └── states.py              # KEEP: same states
├── sandbox/                   # NEW DIRECTORY
│   ├── __init__.py
│   ├── executor.py            # NEW: SandboxExecutor class
│   ├── bridge.py              # NEW: ProgrammaticToolBridge
│   └── server.py              # NEW: FastAPI server for sandbox
└── trajectory/
    └── collector.py           # KEEP: still works
```

## Security Considerations

### Sandbox Security
- **Docker isolation**: Run sandbox in separate container
- **Resource limits**: CPU, memory, network constraints
- **Read-only docker.sock**: For inspect-only operations
- **Docker-in-Docker**: For operations requiring container creation

### Input Validation
- **Pydantic schemas**: All tool arguments validated
- **Whitelist commands**: Only SAFE_DOCKER_COMMANDS allowed
- **HITL integration**: Dangerous tools require approval

### Access Control
- **Tool Router**: Enforces BLOCKED_TOOLS per agent type
- **Origin verification**: Only authorized nodes can invoke sandbox
- **Audit logging**: All programmatic calls logged

## Token/Latency Efficiency

### Token Savings
| Scenario | Traditional | Programmatic | Savings |
|----------|-------------|--------------|---------|
| 10 tool calls | ~15,000 tokens | ~3,000 tokens | 80% |
| Filter 100 items | ~50,000 tokens | ~5,000 tokens | 90% |
| Loop 20 iterations | ~30,000 tokens | ~4,000 tokens | 87% |

### Latency Savings
| Scenario | Traditional | Programmatic | Savings |
|----------|-------------|--------------|---------|
| 10 tool calls | 10 LLM round-trips | 2 LLM round-trips | 80% |
| Complex workflow | 5-15 seconds | 2-4 seconds | 60-70% |

## Recommended Approach

### Phase 1: Core Infrastructure
1. Create `SandboxExecutor` class with Docker container management
2. Implement `ProgrammaticToolBridge` for tool-to-function conversion
3. Add `code_execution` tool to agent

### Phase 2: Integration
1. Add `ToolRouterDispatcher` node to LangGraph
2. Update agent prompt for programmatic mode
3. Wire up HITL for dangerous operations

### Phase 3: Optimization
1. Container pooling for reduced latency
2. Streaming execution results
3. Trajectory collection for programmatic calls

## Unresolved Questions

1. Container pooling strategy vs per-request containers?
2. How to handle long-running tool calls in sandbox?
3. Should code_execution tool have its own HITL for complex code?
4. How to surface sandbox errors to LLM for recovery?

## References

- [Claude Programmatic Tool Calling](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling)
- [LangGraph ToolNode](https://github.com/langchain-ai/langgraph/blob/main/libs/prebuilt/README.md)
- [Docker SDK for Python](https://docker-py.readthedocs.io/)

## Raw Gemini Response

<details>
<summary>Full response (truncated for brevity)</summary>

The Gemini response covered:
1. Overview of programmatic tool calling pattern
2. Python sandbox options comparison (Docker, RestrictedPython, Pyodide, Custom)
3. Tool-to-async-function bridge patterns with code examples
4. Implementation architecture for hybrid mode
5. Security considerations (sandbox, input validation, authorization, HITL)
6. Token/latency efficiency analysis

</details>
