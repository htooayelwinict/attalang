# Loop Detection & Replanning Workflow Analysis

**Study Date:** 2026-02-25
**Source:** `sample-srcs/bot` (Facebook Surfer Agent)
**Focus:** How loop detection triggers replanning via RAG

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         LOOP DETECTION → REPLAN FLOW                          │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. RUNTIME LOOP DETECTION                                                   │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │ TrajectoryCallbackHandler.on_tool_end()                         │    │
│     │   (src/metrics/trajectory_callback.py:168-208)                  │    │
│     │                                                                 │    │
│     │  - Tracks _consecutive_empty_results                             │    │
│     │  - Tracks _same_tool_streak (tool + count)                      │    │
│     │  - Checks identical calls in last N                               │    │
│     │                                                                 │    │
│     │  ABORT CRITERIA:                                                  │    │
│     │  1. Same tool empty 5x → RuntimeError                             │    │
│     │  2. Same tool 6x consecutively → RuntimeError                     │    │
│     │  3. Identical calls 5x → RuntimeError                             │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                    ↓                                        │
│                           Raises RuntimeError                             │
│                                    ↓                                        │
│  2. EXCEPTION HANDLING                                                      │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │ FacebookSurferAgent.invoke()                                    │    │
│     │   (src/agents/facebook_surfer.py:419-525)                       │    │
│     │                                                                 │    │
│     │  Catches "infinite loop detected" error →:                       │    │
│     │  - Stores trajectory in RAG                                      │    │
│     │  - Calls MetricsMiddleware.process_execution()                  │    │
│     │  - Re-raises RuntimeError                                       │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                    ↓                                        │
│  3. REFLECTION & STORAGE                                                     │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │ MetricsMiddleware.process_execution()                           │    │
│     │   (src/metrics/middleware.py:63-229)                           │    │
│     │                                                                 │    │
│     │  If callback._loop_detected == True:                            │    │
│     │  - Calls ReflectionAgent.analyze_trajectory()                    │    │
│     │  - Tags reflection with "max_iterations_exceeded": True          │    │
│     │  - Stores in Qdrant RAG with loop metadata                        │    │
│     │                                                                 │    │
│     │  Reflection adds:                                                │    │
│     │  - failed_patterns (what selectors/actions failed)               │    │
│     │  - successful_patterns (what worked)                             │    │
│     │  - critique (summary)                                            │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                    ↓                                        │
│  4. NEXT RUN - PLANNING AGENT                                              │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │ PlanningAgent.craft_success_plan()                              │    │
│     │   (src/agents/planner.py:103-192)                               │    │
│     │                                                                 │    │
│     │  retrieve_similar_trajectories() → exclude_failed_patterns    │    │
│     │  ↓                                                                │    │
│     │  Formats historical context with:                               │    │
│     │  - working_selectors (refs that worked)                        │    │
│     │  - failed_patterns (reflection data)                            │    │
│     │  - successful_patterns                                          │    │
│     │  ↓                                                                │    │
│     │  Generates JSON plan:                                           │    │
│     │  {                                                              │    │
│     │    "analysis": "What went wrong...",                           │    │
│     │    "suggested_plan": ["1. Navigate...", ...],                   │    │
│     │    "working_selectors": {"profile_link": "..."},               │    │
│     │    "avoid_patterns": ["MUST NOT: scroll home feed..."]          │    │
│     │  }                                                              │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                    ↓                                        │
│  5. EXECUTION WITH PLAN                                                    │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │ FacebookSurferAgent.stream()                                    │    │
│     │   (src/agents/facebook_surfer.py:546-732)                       │    │
│     │                                                                 │    │
│     │  Injects plan into task:                                        │    │
│     │  enhanced_task = f"Task: {task}\n\n{plan}"                     │    │
│     │                                                                 │    │
│     │  Agent follows plan with guardrails:                           │    │
│     │  - ENFORCE avoid_patterns                                       │    │
│     │  - OBEY guardrails                                              │    │
│     │  - Use working_selectors as CUES                                 │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└────────────────────────────────────────────────────────────────────────────┘
```

## Key Files & Line Numbers

| Component | File | Key Lines |
|-----------|------|-------------|
| **Loop Detection** | `sample-srcs/bot/src/metrics/trajectory_callback.py` | 32-34 (vars), 168-208 (detection logic) |
| **Exception Handler** | `sample-srcs/bot/src/agents/facebook_surfer.py` | 419-447 (loop catch + storage) |
| **Reflection** | `sample-srcs/bot/src/metrics/middleware.py` | 164-176 (loop metadata tagging) |
| | `sample-srcs/bot/src/agents/reflection.py` | 45-88 (analyze trajectory) |
| **Planning** | `sample-srcs/bot/src/agents/planner.py` | 127-148 (exclude_failed_patterns) |
| | `sample-srcs/bot/src/agents/planner.py` | 244-350 (format_workflows with selectors) |
| **Plan Injection** | `sample-srcs/bot/src/agents/facebook_surfer.py` | 378-394 (craft plan) |

## Critical Settings

```python
# Loop thresholds (trajectory_callback.py)
_consecutive_empty_threshold = 5  # Line 183
_same_tool_streak_threshold = 6      # Line 191
_identical_calls_threshold = 5       # Line 203

