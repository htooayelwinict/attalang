# Plan: Quick Win Token Reduction

**Created:** 2026-02-21 01:46
**Goal:** Reduce total token usage from 24k-41k to <15k per query

---

## Context

Current subagent architecture reduces input tokens but increases TOTAL tokens:
- Input: ~6k (down from 11k) ✅
- Output: ~18k (up from ~1k) ❌
- **Total: 24k-41k** (vs 12k with direct tools)

**Root cause:** Verbose subagent outputs + synthesis step

---

## Quick Win Strategy

Based on OpenBridge recommendations:

| # | Solution | Savings | Effort |
|---|----------|---------|--------|
| 1 | JSON-only subagent output | ~7-8k | Low |
| 2 | Skip synthesis for single-subagent | ~5k | Low |

**Target:** Reduce from 24k → ~10k per query

---

## Phase 1: JSON-Only Subagent Output

### Objective
Force all subagents to return minimal JSON instead of verbose prose.

### Changes
1. Update subagent system prompts to demand JSON
2. Add `response_format` constraint (if supported)
3. Validate output is JSON before synthesis

### Files
| File | Action |
|------|--------|
| `src/multi_agent/agents/docker_agent.py` | Update subagent system_prompt |

### New Subagent Prompt Pattern
```python
system_prompt: """Docker container specialist.

CRITICAL: Return ONLY valid JSON. No explanations, no prose.

Example outputs:
- Success: {"status": "success", "container_id": "abc123"}
- List: {"containers": [{"id": "abc", "name": "web", "status": "running"}]}
- Error: {"status": "error", "message": "container not found"}

Guardrails:
- Report impact before destructive operations
- Verify outcomes using list/inspect
"""
```

### Estimate
1 hour (S)

---

## Phase 2: Skip Synthesis for Single-Subagent

### Objective
Return subagent output directly when only one subagent was called.

### Changes
1. Track whether single or multi-subagent delegation
2. For single delegation, return output directly
3. For multi delegation, synthesize

### Files
| File | Action |
|------|--------|
| `src/multi_agent/agents/docker_agent.py` | Modify invoke() logic |

### Implementation Pattern
```python
# In main agent system prompt
"If only ONE subagent is needed, return its output directly.
Do NOT summarize or synthesize single-subagent results."
```

### Estimate
0.5 hour (XS)

---

## Phase 3: Verify Token Reduction

### Objective
Confirm token reduction in LangSmith.

### Tasks
1. Run same 6 test queries
2. Compare LangSmith token counts
3. Target: <15k total per query

### Verification Commands
```bash
multi-agent-cli --prompt "list my docker containers"
multi-agent-cli --prompt "pull nginx:alpine"
multi-agent-cli --prompt "show docker version"
```

### Success Criteria
- [ ] Single-domain queries: <10k tokens
- [ ] Multi-domain queries: <15k tokens
- [ ] All functionality preserved

### Estimate
0.5 hour (XS)

---

## Summary

- **Total Phases**: 3
- **Estimated Effort**: 2 hours
- **Target Reduction**: 24k → 10k (58% savings)

## Rollback

If JSON-only breaks functionality:
1. Revert subagent system prompts
2. Remove "return only JSON" constraint
3. Keep synthesis step
