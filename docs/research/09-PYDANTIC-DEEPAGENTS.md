# Pydantic + DeepAgents Research

**Date:** 2026-02-21  
**Method:** MCP (Context7) documentation research

---

## Scope

Research how to use Pydantic effectively with DeepAgents-based systems to reduce ambiguity, control token growth, and improve tool-call reliability.

---

## Sources (MCP)

1. DeepAgents (official): `/langchain-ai/deepagents`  
   - `create_deep_agent(...)` usage and subagent schema patterns.
2. LangChain OSS Python docs: `/websites/langchain_oss_python`  
   - Tool schema patterns with `@tool(args_schema=...)`.
3. Pydantic (official): `/pydantic/pydantic`  
   - Pydantic v2 validation/serialization patterns (`model_validate`, `model_dump`, constrained fields).
4. Ecosystem signal: `/vstorm-co/pydantic-deepagents` (community project, medium reputation from MCP index).

---

## Key Findings

1. **DeepAgents itself does not replace Pydantic tool schemas**  
   DeepAgents consumes standard LangChain tools, so Pydantic integration is primarily done at the tool boundary (`args_schema`), not via a DeepAgents-specific schema system.

2. **Best integration point is LangChain tool input schemas**  
   For reliable tool-calling, define `BaseModel` input schemas with `Field(...)` descriptions and constraints. This gives the model a better call contract and reduces malformed tool calls.

3. **Pydantic v2 is ideal for deterministic post-processing**  
   After tool returns, `model_validate(...)` and `model_dump(...)` are useful for normalizing and validating structured payloads before returning user-facing output.

4. **Use constrained/strict fields for safety-critical tools**  
   Pydantic constrained fields (`ge/le`, `pattern`, strict types, `extra='forbid'`) reduce bad invocations and prevent silently accepted invalid parameters.

5. **For token-heavy outputs, schema + truncation metadata should be explicit**  
   With output truncation, include machine-readable markers (`_truncated_items`, `_truncated_keys`, truncation marker text). Agent prompt must treat these as partial-success, not failure.

---

## Recommended Pattern for This Repo

### 1) Keep current tool contract (string output), but enforce typed inputs

Use Pydantic `args_schema` for every non-trivial tool input:

```python
from pydantic import BaseModel, Field
from langchain.tools import tool


class ComposeLogsInput(BaseModel):
    file_path: str = Field(default="/docker-compose.yml", description="Compose file in workspace")
    tail: int = Field(default=100, ge=1, le=5000, description="Number of lines")
    follow: bool = Field(default=False, description="Stream logs")


@tool(args_schema=ComposeLogsInput)
def compose_logs(file_path: str = "/docker-compose.yml", tail: int = 100, follow: bool = False) -> str:
    ...
```

### 2) Add optional internal response models for normalization

Define internal Pydantic response models before serializing to final JSON string:

```python
from pydantic import BaseModel


class ToolEnvelope(BaseModel):
    success: bool
    error: str | None = None
```

This keeps your outward compatibility while making internal validation deterministic.

### 3) Tighten schema behavior for risky inputs

For destructive operations (prune/remove/system-level), use:
- bounds for numeric flags and counts
- enum/literal for known options
- `extra='forbid'` on models where unknown keys should fail fast

### 4) Keep truncation policy explicit and agent-aware

Your current truncation metadata approach is directionally correct. Keep these invariants:
- truncation markers must be explicit in payload
- agent prompt must treat truncation as partial output
- failure must be explicit (`success=false` / exit-code style error markers)

---

## Practical Implementation Checklist

1. Convert remaining weakly-typed tool params to Pydantic models (`args_schema`) with constraints.
2. Add shared base input model config for strictness where appropriate.
3. Add optional internal response Pydantic models for envelope and key payload types.
4. Keep serialized JSON string output for backward compatibility with current agent/tool flow.
5. Add tests for:
   - invalid input rejection
   - truncation metadata presence
   - stable error envelope shape

---

## Notes on `pydantic-deepagents` (community project)

MCP index shows a community project (`/vstorm-co/pydantic-deepagents`).  
For this repo, the lower-risk path is still:
- official DeepAgents + official LangChain tool schema patterns + official Pydantic v2.

Reason: this aligns with primary-source docs and your existing architecture, minimizing migration risk.

