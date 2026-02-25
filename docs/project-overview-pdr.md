# Project Overview & PDR

## Project Summary

**AttaLang** is a Docker management agent framework providing three parallel implementations:
- **V1 (LangChain)**: Single agent using LangChain DeepAgents with direct tool access + HITL security
- **V2 (Pydantic)**: Single agent using Pydantic-DeepAgents with prefixed tools
- **V3 (Programmatic)**: Token-efficient agent that writes Python code to call Docker tools directly

All versions provide natural language control over Docker operations including containers, images, networks, volumes, and compose stacks.

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
| Feature | V1 | V2 | V3 | Priority |
|---------|----|----|----|----------|
| Container CRUD | ✅ | ✅ | ✅ | High |
| Image management | ✅ | ✅ | ✅ | High |
| Network management | ✅ | ✅ | ✅ | Medium |
| Volume management | ✅ | ✅ | ✅ | Medium |
| Compose support | ✅ | ✅ | ✅ | Medium |
| HITL Security | ✅ | ❌ | ⚠️ | High |
| Token efficiency | Normal | Normal | **High** | High |
| Loop detection | ❌ | ❌ | ✅ | Medium |
| Trajectory tracking | ✅ | ❌ | ✅ | Low |
| Verbose mode | ✅ | ✅ | ✅ | Medium |

### Success Metrics
- Tool call accuracy: 95%+
- Multi-step task completion: 90%+
- Response time: <5s for simple ops

## Tech Stack

| Layer | V1 (LangChain) | V2 (Pydantic) | V3 (Programmatic) |
|-------|-----------------|---------------|-------------------|
| Framework | LangChain DeepAgents | Pydantic-DeepAgents | LangChain DeepAgents |
| Tool calling | Direct (N round-trips) | Prefixed | **Code execution** |
| LLM | OpenRouter | OpenRouter | OpenRouter |
| Tools | Docker SDK (direct) | Docker SDK (prefixed) | **Python bridge** |
| State | MemorySaver | Thread deps | MemorySaver |
| Security | HITL + auto-reject | - | Shell operator blocking |
| Research | Loop detection | - | Loop detection + trajectory |

## Getting Started

```bash
# Install
python3 -m venv .venv
.venv/bin/pip install -e ".[dev,agentv2]"

# Configure
cp .env.example .env
# Add OPENROUTER_API_KEY to .env

# Run V1 (LangGraph) - with HITL security
.venv/bin/python -m src.multi_agent.runtime.cli --hitl

# Run V2 (Pydantic)
.venv/bin/python -m src.multi_agent_v2.runtime.cli_v2 -v

# Run V3 (Programmatic) - token efficient
.venv/bin/python -m src.multi_agent_v3.runtime.cli_v3 -v
```
