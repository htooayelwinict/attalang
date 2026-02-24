# System Architecture

## Overview

AttaLang provides two parallel single-agent implementations for Docker management with Human-in-the-Loop (HITL) security controls:

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
│  DeepAgents + HITL      │     │                         │
│                         │     │                         │
│  ┌─────────────────┐    │     │  ┌─────────────────┐   │
│  │ DockerAgent     │    │     │  │ DockerAgentV2   │   │
│  │ (Single Agent)  │    │     │  │ (Single Agent)  │   │
│  │ + interrupt_on  │    │     │  │                 │   │
│  └────────┬────────┘    │     │  └────────┬────────┘   │
│           │             │     │           │            │
│           ▼             │     │           ▼            │
│  ┌─────────────────┐    │     │  ┌─────────────────┐   │
│  │ ALL_DOCKER_TOOLS│    │     │  │ PrefixedToolset │   │
│  │ + HITL checks   │    │     │  │ (docker_*)      │   │
│  └────────┬────────┘    │     │  └────────┬────────┘   │
│           │             │     │           │            │
│           ▼             │     │           ▼            │
│  ┌─────────────────┐    │     │  ┌─────────────────┐   │
│  │ Docker SDK      │    │     │  │ Docker SDK      │   │
│  └─────────────────┘    │     │  └─────────────────┘   │
└─────────────────────────┘     └─────────────────────────┘
```

## V1 Architecture (LangChain DeepAgents)

### Request Flow with HITL
```
User Prompt → CLI (--hitl) → DockerGraphRuntime → DockerAgent
                                            ↓
                                   Parse prompt with LLM
                                            ↓
                                   Select tool from ALL_DOCKER_TOOLS
                                            ↓
                              ┌─────────────┴─────────────┐
                              │                           │
                        Safe Tool                  Dangerous Tool
                              │                           │
                              ▼                           ▼
                        Execute                 __interrupt__ triggered
                              │                           │
                              │                    ┌──────┴──────┐
                              │                    │             │
                              │               Auto-reject   Prompt user
                              │                    │             │
                              │                    ▼             ▼
                              │              "🚫 BLOCKED"   "⚠️ Approve?"
                              │                    │             │
                              │               reject         approve/reject
                              │                    │             │
                              └────────────────────┴──────┬──────┘
                                                        │
                                                        ▼
                                              Return result via MemorySaver
```

### Graph Flow
```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                    LangGraph StateGraph Flow                    │
                    └─────────────────────────────────────────────────────────────────┘

     START
       │
       │ _route_from_start() [error check]
       │
       ├─── error ──────────────────────────────────────┐
       │                                               │
       │ (no error)                                     ▼
       ▼                                    ┌──────────────────────┐
 ┌─────────────────────┐                     │  finalize_response   │
 │   docker_v1_node    │  (CoordinatorDockerNode)  │  (FinalizeNode)      │
 │  - Execute task     │  → DockerWorkerNode    │  - Return response   │
 │  - Call Docker SDK  │                        └──────────┬───────────┘
 └────────┬────────────┘                                   │
          │                                                │
          │ (always)                                       │
          └────────────────────────────────────────────────┤
                                                          ▼
                                                       END
```

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| `DockerAgent` | `agents/docker_agent.py` | Agent with HITL support |
| `DockerGraphRuntime` | `runtime/runtime.py` | LangGraph runtime wrapper |
| `DockerWorkerNode` | `runtime/nodes.py` | Invokes Docker agent |
| `CoordinatorDockerNode` | `runtime/nodes.py` | Coordinates state flow |
| `FinalizeNode` | `runtime/nodes.py` | Returns final response |
| `docker_tools.py` | `tools/docker_tools.py` | 40+ Docker SDK wrappers |
| `VerboseCallback` | `runtime/verbose_callback.py` | Real-time tool output |
| `create_openrouter_llm` | `utils/llm.py` | OpenRouter LLM factory |
| `MemorySaver` | langgraph | Checkpointer for state |
| `TrajectoryCollector` | `trajectory/collector.py` | Optional trajectory tracking |

### HITL Configuration

```python
# Tools requiring user approval
DANGEROUS_TOOLS = ("remove_image", "prune_images")

