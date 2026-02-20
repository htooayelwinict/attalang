# Plan: Subagent Architecture for Docker Tools

**Created:** 2026-02-21 00:55
**Goal:** Reduce input tokens from ~11,300 to ~6,500 (43% reduction)

---

## Context

Current DockerAgent loads all 37 tools (4,924 tokens) into main agent context. By splitting into 6 subagents, main agent only sees subagent descriptions (~112 tokens), saving 98% on tool tokens.

### Token Breakdown

| Component | Before | After | Savings |
|-----------|--------|-------|---------|
| Tools in main agent | 4,924 | 112 | 98% |
| Skills | 354 | ~50 | 86% |
| **Main agent total** | **~11,300** | **~6,500** | **43%** |

---

## Code Patterns to Follow

1. **SubAgent schema** - Use dict format with name, description, system_prompt, tools
2. **Tool groups** - Already defined: CONTAINER_TOOLS, IMAGE_TOOLS, etc.
3. **Embed guidance in system_prompt** - Subagents don't support `skills` param
4. **Minimal main agent** - No direct tools, only routes to subagents

---

## Phases

| # | Name | Objective | Est. |
|---|------|-----------|------|
| 1 | Define Subagents | Create subagent configs with embedded guidance | S |
| 2 | Update DockerAgent | Replace ALL_DOCKER_TOOLS with subagents | S |
| 3 | Simplify SKILL.md | Convert to routing-only skill | XS |
| 4 | Test & Verify | Confirm token reduction and functionality | S |

---

## Phase 1: Define Subagents

### Objective
Create 6 subagent configurations with embedded system_prompt guidance.

### Tasks
- [ ] Create `_build_subagents()` method in DockerAgent
- [ ] Define container-agent with CONTAINER_TOOLS + guidance
- [ ] Define image-agent with IMAGE_TOOLS + guidance
- [ ] Define network-agent with NETWORK_TOOLS + guidance
- [ ] Define volume-agent with VOLUME_TOOLS + guidance
- [ ] Define compose-agent with COMPOSE_TOOLS + guidance
- [ ] Define system-agent with SYSTEM_TOOLS + guidance

### Files
| File | Action |
|------|--------|
| `src/multi_agent/agents/docker_agent.py` | Add `_build_subagents()` method |

### Subagent Template
```python
{
    "name": "container-agent",
    "description": "Manages Docker containers: list, run, start, stop, restart, remove, logs, stats, exec, inspect",
    "system_prompt": """Docker container specialist.

## Guardrails
- Report impact before destructive operations
- Don't repeat identical failing calls
- Verify with inspect after operations

## Workflow
1. Identify container and safety impact
2. Execute operation
3. Verify result
4. Report outcome
""",
    "tools": CONTAINER_TOOLS,
}
```

### Estimate
2 hours (S)

---

## Phase 2: Update DockerAgent

### Objective
Replace `ALL_DOCKER_TOOLS` with subagents architecture.

### Tasks
- [ ] Modify `__init__` to call `_build_subagents()`
- [ ] Update `_build_agent()` to pass `subagents=` instead of `tools=`
- [ ] Set `self._tools = []` (main agent has no direct tools)
- [ ] Update system prompt to routing-focused

### Files
| File | Action |
|------|--------|
| `src/multi_agent/agents/docker_agent.py` | Modify constructor and _build_agent |

### Key Changes
```python
# Before
self._tools = list(tools) if tools else list(ALL_DOCKER_TOOLS)
agent = create_deep_agent(tools=self._tools, ...)

# After
self._tools = []  # No direct tools
self._subagents = self._build_subagents()
agent = create_deep_agent(tools=[], subagents=self._subagents, ...)
```

### Estimate
1 hour (XS)

---

## Phase 3: Simplify SKILL.md

### Objective
Convert current SKILL.md to minimal routing guidance.

### Tasks
- [ ] Replace full skill with routing-only content
- [ ] Keep subagent routing table
- [ ] Remove tool-specific guidance (moved to subagent system_prompt)

### Files
| File | Action |
|------|--------|
| `src/skills/docker-management/SKILL.md` | Simplify |

### New SKILL.md Content
```markdown
---
name: docker-management
description: Route Docker tasks to appropriate subagents.
---

# Docker Routing

Route tasks to the appropriate subagent:

| Task Type | Subagent |
|-----------|----------|
| Containers (run, stop, logs, etc.) | container-agent |
| Images (pull, build, tag, etc.) | image-agent |
| Networks | network-agent |
| Volumes | volume-agent |
| Docker Compose | compose-agent |
| System (info, prune, version) | system-agent |

Use the `task` tool to delegate: `task("description", "subagent-name")`
```

### Estimate
0.5 hour (XS)

---

## Phase 4: Test & Verify

### Objective
Confirm token reduction and functionality.

### Tasks
- [ ] Run token calculation script
- [ ] Test single operation: "list my docker containers"
- [ ] Test multi-group operation: "pull nginx and run it"
- [ ] Verify LangSmith trace shows reduced tokens
- [ ] Update TOKEN-USAGE-REPORT.md

### Files
| File | Action |
|------|--------|
| `docs/TOKEN-USAGE-REPORT.md` | Update with new metrics |

### Verification Commands
```bash
# Token calculation
source .venv/bin/activate && python3 -c "
from src.multi_agent.agents import DockerAgent
agent = DockerAgent()
print(f'Main agent tools: {len(agent._tools)}')
print(f'Subagents: {len(agent._subagents)}')
"

# Test run
multi-agent-cli --prompt "list my docker containers"
```

### Estimate
1 hour (S)

---

## Summary

- **Total Phases**: 4
- **Estimated Effort**: 4.5 hours (S)
- **Key Risks**:
  - 🟡 Subagent routing may need prompt tuning
  - 🟡 Multi-group operations require task delegation

## Rollback Plan

If subagent architecture causes issues:
1. Revert `docker_agent.py` to use `ALL_DOCKER_TOOLS`
2. Restore original `SKILL.md`
3. Set `self._tools = ALL_DOCKER_TOOLS`
