# 🧠 Brainstorm: Reducing Subagent Token Costs

**Date:** 2026-02-21
**Problem:** Subagent architecture increases TOTAL tokens (24k-41k) despite reducing input tokens (6k)

---

## Current State Analysis

| Architecture | Input | Output | Total |
|--------------|-------|--------|-------|
| **Direct tools** | ~11k | ~1k | ~12k |
| **Subagents** | ~6k | ~18k | ~24k |

**Root cause:** Subagent delegation creates token amplification:
1. Main → Subagent context passing
2. Subagent verbose output
3. Main synthesis of results

---

## 💡 Ideas Generated (SCAMPER)

### Substitute
- **Replace subagents with combined tools** - One `docker_container` tool with `action` param instead of 11 separate tools
- **Replace verbose outputs with JSON** - Structured data instead of prose

### Combine
- **Merge similar tools** - `docker_container(action, **params)` handles run/start/stop/remove
- **Batch operations** - Single tool call for multi-step operations

### Adapt
- **Borrow from function calling patterns** - Use structured output mode
- **Adapt tool result compression** - Auto-summarize tool outputs

### Modify
- **Change subagent system prompts** - Force minimal output (JSON only)
- **Reduce tool schema complexity** - Remove optional fields, use simpler types

### Eliminate
- **Remove subagent synthesis step** - Return subagent output directly
- **Eliminate redundant context passing** - Don't re-send full context to subagent

### Reverse
- **Go back to direct tools** - But with simplified schemas
- **Use LLM only for routing** - Execute tools directly, no subagent LLM calls

---

## 📊 Evaluation Matrix

| Idea | Feasibility | Impact | Effort | Score |
|------|-------------|--------|--------|-------|
| 1. Combined tools | High | High | Medium | ⭐⭐⭐⭐ |
| 2. JSON-only output | High | Medium | Low | ⭐⭐⭐ |
| 3. Skip synthesis | Medium | Medium | Low | ⭐⭐⭐ |
| 4. Simplified schemas | High | Medium | Medium | ⭐⭐⭐ |
| 5. Direct SDK for simple ops | Medium | High | Medium | ⭐⭐⭐⭐ |
| 6. Tool output compression | Medium | Medium | High | ⭐⭐ |

---

## 🚀 Top 3 Recommendations

### 1. Combined Tools Pattern (Highest Impact)

**Current:** 11 container tools = 1,484 tokens
**Proposed:** 1 combined tool = ~300 tokens

```python
@tool
def docker_container(
    action: Literal["list", "run", "start", "stop", "remove", "logs", "exec"],
    container_id: str | None = None,
    image: str | None = None,
    **params
) -> str:
    """Execute container operations. Actions: list, run, start, stop, remove, logs, exec."""
```

**Savings:** ~80% on tool tokens

### 2. Minimal Output Subagents

**Current:** Subagents return verbose prose (~10k tokens)
**Proposed:** Return JSON only (~500 tokens)

```python
# Subagent system prompt addition:
"ALWAYS return results as minimal JSON. No explanations, no prose.
Example: {\"status\": \"success\", \"container_id\": \"abc123\"}"
```

**Savings:** ~90% on output tokens

### 3. Hybrid: Direct SDK + LLM Routing

**Current:** Every operation goes through LLM
**Proposed:** Simple operations bypass LLM

```python
# Router decides:
if is_simple_query(prompt):  # "list containers"
    return docker_client.containers.list()  # Direct SDK call
else:
    return agent.invoke(prompt)  # LLM for complex ops
```

**Savings:** ~100% for simple queries, 0% for complex

---

## 🌟 Moonshot

**Tool-less Agent:** Use code generation instead of tool calling:
- Agent writes Python code to execute Docker operations
- Code runs in sandbox, returns results
- No tool schemas in context at all
- Similar to OpenAI Code Interpreter

---

## Next Steps

1. [ ] Implement combined tool pattern for CONTAINER_TOOLS
2. [ ] Update subagent system prompts for JSON-only output
3. [ ] Add simple query detection for direct SDK bypass
4. [ ] Measure token reduction after each change