# Tools auto-rejected (no user prompt)
AUTO_REJECT_TOOLS = ("remove_volume", "prune_volumes", "docker_system_prune")

# interrupt_on config
interrupt_on = {
    "remove_image": {"allowed_decisions": ["approve", "reject"]},
    "remove_volume": {"allowed_decisions": ["reject"]},  # Auto-reject only
}
```

### Agent Building with HITL
```python
backend = FilesystemBackend(root_dir=str(workspace))
checkpointer = MemorySaver()

# Configure interrupts
interrupt_on = {
    tool: {"allowed_decisions": ["approve", "reject"]}
    for tool in DANGEROUS_TOOLS
}
for tool in AUTO_REJECT_TOOLS:
    interrupt_on[tool] = {"allowed_decisions": ["reject"]}

agent = create_deep_agent(
    model=model,
    tools=ALL_DOCKER_TOOLS,
    system_prompt=instructions,
    skills=[skills_dir],
    backend=backend,
    checkpointer=checkpointer,
    interrupt_on=interrupt_on,  # Enable HITL
)
```

### Simplified Graph Flow (2025-02-24)

The V1 runtime was simplified to remove loop detection and replan logic:

**Removed:**
- `RouterNode` (input parsing moved to `run_turn()`)
- Loop detection and `DockerLoopException`
- Replan attempts and trajectory callback

**Current Flow:**
```
START → docker_v1_node → finalize_response → END
```

**State Transformation:**
```
CoordinatorState               DockerWorkerState
├── user_input          →      ├── request (from docker_request)
├── docker_request      →      ├── thread_id
├── docker_response     ←      ├── response
├── final_response      ←      └── error
├── error               ←
└── thread_id           ─────────────────────────────────▶
```

### HITL Interrupt Handling

```python
def invoke(self, message: str, thread_id: str | None = None) -> str:
    result = self._agent.invoke(...)

    while result.get("__interrupt__"):
        decisions = []
        for action in action_requests:
            tool_name = action.get("name")

            if tool_name in self._auto_reject_tools:
                # Auto-reject without prompting
                decisions.append({"type": "reject", "message": "Blocked"})
            else:
                # Prompt user
                response = input("Approve? [y/n]: ")
                decisions.append({"type": "approve" if response == "y" else "reject"})

        result = self._agent.invoke(Command(resume={"decisions": decisions}))

    return self._extract_text(result)
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
| Architecture | Single agent + HITL | Single agent |
| Tool access | Direct list | Prefixed toolset |
| Tool prefix | None | `docker_` |
| Planning | Built-in todos | docker_create_plan |
| Verbose mode | LangSmith tracing | -v flag |
| HITL Security | ✅ interrupt_on + auto-reject | ❌ Not implemented |
| State | MemorySaver | Thread deps |
| Dependencies | langchain, langgraph | pydantic-deep |

## Security (V1 HITL)

### Tool Categories

| Category | Tools | Behavior |
|----------|-------|----------|
| Safe | list_*, inspect_*, stats, logs | Execute directly |
| Dangerous | remove_image, prune_images | Prompt user: "⚠️ Approve?" |
| Blocked | remove_volume, prune_*, system_prune | Auto-reject: "🚫 BLOCKED" |

### Usage
```bash
# Enable HITL security
multi-agent-cli --hitl

# Safe operation - executes directly
"list all containers"

# Dangerous - prompts for approval
"remove the nginx image"
⚠️  DANGEROUS OPERATION: remove_image
   Arguments: {'image': 'nginx'}
Approve? [y/n]:

# Blocked - auto-rejected
"remove the app-data volume"
🚫 BLOCKED: remove_volume - {'name': 'app-data'}
```

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
