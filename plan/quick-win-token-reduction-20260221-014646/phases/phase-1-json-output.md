# Phase 1: JSON-Only Subagent Output

## Objective
Force all subagents to return minimal JSON instead of verbose prose.

## Prerequisites
- None

## Tasks

### 1.1 Update container-agent system prompt
```python
system_prompt: """Docker container specialist.

CRITICAL: Return ONLY valid JSON. No explanations, no markdown, no prose.

Output format:
- Success: {"status": "success", "data": {...}}
- Error: {"status": "error", "message": "..."}

Example: {"status": "success", "data": {"containers": []}}
"""
```

### 1.2 Update all 6 subagent prompts
- container-agent
- image-agent
- network-agent
- volume-agent
- compose-agent
- system-agent

### 1.3 Update main agent prompt
```python
"When receiving subagent JSON output, pass it through directly.
Do NOT summarize or explain. Just return the JSON to the user."
```

## Files
| File | Change |
|------|--------|
| `src/multi_agent/agents/docker_agent.py` | Update all 6 `_build_*_subagent()` methods |

## Verification
```bash
source .venv/bin/activate && multi-agent-cli --prompt "list containers"
# Should return JSON, not prose
```

## Estimate
1 hour (S)
