# Plan: Quick Win Token Reduction

**Created:** 2026-02-21 01:46
**Status:** Ready for Implementation

## Summary

Reduce total token usage from 24k-41k to <15k per query by enforcing JSON-only subagent output and skipping synthesis for single-subagent calls.

## Goals

- [ ] Reduce single-domain query tokens: 24k → <10k
- [ ] Reduce multi-domain query tokens: 41k → <15k
- [ ] Maintain all functionality

## Scope

### In Scope
- Subagent system prompt updates
- Main agent synthesis optimization

### Out of Scope
- Tool schema changes
- New subagents
- CLI changes

## Phases Overview

| Phase | Description | Est. Effort |
|-------|-------------|-------------|
| 1 | JSON-only subagent output | 1h (S) |
| 2 | Skip synthesis for single-subagent | 0.5h (XS) |
| 3 | Verify token reduction | 0.5h (XS) |

**Total: ~2 hours**

## Files to Modify

| File | Change |
|------|--------|
| `src/multi_agent/agents/docker_agent.py` | Update subagent prompts, main prompt |

## Expected Outcome

| Metric | Before | After |
|--------|--------|-------|
| Simple query | 24k | <10k |
| Multi-domain | 41k | <15k |

## Next Steps

1. Review `plan.md` for details
2. Run `/code plan/quick-win-token-reduction-20260221-014646` to implement
