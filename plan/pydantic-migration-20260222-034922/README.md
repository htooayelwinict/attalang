# Plan: Pydantic Migration for V1 Runtime

**Created:** 2026-02-22 03:49
**Status:** Planning

## Summary

Migrate V1 LangGraph runtime from TypedDict to Pydantic BaseModel for better runtime validation, serialization, and consistency with existing LangChain tools.

## Goals

- [x] Research completed (`plan/research-pydantic-migration-20260222/research.md`)
- [ ] Convert state types to Pydantic BaseModel
- [ ] Update node access patterns
- [ ] Update runtime invocation
- [ ] Add/update tests for Pydantic validation

## Scope

### In Scope
- `src/multi_agent/runtime/states.py` - State definitions
- `src/multi_agent/runtime/nodes.py` - Node implementations
- `src/multi_agent/runtime/runtime.py` - Graph runtime
- `tests/test_langgraph_runtime.py` - Runtime tests

### Out of Scope
- V2 implementation (already uses Pydantic patterns)
- Tool definitions (already use Pydantic)
- CLI changes

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| LangGraph compatibility | Low | Native BaseModel support confirmed |
| State access patterns | Medium | Use `state.field or default` pattern |
| Test failures | Low | Incremental migration with test verification |
| Serialization edge cases | Low | `.model_dump()` handles this |

## Phases Overview

| Phase | Description | Files |
|-------|-------------|-------|
| 1 | Convert states.py to Pydantic | `states.py` |
| 2 | Update nodes.py access patterns | `nodes.py` |
| 3 | Update runtime.py invocation | `runtime.py` |
| 4 | Update and add tests | `test_langgraph_runtime.py` |

## Files to Modify

| File | Changes |
|------|---------|
| `states.py` | TypedDict → BaseModel, add ConfigDict |
| `nodes.py` | `.get()` → `.field or default` |
| `runtime.py` | Dict init → Model init, `.get()` → `.field` |
| `test_langgraph_runtime.py` | Update assertions, add validation tests |
