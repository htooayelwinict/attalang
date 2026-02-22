# Agentic Lab

**Purpose:** Testing ground for autonomous AI agent frameworks on macOS M1

> ⚠️ **Security Warning:** These agents require broad system permissions. Use dedicated user accounts or VMs.

---

## Research Documents

| Document | Content |
|----------|---------|
| [comprehensive-comparison-20250222.md](research/comprehensive-comparison-20250222.md) | All frameworks comparison matrix |
| [picoclaw-ironclaw-m1-20250222.md](research/picoclaw-ironclaw-m1-20250222.md) | OpenClaw variants (Go/Rust) |
| [agent-frameworks-m1-20250222.md](research/agent-frameworks-m1-20250222.md) | AutoGPT, BabyAGI, CrewAI, LangGraph |
| [self-hosted-assistants-m1-20250222.md](research/self-hosted-assistants-m1-20250222.md) | Open Interpreter, Aider, Continue |

---

## Quick Install

```bash
# Local LLM backend (M1 optimized)
brew install ollama
ollama run llama2

# Coding assistants
brew install aider
brew install tabby
pip install open-interpreter

# Multi-agent frameworks
pip install crewai langgraph phidata

# Always-on chat agents
curl -fsSL https://openclaw.ai/install.sh | bash
# Download PicoClaw from GitHub releases
```

---

## Framework Categories

### Chat Platform Agents
- OpenClaw (Node.js)
- PicoClaw (Go, <10MB RAM)
- IronClaw (Rust, WASM sandbox)

### Autonomous Task Agents
- AutoGPT / BabyAGI (experimental)
- CrewAI (multi-agent orchestration)
- LangGraph (stateful agents)
- Phidata (multi-modal workflows)

### Coding Assistants
- Aider (Git-native)
- Open Interpreter (code execution)
- Continue.dev (VS Code extension)
- Cursor / Void Editor (AI IDEs)
- OpenDevin (full SWE in Docker)

### Specialized
- LlamaIndex (RAG)
- Tabby (completion, Metal GPU)
- C/ua (OS control)

---

## Capability vs Risk Matrix

| Autonomy | Risk | Frameworks |
|----------|------|------------|
| 🔴 High | High | OpenDevin, AutoGPT, OpenClaw |
| 🟡 Medium | Medium | Aider, CrewAI, LangGraph |
| 🟢 Low | Low | Continue, Tabby, Codeium |

---

## M1 Hardware Recommendations

| RAM | Recommended Frameworks |
|-----|------------------------|
| 8GB | Cloud APIs, PicoClaw, quantized models |
| 16GB | Most frameworks with local LLMs |
| 32GB+ | Full local development experience |

---

## Next Steps

1. Install Ollama for local LLM backend
2. Pick one category to explore
3. Test in isolated environment
4. Document findings

---

## References

- OpenClaw variants research
- Agent frameworks comparison
- Self-hosted assistants guide
- Setup commands and limitations
