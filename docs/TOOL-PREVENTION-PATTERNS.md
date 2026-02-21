# Tool Prevention Patterns

Reference guide for blocking unwanted tool calls in DeepAgents, based on P-2 implementation.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        GlobalState                               │
│  (Holds secrets: secret_context, secret_key_ref, admin_input)   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SupervisorAgentNode                          │
│  - Uses DeepAgentsScopedNode (ALL tools allowed)                │
│  - Classifies task: "route_bridge" or "respond_admin"           │
└─────────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┴─────────────────┐
            │                                   │
            ▼                                   ▼
┌─────────────────────┐              ┌─────────────────────────────┐
│   respond_admin     │              │       BridgeNode            │
│  (supervisor       │              │  CHECK: origin=="supervisor"│
│   handles directly) │              │  STRIP: secrets removed     │
└─────────────────────┘              └─────────────────────────────┘
                                                  │
                                                  ▼
                                     ┌─────────────────────────────┐
                                     │      UnsafeState            │
                                     │  (No secrets allowed)       │
                                     └─────────────────────────────┘
                                                  │
                                                  ▼
                                     ┌─────────────────────────────┐
                                     │  CustomerServiceAgentNode   │
                                     │  Uses ReadOnlyScopedNode    │
                                     │  BLOCKED: write, edit, etc  │
                                     └─────────────────────────────┘
```

---

## Step-by-Step Flow

### Step 1: Request Arrives at Supervisor

```python
# User input comes in as GlobalState
state = {
    "admin_input": "Delete the config file",
    "secret_context": "API_KEY=xxx",  # Secret!
    "secret_key_ref": "/keys/admin.key",
}

# Supervisor classifies the task
route = self.classifier.classify(admin_input)
# Returns: "route_bridge" or "respond_admin"
```

### Step 2A: Supervisor Handles Directly (Admin Route)

```python
# DeepAgentsScopedNode - ALL tools allowed
worker = DeepAgentsScopedNode.create(
    scope_name="admin",
    scope_root=base_dir / "admin",  # Scoped to /admin
    system_prompt="You are the supervisor agent...",
    # No interrupt_on = all tools allowed
)

response = self.worker.respond(admin_input)
# Agent can write, edit, delete files in /admin scope
```

### Step 2B: Route to Customer Service (Bridge Route)

```python
# BridgeNode acts as security gate
class BridgeNode:
    def invoke(self, state: GlobalState) -> UnsafeState:
        # SECURITY CHECK #1: Origin verification
        if state.get("origin") != "supervisor":
            raise BridgeAccessError("Only supervisor can use bridge!")

        # SECURITY CHECK #2: Strip all secrets
        return {
            "origin": "bridge",
            "bridge_input": state.get("admin_input", ""),
            # secret_context and secret_key_ref are GONE
        }
```

### Step 3: Customer Agent with Read-Only Enforcement

```python
class ReadOnlyScopedNode:
    # These tools are BLOCKED
    BLOCKED_TOOLS = ("write_file", "edit_file", "glob", "grep")

    @classmethod
    def create(cls, ...):
        # Configure interrupt_on - only "reject" decision allowed
        interrupt_config = {
            tool: {"allowed_decisions": ["reject"]}
            for tool in cls.BLOCKED_TOOLS
        }

        agent = create_deep_agent(
            ...
            interrupt_on=interrupt_config,  # KEY: Blocks these tools
        )
```

### Step 4: Auto-Reject Loop

```python
def respond(self, input_text: str) -> str:
    result = self.agent.invoke(...)

    # If agent tried a blocked tool, __interrupt__ is set
    while result.get("__interrupt__"):
        # Auto-reject without human intervention
        result = self.agent.invoke(
            Command(resume={
                "decisions": [{
                    "type": "reject",
                    "message": "SECURITY ALERT: file creation is not allowed!",
                }]
            }),
            config=config,
        )
        # Agent must find another way (read-only) or fail

    return extract_content(result)
