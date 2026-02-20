# Agentic AI Tools Playbook

Reference architecture for building secure multi-agent systems with LangGraph + DeepAgents.

---

## Quick Reference

| Pattern | File | Line |
|---------|------|------|
| Scoped Filesystem Agent | [nodes.py:31-62](../src/multi_agent_app/nodes.py#L31-L62) | `DeepAgentsScopedNode` |
| Read-Only Agent with Auto-Reject | [nodes.py:66-147](../src/multi_agent_app/nodes.py#L66-L147) | `ReadOnlyScopedNode` |
| State Boundary Bridge | [nodes.py:203-221](../src/multi_agent_app/nodes.py#L203-L221) | `BridgeNode` |
| LLM Task Router | [classifier.py:16-67](../src/multi_agent_app/classifier.py#L16-L67) | `LLMTaskClassifier` |
| Dual Graph Runtime | [runtime.py:87-107](../src/multi_agent_app/runtime.py#L87-L107) | `_build_*_graph()` |
| State Projection | [runtime.py:72-85](../src/multi_agent_app/runtime.py#L72-L85) | `_customer_from_bridge_node` |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      ADMIN GRAPH                            │
│  State: GlobalState (has secret_context, secret_key_ref)    │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Supervisor  │───▶│    Bridge    │───▶│  Customer    │  │
│  │  (admin/)    │    │  (projects)  │    │  (docs/)     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                   │                    │          │
│         ▼                   ▼                    ▼          │
│   respond_admin      UnsafeState          (read-only)      │
│       or             (no secrets)                           │
│   route_bridge                                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                       USER GRAPH                            │
│  State: UnsafeState (cannot hold secrets)                   │
│                                                             │
│  ┌──────────────┐                                          │
│  │  Customer    │                                          │
│  │  (docs/)     │                                          │
│  └──────────────┘                                          │
│  (read-only via interrupt_on)                               │
└─────────────────────────────────────────────────────────────┘
```

**Key Property**: Customer agent NEVER sees GlobalState. Bridge projects to UnsafeState.

---

## Core Patterns

### 1. Scoped Filesystem Node

Creates isolated filesystem access with path normalization.

```python
@dataclass
class DeepAgentsScopedNode:
    scope_name: str
    backend: FilesystemBackend
    model: BaseChatModel
    agent: Any

    @classmethod
    def create(cls, scope_name: str, scope_root: Path, model: BaseChatModel, system_prompt: str):
        backend = FilesystemBackend(root_dir=scope_root, virtual_mode=True)
        agent = create_deep_agent(
            model=model,
            backend=backend,
            system_prompt=system_prompt,
            checkpointer=False,  # No interrupt handling
        )
        return cls(scope_name=scope_name, backend=backend, model=model, agent=agent)

    def respond(self, input_text: str) -> str:
        normalized = normalize_scope_prefixes(input_text, self.scope_name)
        result = self.agent.invoke({"messages": [{"role": "user", "content": normalized}]})
        return extract_last_message(result)
```

**Use When**: Full filesystem access needed (admin, supervisor)

---

### 2. Read-Only Node with Auto-Reject

Blocks write operations using `interrupt_on` with automatic rejection loop.

```python
@dataclass
class ReadOnlyScopedNode:
    BLOCKED_TOOLS: tuple[str, ...] = ("write_file", "edit_file", "glob", "grep")
    checkpointer: MemorySaver = field(default_factory=MemorySaver)

    @classmethod
    def create(cls, scope_name: str, scope_root: Path, model: BaseChatModel, system_prompt: str):
        backend = FilesystemBackend(root_dir=scope_root, virtual_mode=True)
        checkpointer = MemorySaver()

        # Only "reject" allowed - auto-reject pattern
        interrupt_config = {
            tool: {"allowed_decisions": ["reject"]}
            for tool in cls.BLOCKED_TOOLS
        }

        agent = create_deep_agent(
            model=model,
            backend=backend,
            system_prompt=system_prompt,
            checkpointer=checkpointer,  # REQUIRED for interrupt/resume
            interrupt_on=interrupt_config,
        )
        return cls(...)

    def respond(self, input_text: str) -> str:
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        result = self.agent.invoke(
            {"messages": [{"role": "user", "content": normalized_input}]},
            config=config,
        )

        # Auto-reject loop
        while result.get("__interrupt__"):
            result = self.agent.invoke(
                Command(resume={
                    "decisions": [{
                        "type": "reject",
                        "message": "SECURITY ALERT: file creation is not allowed. Terminate this attempt and do not retry with different paths.",
                    }]
                }),
                config=config,
            )

        return extract_last_message(result)
```

**Use When**: Customer-facing, untrusted, or restricted agents

**Critical**: Checkpointer is REQUIRED for interrupt/resume to work.

---

### 3. State Boundary Bridge

Projects high-privilege state to low-privilege state, stripping secrets.

```python
# State definitions (states.py)
class GlobalState(TypedDict):
    messages: list[BaseMessage]
    admin_input: str
    secret_context: str | None      # NEVER forwarded
    secret_key_ref: str | None      # NEVER forwarded
    route: RouteDecision | None
    supervisor_response: str | None
    customer_response: str | None

class UnsafeState(TypedDict):
    messages: list[BaseMessage]
    user_input: str | None
    bridge_input: str | None        # Sanitized from admin_input
    response: str | None
    # NOTE: Cannot hold secret_context or secret_key_ref

# Bridge implementation (nodes.py)
@dataclass
class BridgeNode:
    def invoke(self, state: GlobalState) -> UnsafeState:
        if state.get("origin") != "supervisor":
            raise BridgeAccessError("Bridge accepts input only from supervisor.")

        return {
            "origin": "bridge",
            "bridge_input": state.get("admin_input", ""),  # Only this is forwarded
        }
```

**Use When**: Crossing privilege boundaries

---

### 4. LLM Task Router

Classifies tasks using LLM with deterministic fallback.

```python
@dataclass
class LLMTaskClassifier:
    model: BaseChatModel

    def classify(self, admin_input: str) -> RouteDecision:
        prompt = f"""You are a task router. Classify into:
1. respond_admin - Coding, debugging, system ops, data analysis
2. route_bridge - Documentation, knowledge base, customer content

USER REQUEST: {admin_input}
OUTPUT: Exactly one word - 'route_bridge' or 'respond_admin'."""

        response = self.model.invoke(prompt)
        text = response.content.lower()

        return "route_bridge" if "route_bridge" in text else "respond_admin"
```

**Use When**: Dynamic routing based on intent

---

### 5. Dual Graph Runtime

Separate graphs with incompatible states prevent secret leakage.

```python
class MultiAgentRuntime:
    def _build_admin_graph(self):
        builder = StateGraph(GlobalState)
        builder.add_node("supervisor", self.supervisor.invoke)
        builder.add_node("bridge", self._bridge_node)
        builder.add_node("customer_from_bridge", self._customer_from_bridge_node)

        builder.add_edge(START, "supervisor")
        builder.add_conditional_edges(
            "supervisor",
            self._route_after_supervisor,
            {"respond_admin": END, "route_bridge": "bridge"},
        )
        builder.add_edge("bridge", "customer_from_bridge")
        builder.add_edge("customer_from_bridge", END)
        return builder.compile()

    def _build_user_graph(self):
        builder = StateGraph(UnsafeState)  # Different state type!
        builder.add_node("customer", self.customer.invoke)
        builder.add_edge(START, "customer")
        builder.add_edge("customer", END)
        return builder.compile()
```

**Use When**: Multiple entry points with different privilege levels

---

## File Structure

```
src/multi_agent_app/
├── config.py          # Env loading, settings classes
├── models.py          # RuntimeModels resolver, offline model
├── states.py          # GlobalState, UnsafeState TypedDicts
├── classifier.py      # LLMTaskClassifier for routing
├── nodes.py           # All agent node implementations
├── runtime.py         # Graph builders, CLI entry points
└── cli.py             # Argparse CLI

tests/
└── test_runtime.py    # Security boundary tests

admin/                 # Supervisor scope (gitignored content)
docs/                  # Customer scope (public docs)
```

---

## Security Model

### 1. Path Traversal Prevention

`FilesystemBackend(virtual_mode=True)` blocks `../` at tool level:

```python
# This raises ValueError:
backend.read("/../../etc/passwd")
```

### 2. State Type Isolation

- `GlobalState` has `secret_context`, `secret_key_ref`
- `UnsafeState` physically cannot hold these fields
- Bridge only forwards `admin_input` string

### 3. Write Operation Blocking

`interrupt_on` with `allowed_decisions: ["reject"]` auto-rejects:
- `write_file` - No file creation
- `edit_file` - No modifications
- `glob` - No pattern discovery
- `grep` - No content search

Only `read_file` and `ls` permitted.

### 4. Access Control

Bridge validates `origin == "supervisor"` before projecting state.

---

## Implementation Checklist

### New Agent Node

1. [ ] Create dataclass with required fields (scope_name, backend, model, agent)
2. [ ] Add `@classmethod create()` with FilesystemBackend setup
3. [ ] Add `respond()` with input normalization
4. [ ] If read-only: add checkpointer + interrupt_on config
5. [ ] Add to RuntimeModels if needs separate model

### New Route

1. [ ] Add route type to `RouteDecision` literal
2. [ ] Update classifier prompt with new route criteria
3. [ ] Add conditional edge in graph builder
4. [ ] Add node for new route

### New State Field

1. [ ] Add to appropriate TypedDict (GlobalState or UnsafeState)
2. [ ] Consider if field should cross bridge (security review)
3. [ ] Update bridge projection if needed
4. [ ] Add tests for state isolation

---

## Common Pitfalls

| Issue | Symptom | Fix |
|-------|---------|-----|
| Missing checkpointer | Interrupt doesn't resume | Add `MemorySaver()` to agent |
| Wrong resume format | KeyError 'decisions' | Use `{"decisions": [{"type": "reject", ...}]}` |
| State type mixing | Secrets in UnsafeState | Use separate graphs |
| Path traversal | Access outside scope | Use `virtual_mode=True` |
| Origin not set | BridgeAccessError | Set `origin` in initial state |

---

## Dependencies

```toml
[project.dependencies]
langchain = ">=1.2.10"
langgraph = ">=1.0.8"
deepagents = ">=0.4.1"

[project.optional-dependencies]
dev = ["pytest>=7.0.0"]
```

---

## Testing Patterns

```python
class TestSecurityBoundary(unittest.TestCase):
    def test_bridge_rejects_non_supervisor(self):
        bridge = BridgeNode()
        with self.assertRaises(BridgeAccessError):
            bridge.invoke({"origin": "user_cli", "admin_input": "test"})

    def test_state_sanitization(self):
        bridge = BridgeNode()
        result = bridge.invoke({
            "origin": "supervisor",
            "admin_input": "docs please",
            "secret_context": "SECRET",  # Should be dropped
        })
        self.assertNotIn("secret_context", result)
```

---

## Quick Commands

```bash
# Install
pip install -e .

# Run admin mode
multi-agent-cli --mode admin

# Run user mode
multi-agent-cli --mode user

# Offline mode (no API)
multi-agent-cli --mode admin --model-mode offline

# Run tests
python -m unittest -v tests/test_runtime.py
```

---

## Related Docs

- [ARCHITECTURE-ROUTING.md](./ARCHITECTURE-ROUTING.md) - State flow diagrams
- [PRD.md](./PRD.md) - Product requirements
- [research/](./research/) - LangChain/LangGraph/DeepAgents reference
