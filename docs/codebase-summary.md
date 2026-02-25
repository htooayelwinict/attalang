# Codebase Summary

## Directory Structure

```
src/
├── multi_agent/                 # V1: LangChain DeepAgents + LangGraph
│   ├── agents/
│   │   └── docker_agent.py      # Single agent with HITL
│   ├── runtime/
│   │   ├── cli.py               # Click CLI entrypoint
│   │   ├── runtime.py           # DockerGraphRuntime + StateGraph
│   │   ├── nodes.py             # 3 nodes: Worker, Coordinator, Finalize
│   │   ├── states.py            # CoordinatorState, DockerWorkerState
│   │   └── verbose_callback.py  # VerboseCallback for tool output
│   ├── trajectory/              # Trajectory tracking + loop detection
│   │   ├── collector.py         # TrajectoryCollector
│   │   ├── models.py            # Pydantic models
│   │   └── summary.py           # Summary generation
│   ├── tools/
│   │   └── docker_tools.py      # Docker SDK wrappers (40+ tools)
│   └── utils/
│       └── llm.py               # OpenRouter LLM factory
│
├── multi_agent_v2/              # V2: Pydantic-DeepAgents
│   ├── agents/
│   │   └── docker_agent_v2.py   # Single agent with prefixed tools
│   ├── runtime/
│   │   ├── cli_v2.py            # Click CLI (with -v flag)
│   │   └── runtime_v2.py        # DockerRuntimeV2
│   └── tools/
│       └── docker_tools_v2.py   # Tools + planning + port parsing
│
├── multi_agent_v3/              # V3: Programmatic (code execution)
│   ├── agents/
│   │   └── programmatic_docker_agent.py  # Agent that writes Python code
│   ├── runtime/
│   │   ├── cli_v3.py            # CLI with trajectory tracking
│   │   └── runtime_v3.py        # ProgrammaticDockerRuntime
│   └── tools/
│       ├── bridge.py            # ProgrammaticToolBridge
│       └── executor.py          # Restricted Python executor
│
└── skills/
    ├── docker-management/       # V1 skill definitions
    │   └── SKILL.md
    └── docker-management-v2/    # V2 skill definitions
        └── SKILL.md

tests/                           # 9 test files
├── test_docker_agent_v2.py
├── test_docker_tools_workspace.py
├── test_docker_tools_v2_workspace.py
├── test_docker_bash.py
├── test_langgraph_runtime.py
├── test_runtime_v2.py
├── test_programmatic_v3.py      # V3 programmatic agent tests
└── test_trajectory.py           # Trajectory + loop detection tests
```

## Key Files

| File | Purpose |
|------|---------|
| `src/multi_agent/agents/docker_agent.py` | V1 single agent (LangChain + HITL) |
| `src/multi_agent/runtime/runtime.py` | V1 DockerGraphRuntime + StateGraph |
| `src/multi_agent/runtime/nodes.py` | V1 graph nodes (Worker, Coordinator, Finalize) |
| `src/multi_agent/runtime/states.py` | V1 state models |
| `src/multi_agent/runtime/verbose_callback.py` | VerboseCallback for tool output |
| `src/multi_agent/trajectory/collector.py` | TrajectoryCollector + loop detection |
| `src/multi_agent_v2/agents/docker_agent_v2.py` | V2 single agent (Pydantic) |
| `src/multi_agent_v3/agents/programmatic_docker_agent.py` | V3 programmatic agent (code execution) |
| `src/multi_agent/tools/docker_tools.py` | V1 Docker SDK wrappers |
| `src/multi_agent_v2/tools/docker_tools_v2.py` | V2 tools + planning |
| `src/multi_agent_v3/tools/executor.py` | V3 restricted Python executor |
| `src/multi_agent/runtime/cli.py` | V1 CLI entrypoint |
| `src/multi_agent_v2/runtime/cli_v2.py` | V2 CLI with verbose |
| `src/multi_agent_v3/runtime/cli_v3.py` | V3 CLI with trajectory tracking |
| `pyproject.toml` | Project config + dependencies |

## Agent Comparison

| Aspect | V1 (LangChain) | V2 (Pydantic) | V3 (Programmatic) |
|--------|----------------|---------------|-------------------|
| Architecture | LangGraph StateGraph | Single agent | Code execution |
| Tool calling | Direct (N round-trips) | Prefixed (N round-trips) | **1 Python script** |
| Tool prefix | None | `docker_` | N/A (functions) |
| Planning | Built-in todos | docker_create_plan | Built-in (in code) |
| Verbose mode | VerboseCallback | -v flag | -v flag |
| State | MemorySaver | Thread deps | MemorySaver |
| HITL Security | ✅ interrupt_on + auto-reject | ❌ | ⚠️ Shell operator block |
| Token efficiency | Normal | Normal | **High** |
| Loop detection | ❌ | ❌ | ✅ |
| Trajectory | Optional | ❌ | Built-in |

## CLI Commands

```bash
# V1 (LangGraph) - with HITL security
multi-agent-cli                    # Interactive
multi-agent-cli --hitl             # Interactive + security prompts
multi-agent-cli --prompt "..."     # Single-shot

# V2 (Pydantic)
multi-agent-cli-v2                 # Interactive
multi-agent-cli-v2 -v              # Verbose (shows tool calls)
multi-agent-cli-v2 --prompt "..."  # Single-shot

# V3 (Programmatic) - token efficient
multi-agent-cli-v3                 # Interactive
multi-agent-cli-v3 -v              # Verbose + trajectory tracking
multi-agent-cli-v3 --prompt "..."  # Single-shot
```

## Tool Prefixes (V2)

All V2 tools are prefixed with `docker_`:
- `docker_list_containers`
- `docker_run_container`
- `docker_create_plan`
- etc.