# RAG retrieval filters (planner.py:131-133)
min_score=0.4              # Allow learning from moderate success
min_similarity=0.4         # Match across different topics
exclude_failed_patterns=True  # P1 FIX - deprioritize loops
```

## Loop Detection Patterns

### Pattern 1: Consecutive Empty Results
```python
# trajectory_callback.py:170-188
if is_empty:
    self._consecutive_empty_results += 1
else:
    self._consecutive_empty_results = 0

if self._consecutive_empty_results >= 5:
    self._loop_detected = True
    raise RuntimeError(
        f"🛑 INFINITE LOOP DETECTED: Tool '{tool_name}' returned empty/useless results "
        f"{self._consecutive_empty_results} times consecutively."
    )
```

### Pattern 2: Same Tool Streak
```python
# trajectory_callback.py:176-196
if tool_name == self._same_tool_streak["tool"]:
    self._same_tool_streak["count"] += 1
else:
    self._same_tool_streak = {"tool": tool_name, "count": 1}

if self._same_tool_streak["count"] >= 6:
    self._loop_detected = True
    raise RuntimeError(
        f"🛑 INFINITE LOOP DETECTED: Tool '{tool_name}' called "
        f"{self._same_tool_streak['count']} times in a row."
    )
```

### Pattern 3: Identical Calls
```python
# trajectory_callback.py:199-208
if len(self.trajectory) >= 5:
    recent_tools = [e.get("tool") for e in self.trajectory[-5:] if e.get("type") == "tool_start"]
    recent_inputs = [str(e.get("input", ""))[:100] for e in self.trajectory[-5:] if e.get("type") == "tool_start"]

    if len(recent_tools) >= 5 and len(set(recent_tools)) == 1 and len(set(recent_inputs)) == 1:
        self._loop_detected = True
        raise RuntimeError(
            f"🛑 INFINITE LOOP DETECTED: Same tool '{tool_name}' with identical inputs "
            f"repeated 5+ times."
        )
```

## Exception Handling & Storage

```python
# facebook_surfer.py:419-447
except Exception as e:
    if "infinite loop detected" in str(e).lower():
        # Store failure in RAG with loop metadata
        if metrics_callback is not None and self.metrics_middleware is not None:
            trajectory_data = metrics_callback.get_trajectory()
            metrics_result = await self.metrics_middleware.process_execution(
                task=task,
                trajectory_data={"trajectory": trajectory_data},
                callback=metrics_callback,
            )

        raise RuntimeError(
            f"Agent stuck in infinite loop. Runtime guard aborted execution after:\n{e}"
        ) from e
