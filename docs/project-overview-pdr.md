# Project Overview & PDR

## Project Summary

**AttaLang** is a Docker management agent framework providing two parallel implementations:
- **V1 (LangChain)**: Single agent using LangChain DeepAgents with direct tool access
- **V2 (Pydantic)**: Single agent using Pydantic-DeepAgents with prefixed tools

Both versions provide natural language control over Docker operations including containers, images, networks, volumes, and compose stacks.

## Product Development Requirements (PDR)

### Business Goals
- [x] Natural language Docker management
- [x] Multi-agent architecture comparison (LangGraph vs Pydantic)
- [ ] Production deployment ready
- [ ] Multi-user session support

### User Stories
| ID | As a... | I want to... | So that... |
|----|---------|--------------|------------|
| US-001 | DevOps engineer | Manage containers via natural language | Reduce CLI memorization |
| US-002 | Developer | Deploy multi-tier apps | Quick local development setup |
| US-003 | Admin | Monitor container stats | Track resource usage |

### Features
| Feature | Status | Priority |
|---------|--------|----------|
| Container CRUD | Done | High |
| Image management | Done | High |
| Network management | Done | Medium |
| Volume management | Done | Medium |
| Compose support | Done | Medium |
| Planning/Todo | Done (V2) | High |
| Verbose mode | Done (V2) | Medium |
| LangSmith tracing | V1 only | Low |

### Success Metrics
- Tool call accuracy: 95%+
- Multi-step task completion: 90%+
- Response time: <5s for simple ops

## Tech Stack

| Layer | V1 (LangChain) | V2 (Pydantic) |
|-------|-----------------|---------------|
| Framework | LangChain DeepAgents | Pydantic-DeepAgents |
| LLM | OpenRouter (LangChain) | OpenRouter (Pydantic-AI) |
| Tools | Docker SDK (direct) | Docker SDK (prefixed) |
| State | MemorySaver checkpointer | Thread-based deps |
| Planning | Built-in todos | docker_create_plan tool |

## Getting Started

```bash
# Install
python3 -m venv .venv
.venv/bin/pip install -e ".[dev,agentv2]"

# Configure
cp .env.example .env
# Add OPENROUTER_API_KEY to .env

# Run V1 (LangGraph)
.venv/bin/python -m src.multi_agent.runtime.cli

# Run V2 (Pydantic)
.venv/bin/python -m src.multi_agent_v2.runtime.cli_v2 -v
```
