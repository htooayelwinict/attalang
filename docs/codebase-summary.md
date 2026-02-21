# Codebase Summary

## Directory Structure

```
src/
├── multi_agent/                 # V1: LangChain DeepAgents
│   ├── agents/
│   │   └── docker_agent.py      # Single agent with direct tools
│   ├── runtime/
│   │   ├── cli.py               # Click CLI entrypoint
│   │   └── runtime.py           # DockerRuntime
│   ├── tools/
│   │   └── docker_tools.py      # Docker SDK wrappers (40 tools)
│   └── utils/
│       ├── llm.py               # OpenRouter LLM factory
│       └── truncate.py          # Output truncation
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
└── skills/
    ├── docker-management/       # V1 skill definitions
    │   └── SKILL.md
    └── docker-management-v2/    # V2 skill definitions
        └── SKILL.md

tests/                           # 6 test files
├── test_docker_agent_subagents.py
├── test_docker_agent_v2.py
├── test_docker_tools_workspace.py
├── test_docker_tools_v2_workspace.py
├── test_langgraph_runtime.py
└── test_runtime_v2.py
```

## Key Files

| File | Purpose |
|------|---------|
| `src/multi_agent/agents/docker_agent.py` | V1 single agent (LangChain) |
| `src/multi_agent_v2/agents/docker_agent_v2.py` | V2 single agent (Pydantic) |
| `src/multi_agent/tools/docker_tools.py` | V1 Docker SDK wrappers |
| `src/multi_agent_v2/tools/docker_tools_v2.py` | V2 tools + planning |
| `src/multi_agent/runtime/cli.py` | V1 CLI entrypoint |
| `src/multi_agent_v2/runtime/cli_v2.py` | V2 CLI with verbose |
| `pyproject.toml` | Project config + dependencies |

## Agent Comparison

| Aspect | V1 (LangChain) | V2 (Pydantic) |
|--------|----------------|---------------|
| Architecture | Single agent | Single agent |
| Tool count | 40+ (direct) | 40+ (prefixed) |
| Tool prefix | None | `docker_` |
| Planning | Built-in todos | docker_create_plan |
| Verbose mode | LangSmith tracing | -v flag |
| State | MemorySaver | Thread deps |

## CLI Commands

```bash
# V1
multi-agent-cli                    # Interactive
multi-agent-cli --prompt "..."     # Single-shot

# V2
multi-agent-cli-v2                 # Interactive
multi-agent-cli-v2 -v              # Verbose (shows tool calls)
multi-agent-cli-v2 --prompt "..."  # Single-shot
```

## Tool Prefixes (V2)

All V2 tools are prefixed with `docker_`:
- `docker_list_containers`
- `docker_run_container`
- `docker_create_plan`
- etc.