```

## Reflection & Loop Metadata

```python
# middleware.py:164-176
if callback._loop_detected:
    reflection["max_iterations_exceeded"] = True
    reflection["failure_reason"] = "Infinite loop: repeated identical tool calls"
    reflection["critique"] = (
        f"[INFINITE LOOP DETECTED] {reflection['critique']}\n\n"
        f"⚠️ CRITICAL: Agent stuck in infinite loop (same tool repeated consecutively). "
        f"This was likely caused by: 1) Wrong selector returning empty results, "
        f"2) Retrying same approach without changing strategy, "
        f"3) Not recognizing empty results as failures. "
        f"Planner should avoid this exact selector/approach."
    )
```

## Planning Agent - Retrieval

```python
# planner.py:127-148
similar = await retrieve_similar_trajectories(
    task=task,
    top_k=top_k,
    min_score=0.4,
    min_similarity=0.4,
    exclude_failed_patterns=True,  # KEY: deprioritize failed workflows
    client=self.qdrant_client,
)
```

## Planning Agent - Plan Formatting

```python
# planner.py:244-350
def _format_workflows(self, workflows):
    working_selectors = []
    detailed_steps = []

    for tc in tool_calls:
        inputs = tc.get("input", {})
        if "ref" in inputs and success:
            working_selectors.append({
                "tool": tool_name,
                "ref": inputs["ref"],
                "element": inputs.get("element", "unknown")
            })

    # Format reflection data
    reflection = w.get("reflection", {})
    failed_patterns = reflection.get("failed_patterns", [])
    successful_patterns = reflection.get("successful_patterns", [])
```

## Generated Plan Structure

```json
{
  "analysis": "What went wrong with the selectors/approach",
  "suggested_plan": [
    "1. Navigate to profile (verify URL shows /profile)",
    "2. Verify author name matches",
    "3. Extract posts..."
  ],
  "working_selectors": {
    "profile_link": "Your profile button (aria-label)",
    "posts_tab": "Posts tab link"
  },
  "avoid_patterns": [
    "MUST NOT: scroll home feed expecting to find target user posts",
    "MUST NOT: use feed_story selector (returns empty)"
  ],
  "guardrails": [
    "If selector fails 3+ times, switch strategy",
    "Verify author/ownership before collecting posts"
  ]
}
```

## Execution Guardrails

```python
# facebook_surfer.py:106-117 (system prompt)
**INSTRUCTIONS (ENFORCEABLE):**
1. **Read the Analysis**: Understand the strategy and guardrails.
2. **Follow the Suggested Plan EXACTLY**: It comes from PROVEN success.
3. **Use working_selectors as CUES**: Find fresh refs in YOUR snapshots.
4. **ENFORCE avoid_patterns**: Treat them as HARD CONSTRAINTS.
5. **OBEY guardrails**:
   - If a selector/tool fails 3+ times → IMMEDIATELY switch strategy
   - Verify page state before proceeding
   - Confirm author/ownership before collecting posts
6. **Adapt IF page changed**: Stick to the *intent* of the plan
```

## Comparison: Bot vs G-4

| Aspect | sample-srcs/bot | G-4 (current) |
|--------|-----------------|----------------|
| Loop detection | ✅ 3 patterns + RuntimeError | ⚠️ Silent flag only |
| Exception on loop | ✅ Raises RuntimeError | ❌ No exception |
| Replanning | ✅ RAG-based via PlanningAgent | ❌ No replanning |
| Reflection | ✅ ReflectionAgent analyzes failure | ❌ No reflection |
| Storage | ✅ Qdrant RAG with metadata | ⚠️ JSONL only |
| Guardrails | ✅ avoid_patterns in plan | ❌ No guardrails |

## Recommendations for G-4

1. **Add RuntimeError exception** in collector when loop detected
2. **Catch in runtime nodes** and trigger replanning flow
3. **Add ReflectionAgent** for trajectory analysis
4. **Store loop metadata** for RAG retrieval
5. **Add exclude_failed_patterns** in retrieval
6. **Inject avoid_patterns** into system prompt