```

---

## How `interrupt_on` Works

```python
# Option 1: Require human approval
interrupt_on = {
    "remove_container": {"allowed_decisions": ["approve", "reject"]},
    # Human sees the tool call, can approve or reject
}

# Option 2: Auto-reject (no human needed)
interrupt_on = {
    "write_file": {"allowed_decisions": ["reject"]},  # Only reject allowed!
    # Tool is blocked, agent gets rejection message
}

# Option 3: Full HITL with edit
interrupt_on = {
    "browser_navigate": {"allowed_decisions": ["approve", "edit", "reject"]},
    # Human can approve, edit the URL, or reject
}
```

---

## Security Layers Summary

| Layer | Mechanism | Purpose |
|-------|-----------|---------|
| 1. Origin Check | `BridgeNode` verifies `origin=="supervisor"` | Prevent direct access to customer agent |
| 2. Secret Stripping | GlobalState → UnsafeState | Customer agent never sees secrets |
| 3. Scoped Backend | `FilesystemBackend(root_dir=scope, virtual_mode=True)` | Path traversal prevention |
| 4. Tool Blocking | `interrupt_on={"allowed_decisions": ["reject"]}` | Prevent unwanted tool calls |
| 5. Auto-Reject Loop | `while result.get("__interrupt__")` | Force agent to comply |

---

## Application to Docker Agent

### Dangerous Docker Tools

```python
DANGEROUS_TOOLS = (
    "remove_container",
    "remove_image",
    "docker_system_prune",
    "exec_in_container",  # Arbitrary code execution
)
```

### Implementation Pattern

```python
def _build_agent(self) -> Any:
    backend = FilesystemBackend(
        root_dir=str(self._workspace_dir),
        virtual_mode=True
    )
    checkpointer = MemorySaver()

    # Require approval for dangerous operations
    interrupt_config = {
        tool: {"allowed_decisions": ["approve", "reject"]}
        for tool in self.DANGEROUS_TOOLS
    }

    return create_deep_agent(
        model=self._model,
        tools=self._tools,
        system_prompt=self._instructions,
        skills=[str(self._skills_dir)] if self._skills_dir else None,
        backend=backend,
        checkpointer=checkpointer,
        interrupt_on=interrupt_config,
    )
```

### HITL Resume Pattern

```python
def invoke_with_hitl(self, message: str, thread_id: str) -> str:
    config = {"configurable": {"thread_id": thread_id}}
    result = self._agent.invoke(
        {"messages": [{"role": "user", "content": message}]},
        config=config,
    )

    # Handle interrupts for dangerous tool calls
    while result.get("__interrupt__"):
        # In real app, show to user and get decision
        decision = self._get_user_decision(result["__interrupt__"])

        result = self._agent.invoke(
            Command(resume={"decisions": [decision]}),
            config=config,
        )

    return self._extract_text(result)
```

---

## State Types

```python
from typing import TypedDict

class GlobalState(TypedDict, total=False):
    """Full state with secrets - supervisor only."""
    origin: str
    admin_input: str
    secret_context: str      # Only in GlobalState
    secret_key_ref: str      # Only in GlobalState
    supervisor_response: str
    route: str

class UnsafeState(TypedDict, total=False):
    """Stripped state - customer-facing, no secrets."""
    origin: str
    bridge_input: str
    user_input: str
    response: str
    # No secret_context or secret_key_ref allowed!
```

---

---

# LangGraph State Control & Graph Structure

## Two Separate Graphs

```
┌─────────────────────────────────────────────────────────────────┐
│                        admin_graph                              │
│                     (StateGraph[GlobalState])                   │
│                                                                 │
│   START ──▶ supervisor ──▶ route? ──▶ END (respond_admin)      │
│                  │               │                              │
│                  │               ▼                              │
│                  │         bridge ──▶ customer_from_bridge ──▶ END
│                  │                                              │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        user_graph                               │
│                    (StateGraph[UnsafeState])                    │
│                                                                 │
│              START ──▶ customer ──▶ END                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## State Types

