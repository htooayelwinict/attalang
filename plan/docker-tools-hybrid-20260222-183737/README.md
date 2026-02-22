# Plan: Docker Tools Hybrid Optimization

**Created:** 2026-02-22 18:37
**Status:** Ready for Implementation

## Summary

Optimize V1 Docker agent token usage by implementing hybrid approach: bash commands for safe operations (70-80% token reduction), SDK tools with HITL for dangerous operations.

## Goals

- [ ] Create `docker_bash()` tool with safety validation
- [ ] Migrate 15 safe tools to bash-based implementation
- [ ] Maintain HITL security for dangerous operations
- [ ] Achieve 70%+ token reduction for common operations

## Scope

### In Scope
- New `docker_bash()` tool with command whitelist
- Migration of safe SDK tools to bash equivalents
- Token reduction verification

### Out of Scope
- V2 (Pydantic) changes
- New dangerous tool creation
- CLI interface changes
- Docker SDK removal (keeping for complex ops)

## Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| HITL bypass | High | Strict whitelist, no dangerous commands in bash tool |
| Tool breakage | Medium | Full test coverage before migration |
| Token regression | Low | Benchmark tests added |

## Phases Overview

| Phase | Description | Est. Effort |
|-------|-------------|-------------|
| 1 | Create `docker_bash()` tool | 2-3h (S) |
| 2 | Migrate 15 safe tools | 4-6h (M) |
| 3 | Update agent config | 1-2h (S) |
| 4 | Testing & validation | 2-3h (S) |

**Total: 9-14 hours**

## Files to Modify

| File | Change |
|------|--------|
| `src/multi_agent/tools/docker_tools.py` | Add bash tool, migrate 15 tools |
| `src/multi_agent/agents/docker_agent.py` | Verify HITL config (no changes needed) |
| `tests/test_docker_bash.py` | Create |
| `tests/test_token_reduction.py` | Create |

## Expected Outcome

| Metric | Before | After |
|--------|--------|-------|
| list_containers | ~250 tokens | ~60 tokens |
| get_container_logs | ~180 tokens | ~40 tokens |
| start/stop/restart | ~120 tokens | ~25 tokens |
| Total common ops | 150-300 | 30-80 |

## Next Steps

1. Review `plan.md` for implementation details
2. Run `/code plan/docker-tools-hybrid-20260222-183737` to implement
