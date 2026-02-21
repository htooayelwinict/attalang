# Phase 2: Update nodes.py Access Patterns

## Objective

Update node implementations to work with Pydantic BaseModel state (attribute access instead of dict access).

## Prerequisites

- Phase 1 completed (states converted to Pydantic)

## Tasks

- [ ] Update RouterNode.invoke
  ```python
  # Before
  user_input = state.get("user_input", "").strip()

  # After
  user_input = (state.user_input or "").strip()
  ```
  - Files: `src/multi_agent/runtime/nodes.py`

- [ ] Update DockerWorkerNode.invoke
  ```python
  # Before
  response = self.worker.invoke(
      state.get("request", ""),
      thread_id=state.get("thread_id"),
  )

  # After
  response = self.worker.invoke(
      state.request or "",
      thread_id=state.thread_id,
  )
  ```
  - Files: `src/multi_agent/runtime/nodes.py`

- [ ] Update CoordinatorDockerNode.invoke
  ```python
  # Before
  worker_state: DockerWorkerState = {
      "request": state.get("docker_request", ""),
      "thread_id": state.get("thread_id", ""),
  }
  result = self.docker_node.invoke(worker_state)
  if result.get("error"):
      return {"error": result["error"]}
  return {"docker_response": result.get("response", "")}

  # After
  worker_state = DockerWorkerState(
      request=state.docker_request or "",
      thread_id=state.thread_id,
  )
  result = self.docker_node.invoke(worker_state)
  if result.error:
      return {"error": result.error}
  return {"docker_response": result.response or ""}
  ```
  - Files: `src/multi_agent/runtime/nodes.py`

- [ ] Update FinalizeNode.invoke
  ```python
  # Before
  if state.get("error"):
      return {"final_response": state["error"]}
  return {"final_response": state.get("docker_response", "")}

  # After
  if state.error:
      return {"final_response": state.error}
  return {"final_response": state.docker_response or ""}
  ```
  - Files: `src/multi_agent/runtime/nodes.py`

## Verification

```bash
.venv/bin/python -m pytest tests/test_langgraph_runtime.py -v
```

## Deliverables

- [ ] All `.get()` calls replaced with attribute access
- [ ] Dict construction replaced with model instantiation where appropriate
- [ ] Return values still use dict (LangGraph merges)

## Notes

- Nodes still return `dict` - LangGraph merges updates
- Keep `@dataclass` for nodes
- Use `state.field or default` for optional field access
