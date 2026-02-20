# Flowchart Reference: LangGraph State Architecture and DeepAgents Customization

This reference file maps the runtime flow in the current codebase.

Primary implementation files:
- `src/multi_agent_app/runtime.py`
- `src/multi_agent_app/nodes.py`
- `src/multi_agent_app/states.py`
- `src/multi_agent_app/classifier.py`
- `src/multi_agent_app/models.py`

## 1. Runtime Component Map

```mermaid
flowchart TD
    CLI["CLI entrypoint<br/>multi-agent-cli"] --> MODE{"Mode switch"}

    MODE -->|"admin"| RTA["MultiAgentRuntime.run_admin_turn"]
    MODE -->|"user"| RTU["MultiAgentRuntime.run_user_turn"]

    RTA --> AG["Admin Graph<br/>StateGraph(GlobalState)"]
    RTU --> UG["User Graph<br/>StateGraph(UnsafeState)"]

    AG --> SUP["SupervisorAgentNode"]
    SUP --> CLS["LLMTaskClassifier"]
    SUP --> SA["DeepAgentsScopedNode<br/>scope admin"]
    SA --> AFS["FilesystemBackend<br/>root admin<br/>virtual_mode true"]

    SUP -->|"route_bridge"| BR["BridgeNode"]
    BR --> CFB["customer_from_bridge wrapper"]
    CFB --> CS["CustomerServiceAgentNode"]

    UG --> CS
    CS --> RO["ReadOnlyScopedNode<br/>scope docs"]
    RO --> CFS["FilesystemBackend<br/>root docs<br/>virtual_mode true"]
```

## 2. LangGraph State Architectures

```mermaid
flowchart LR
    subgraph ADMIN["Admin Graph uses GlobalState"]
        A0["START"] --> A1["supervisor.invoke"]
        A1 -->|"route respond_admin"| AEND["END"]
        A1 -->|"route route_bridge"| A2["bridge wrapper node"]
        A2 --> A3["customer_from_bridge node"]
        A3 --> AEND
    end

    subgraph USER["User Graph uses UnsafeState"]
        U0["START"] --> U1["customer.invoke"]
        U1 --> UEND["END"]
    end
```

## 3. State Boundary Projection

```mermaid
flowchart TD
    G["GlobalState<br/>origin admin_cli or supervisor<br/>admin_input<br/>route<br/>supervisor_response<br/>customer_response<br/>secret_context<br/>secret_key_ref"] --> B{"BridgeNode.invoke"}

    B -->|"origin is not supervisor"| E["BridgeAccessError"]
    B -->|"origin is supervisor"| U["UnsafeState payload<br/>origin bridge<br/>bridge_input only"]

    U --> WR["runtime._bridge_node maps bridge_input to bridge_admin_input in GlobalState"]
    WR --> CW["runtime._customer_from_bridge_node builds fresh UnsafeState for customer node"]
```

## 4. DeepAgents Customization

```mermaid
flowchart TB
    subgraph SUPP["Supervisor worker path"]
        S1["DeepAgentsScopedNode.create"] --> S2["FilesystemBackend(root admin, virtual_mode true)"]
        S2 --> S3["create_deep_agent with checkpointer false"]
        S3 --> S4["respond() normalizes /admin/... to /... before invoke"]
    end

    subgraph CUSP["Customer worker path"]
        C1["ReadOnlyScopedNode.create"] --> C2["FilesystemBackend(root docs, virtual_mode true)"]
        C2 --> C3["MemorySaver checkpointer"]
        C3 --> C4["create_deep_agent with interrupt_on blocked tools"]
        C4 --> C5["respond() normalizes /docs/... to /... before invoke"]
        C5 --> C6["auto reject loop for interrupts via Command resume decisions reject"]
    end
```

Blocked tools configured in `ReadOnlyScopedNode.BLOCKED_TOOLS`:
- `write_file`
- `edit_file`
- `glob`
- `grep`
- `upload_files`
- `download_files`

## 5. Read-Only Auto-Reject Sequence

```mermaid
sequenceDiagram
    participant CS as CustomerServiceAgentNode
    participant RO as ReadOnlyScopedNode
    participant AG as DeepAgents compiled graph

    CS->>RO: respond(user_input or bridge_input)
    RO->>RO: normalize_scope_prefixes for docs scope
    RO->>AG: invoke(messages, thread_id)
    AG-->>RO: result or __interrupt__

    loop while __interrupt__ exists
        RO->>AG: invoke(Command resume decisions reject, same thread_id)
        AG-->>RO: next result
    end

    RO-->>CS: final assistant content
```

## 6. End-to-End Turn Paths

```mermaid
flowchart TD
    IA["Admin input"] --> SV["Supervisor invokes classifier"]
    SV -->|"respond_admin"| RA["Supervisor returns supervisor_response"]
    SV -->|"route_bridge"| RB["Bridge strips to bridge_input"]
    RB --> CU["Customer handles sanitized request"]
    CU --> RC["Return customer_response to admin caller"]

    IU["User input"] --> DU["Direct user graph customer invoke"]
    DU --> RU["Return response"]
```

## 7. Key Invariants Captured by the Flow

- Admin and user flows run on separate LangGraph state schemas.
- Bridge accepts only `origin=supervisor`.
- Bridge forwards only `admin_input` as customer-side `bridge_input`.
- Supervisor filesystem scope is `admin` root in virtual mode.
- Customer filesystem scope is `docs` root in virtual mode.
- Customer write and search style tools are interrupted and auto-rejected.
