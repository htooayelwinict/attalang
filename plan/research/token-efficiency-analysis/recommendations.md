# Token Efficiency Recommendations

## Priority 1: High Impact Changes (50-70% token reduction)

### 1.1 Switch to V2 Runtime

**Current State:** V1 uses DeepAgents + LangGraph + LangChain (3 framework layers)
**Recommendation:** Use V2 Pydantic-DeepAgents (1 framework layer)

**Implementation:**
```python
# Instead of V1:
from src.multi_agent.runtime import create_docker_graph_runtime
runtime = create_docker_graph_runtime(model="openai/gpt-4o-mini")

# Use V2:
from src.multi_agent_v2.runtime import create_docker_graph_runtime_v2
runtime = create_docker_graph_runtime_v2(model="openai/gpt-4o-mini")
```

**Estimated Savings:** 30-40k tokens per task
**File Location:** `/src/multi_agent_v2/runtime/runtime_v2.py`

### 1.2 Implement Conversation Summarization

**Current State:** Full conversation history retained indefinitely
**Recommendation:** Implement sliding window with summarization

**Implementation Pattern:**
```python
# In DockerAgent or runtime
MAX_HISTORY_TURNS = 5
SUMMARIZE_AFTER_TURNS = 10

def _should_summarize(self, messages: list) -> bool:
    return len(messages) > SUMMARIZE_AFTER_TURNS * 2

def _summarize_history(self, messages: list) -> list:
    # Keep system prompt + last N turns + summary
    summary = self._model.invoke(
        "Summarize the conversation so far, preserving key decisions and context:"
        + "\n".join(m.get("content", "") for m in messages[:-MAX_HISTORY_TURNS])
    )
    return [
        messages[0],  # System prompt
        {"role": "assistant", "content": f"Previous context: {summary.content}"},
        *messages[-MAX_HISTORY_TURNS:]  # Recent turns
    ]
```

**Estimated Savings:** 50-70k tokens for long conversations
**Location to Modify:** `/src/multi_agent/agents/docker_agent.py` or `/src/multi_agent_v2/agents/docker_agent_v2.py`

### 1.3 Consolidate Tool Schemas

**Current State:** 19 Docker tools with verbose schemas (~17KB)
**Recommendation:** Consolidate similar tools, shorten descriptions

**Tool Consolidation Map:**
| Current Tools | Consolidated Tool | Savings |
|---------------|-------------------|---------|
| remove_container, remove_image, remove_network, remove_volume | remove_resource | ~2k tokens |
| prune_images, prune_volumes, docker_system_prune | prune_resources | ~2k tokens |
| create_network, create_volume | create_resource | ~1k tokens |

**Implementation:**
```python
@tool
def remove_resource(resource_type: str, resource_id: str, force: bool = False) -> str:
    """Remove a Docker resource (container, image, network, or volume).
    
    Args:
        resource_type: One of 'container', 'image', 'network', 'volume'
        resource_id: ID or name of resource to remove
        force: Force removal (default: False)
    """
    handlers = {
        "container": lambda: docker_client().containers.remove(resource_id, force=force),
        "image": lambda: docker_client().images.remove(resource_id, force=force),
        "network": lambda: docker_client().networks.get(resource_id).remove(),
        "volume": lambda: docker_client().volumes.get(resource_id).remove(),
    }
    # ...
```

**Estimated Savings:** 5-6k tokens per API call
**Location to Modify:** `/src/multi_agent/tools/docker_tools.py`

## Priority 2: Medium Impact Changes (20-30% reduction)

### 2.1 Enable Prompt Caching

**Current State:** Full context sent every API call
**Recommendation:** Use Anthropic's prompt caching for static content

**Implementation:**
```python
# In llm.py or agent config
cached_content = {
    "system": system_prompt,  # Cached
    "tools": tool_schemas,    # Cached
}

# Anthropic API supports:
response = client.messages.create(
    model="claude-3-5-sonnet",
    system=[
        {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}
    ],
    tools=[{"name": t.name, "cache_control": {"type": "ephemeral"}, ...} for t in tools],
    messages=messages
)
```

**Estimated Savings:** 90% cache hit rate on static content = ~5k tokens saved per call
**Requirement:** Anthropic API (not OpenRouter)

### 2.2 Lazy Tool Loading