```python
class GlobalState(TypedDict, total=False):
    """Full state with secrets - supervisor/bridge only."""
    origin: Literal["admin_cli", "supervisor", "bridge"]
    admin_input: str
    route: Literal["respond_admin", "route_bridge"]
    supervisor_response: str
    customer_response: str
    bridge_admin_input: str

    # Secrets - NEVER cross to UnsafeState
    secret_context: str
    secret_key_ref: str


class UnsafeState(TypedDict, total=False):
    """Stripped state - customer-facing, NO secrets."""
    origin: Literal["user_cli", "bridge"]
    user_input: str
    bridge_input: str
    response: str
```

---

## Admin Graph (GlobalState)

```python
def _build_admin_graph(self):
    builder = StateGraph(GlobalState)

    # Nodes
    builder.add_node("supervisor", self.supervisor.invoke)
    builder.add_node("bridge", self._bridge_node)
    builder.add_node("customer_from_bridge", self._customer_from_bridge_node)

    # Edges
    builder.add_edge(START, "supervisor")

    # Conditional routing after supervisor
    builder.add_conditional_edges(
        "supervisor",
        self._route_after_supervisor,  # Returns "respond_admin" or "route_bridge"
        {"respond_admin": END, "route_bridge": "bridge"},
    )

    # Bridge path
    builder.add_edge("bridge", "customer_from_bridge")
    builder.add_edge("customer_from_bridge", END)

    return builder.compile()
```

---

## User Graph (UnsafeState)

```python
def _build_user_graph(self):
    builder = StateGraph(UnsafeState)

    # Simple linear graph
    builder.add_node("customer", self.customer.invoke)
    builder.add_edge(START, "customer")
    builder.add_edge("customer", END)

    return builder.compile()
```

---

## Bridge Node (Security Gate)

```python
def _bridge_node(self, state: GlobalState) -> GlobalState:
    """Project GlobalState to UnsafeState boundary."""
    # BridgeNode.invoke() validates origin == "supervisor"
    # Drops secrets, forwards only admin_input
    payload: UnsafeState = self.bridge.invoke(state)

    return {
        "origin": "bridge",
        "bridge_admin_input": payload.get("bridge_input", ""),
    }


def _customer_from_bridge_node(self, state: GlobalState) -> GlobalState:
    """Invoke customer with sanitized state."""
    unsafe_state: UnsafeState = {
        "origin": "bridge",
        "bridge_input": state.get("bridge_admin_input", ""),
    }
    result = self.customer.invoke(unsafe_state)

    return {
        "customer_response": result.get("response", ""),
    }
```

---

## Routing Logic

```python
def _route_after_supervisor(self, state: GlobalState) -> str:
    """Decide next node after supervisor."""
    return state.get("route", "respond_admin")
    # Returns: "respond_admin" → END
    #          "route_bridge"  → bridge → customer_from_bridge → END
```

---

## Entry Points

```python
def run_admin_turn(self, admin_input: str) -> str:
    """Admin CLI entry - uses admin_graph."""
    state: GlobalState = {"origin": "admin_cli", "admin_input": admin_input}
    result = self.admin_graph.invoke(state)

    if result.get("route") == "route_bridge":
        return result.get("customer_response", "")
    return result.get("supervisor_response", "")


def run_user_turn(self, user_input: str) -> str:
    """User CLI entry - uses user_graph."""
    state: UnsafeState = {"origin": "user_cli", "user_input": user_input}
    result = self.user_graph.invoke(state)
    return result.get("response", "")
```

---

## Key Graph Patterns

| Pattern | Implementation |
|---------|----------------|
| Two graphs | `admin_graph` (GlobalState) + `user_graph` (UnsafeState) |
| Conditional routing | `add_conditional_edges()` with router function |
| State isolation | Bridge strips secrets before crossing to customer |
| Origin tracking | `origin` field tracks request source |
| Type safety | TypedDict with `Literal` for enum-like fields |

---

## Source

Based on:
- `sample-srcs/P-2/src/multi_agent_app/nodes.py`
- `sample-srcs/P-2/src/multi_agent_app/runtime.py`
- `sample-srcs/P-2/src/multi_agent_app/states.py`
