# Plan: Docker Agent V2 (Pydantic-DeepAgents)

**Created:** 2026-02-21 17:38
**Status:** Planning
**Branch:** pydantic

## Summary

Migrate Docker management agent from LangChain `deepagents` to Pydantic `pydantic-deep` for type safety and sandboxing.

## Goals
- [ ] Parallel `docker-agentv2` using `pydantic-deep`
- [ ] Type-safe with Pydantic models
- [ ] `virtual_mode=True` sandboxing
- [ ] Feature parity with v1
- [ ] Async-first design

## Phases

| # | Phase | Description |
|---|-------|-------------|
| 1 | Setup | Dependencies + folder structure |
| 2 | Tools | Migrate Docker tools |
| 3 | Agent | DockerAgentV2 class |
| 4 | CLI | Runtime + CLI entrypoint |
| 5 | Test | Validation + comparison |

## Files

```
src/multi_agent/
├── agents_v2/docker_agent_v2.py    # NEW
├── tools_v2/docker_tools_v2.py     # NEW
└── runtime_v2/cli_v2.py            # NEW
```

## Key Resources
- [Pydantic-DeepAgents Docs](https://vstorm-co.github.io/pydantic-deepagents/)
- [pydantic-ai](https://github.com/pydantic/pydantic-ai)
- [Research file](../../research/pydantic-deepagents.md)