**Current State:** All 19 tools loaded every session
**Recommendation:** Load subset based on task classification

**Implementation:**
```python
# In DockerAgent.__init__
TOOL_SUBSETS = {
    "read_only": ["docker_bash", "logs", "inspect", "stats", "info", "version"],
    "container_ops": ["docker_bash", "run_container", "exec_in_container", "remove_container"],
    "image_ops": ["docker_bash", "pull_image", "build_image", "tag_image", "remove_image"],
    "network_ops": ["docker_bash", "create_network", "connect_to_network", "disconnect_from_network"],
    "compose_ops": ["compose_up", "compose_down", "docker_bash"],
}

def _classify_task(self, user_input: str) -> str:
    # Simple keyword matching
    if any(kw in user_input.lower() for kw in ["list", "show", "get", "logs", "status"]):
        return "read_only"
    # ...
```

**Estimated Savings:** 2-3k tokens per API call
**Location to Modify:** `/src/multi_agent/agents/docker_agent.py`

### 2.3 Reduce Tool Output Size

**Current State:** MAX_TOOL_RESPONSE_CHARS = 4000
**Recommendation:** Reduce to 2000, add smart truncation

**Implementation:**
```python
# In docker_tools.py
MAX_TOOL_RESPONSE_CHARS = int(os.getenv("DOCKER_TOOL_MAX_RESPONSE_CHARS", "2000"))

def _truncate_smart(value: str, max_chars: int = MAX_TOOL_RESPONSE_CHARS) -> str:
    """Truncate preserving important sections."""
    if len(value) <= max_chars:
        return value
    
    # Preserve error messages and headers
    lines = value.split("\n")
    header_lines = lines[:5]
    error_lines = [l for l in lines if "error" in l.lower() or "warning" in l.lower()]
    
    remaining_chars = max_chars - sum(len(l) for l in header_lines + error_lines) - 100
    body = "\n".join(lines[5:])[:remaining_chars]
    
    return "\n".join(header_lines) + "\n... [TRUNCATED] ...\n" + body + "\n" + "\n".join(error_lines)
```

**Estimated Savings:** 1-2k tokens per tool call
**Location to Modify:** `/src/multi_agent/tools/docker_tools.py`

## Priority 3: Low Impact Changes (5-10% reduction)

### 3.1 Optimize State Serialization

**Current State:** Full Pydantic model serialization
**Recommendation:** Serialize only changed fields

**Implementation:**
```python
# In states.py
class CoordinatorState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    def to_api_format(self) -> dict:
        """Serialize only set fields for API efficiency."""
        return self.model_dump(exclude_unset=True, exclude_none=True)
```

**Estimated Savings:** 500-1000 tokens per node transition
**Location to Modify:** `/src/multi_agent/runtime/states.py`

### 3.2 Shorten System Prompt

**Current State:** DOCKER_AGENT_INSTRUCTIONS = ~2,416 chars
**Recommendation:** Compress to essential instructions

**Before/After:**
```
# Before (604 tokens)
## MANDATORY PRE-CHECK RULE
Before creating ANY resource (container, network, volume), you MUST check if it already exists...

# After (400 tokens)
## PRE-CHECK: Verify resources exist before creating. Use docker_bash 'ps -a', 'network ls', 'volume ls'.
```

**Estimated Savings:** 200-300 tokens per API call
**Location to Modify:** `/src/multi_agent/agents/docker_agent.py:30-78`

## Implementation Roadmap

### Phase 1: Quick Wins (1-2 days)
1. Reduce MAX_TOOL_RESPONSE_CHARS to 2000
2. Shorten system prompt
3. Switch to V2 runtime for new sessions

### Phase 2: Medium Effort (3-5 days)
4. Implement conversation summarization
5. Consolidate similar tools
6. Add lazy tool loading

### Phase 3: Architecture (1-2 weeks)
7. Remove DeepAgents dependency (use LangGraph directly)
8. Implement prompt caching
9. Build task classification router

## Expected Results

| Phase | Token Reduction | Cumulative Savings |
|-------|-----------------|-------------------|
| Current | 200k | - |
| Phase 1 | 150k | 25% |
| Phase 2 | 80k | 60% |
| Phase 3 | 30-50k | 75-85% |

**Final Target:** 30-50k tokens per task (closer to coding agent efficiency)
