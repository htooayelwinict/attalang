# Phase 2: Skip Synthesis for Single-Subagent

## Objective
Return subagent output directly when only one subagent was called.

## Prerequisites
- Phase 1 completed (JSON output)

## Tasks

### 2.1 Update main agent system prompt

**Current:**
```
Return concise actions taken, verification status, and next steps.
```

**New:**
```
Output rules:
1. If delegating to ONE subagent: return its output directly, no synthesis
2. If delegating to MULTIPLE subagents: briefly combine results
3. NEVER explain what you did - just show results
4. Keep responses under 200 words unless listing data
```

### 2.2 Consider response_format (if supported)

```python
# In create_deep_agent call
return create_deep_agent(
    ...
    response_format={"type": "json_object"},  # Force JSON
)
```

## Files
| File | Change |
|------|--------|
| `src/multi_agent/agents/docker_agent.py` | Update `DOCKER_AGENT_INSTRUCTIONS` |

## Verification
```bash
multi-agent-cli --prompt "list containers"
# Should return JSON directly, no "I have listed..." preamble
```

## Estimate
0.5 hour (XS)
