# Plan: Subagent Architecture for Docker Tools

**Created:** 2026-02-21 00:55
**Status:** Ready for Implementation

## Summary

Implement subagent architecture to reduce DockerAgent input tokens from ~11,300 to ~6,500 (43% reduction) by splitting 37 tools into 6 specialized subagents.

## Goals

- [x] Analyze current token usage
- [ ] Reduce main agent tokens by 40%+
- [ ] Maintain all 37 tool functionality
- [ ] No breaking changes to API

## Scope

### In Scope
- DockerAgent subagent architecture
- SKILL.md simplification
- Token usage documentation

### Out of Scope
- Tool implementation changes
- CLI changes
- Other agents

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Subagent routing confusion | Medium | Clear descriptions + testing |
| Multi-group operations | Medium | Task delegation examples |
| Token reduction less than expected | Low | Verify with LangSmith |

## Phases Overview

| Phase | Description | Est. Effort |
|-------|-------------|-------------|
| 1 | Define Subagents | S (2h) |
| 2 | Update DockerAgent | XS (1h) |
| 3 | Simplify SKILL.md | XS (0.5h) |
| 4 | Test & Verify | S (1h) |

**Total: ~4.5 hours**

## Files to Modify

| File | Change |
|------|--------|
| `src/multi_agent/agents/docker_agent.py` | Add subagents architecture |
| `src/skills/docker-management/SKILL.md` | Simplify to routing only |
| `docs/TOKEN-USAGE-REPORT.md` | Update metrics |

## Quick Start

```bash
# After implementation, verify
source .venv/bin/activate
multi-agent-cli --prompt "list my docker containers"
```

## Next Steps

1. Review `plan.md` for full details
2. Run `/code plan/subagent-architecture-docker-20260221-005543` to implement
