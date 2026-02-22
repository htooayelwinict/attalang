# Agentic Lab: Comprehensive Framework Comparison

**Date:** 2025-02-22
**Purpose:** Understand capabilities and limitations of autonomous AI agents on M1 Mac

## Framework Categories

### 1. Chat Platform Agents (OpenClaw-style)
| Agent | Language | Local | API | Focus |
|-------|----------|-------|-----|-------|
| **OpenClaw** | Node.js | ⚠️ | ✅ | Always-on assistant |
| **PicoClaw** | Go | ✅ | ✅ | Embedded/lightweight |
| **IronClaw** | Rust | ✅ | ✅ | Privacy/CRM |

### 2. Autonomous Task Agents
| Framework | Language | Local | M1 Optimized |
|-----------|----------|-------|--------------|
| **AutoGPT** | Python | ⚠️ | ❌ |
| **BabyAGI** | Python | ⚠️ | ❌ |
| **CrewAI** | Python | ✅ | ✅ |
| **LangGraph** | Python | ✅ | ✅ (Studio only) |
| **Phidata** | Python | ✅ | ✅ |

### 3. Coding Assistants
| Framework | Type | Git Integration |
|-----------|------|-----------------|
| **Aider** | Terminal | ✅ Native |
| **Cursor** | IDE | ✅ Built-in |
| **Void Editor** | IDE | ✅ |
| **Continue.dev** | Extension | ⚠️ Basic |
| **OpenDevin** | Full SE | ✅ Sandbox |
| **Open Interpreter** | Code runner | ❌ |

### 4. Specialized
| Framework | Focus | M1 Feature |
|-----------|-------|------------|
| **LlamaIndex** | RAG | Unified memory |
| **Tabby** | Completion | Metal GPU |
| **C/ua** | OS Control | Silicon optimized |

---

## Capability Matrix

| Capability | Best For |
|------------|----------|
| **Always-on 24/7** | OpenClaw, PicoClaw |
| **Multi-agent orchestration** | CrewAI, LangGraph |
| **Software engineering** | OpenDevin, Aider |
| **Quick code execution** | Open Interpreter |
| **RAG + custom data** | LlamaIndex |
| **Privacy/security** | IronClaw, local LLMs |
| **Minimal resources** | PicoClaw (<10MB RAM) |
| **IDE integration** | Continue, Cursor, Void |
| **Visual debugging** | LangGraph Studio |

---

## Known Limitations

### Framework-Specific
| Framework | Limitation |
|-----------|------------|
| **AutoGPT** | Costly, experimental, no M1 kernels |
| **BabyAGI** | Continuous costs, may loop |
| **CrewAI** | Strict Python versions, bugs |
| **LangGraph** | Breaking changes, memory issues |
| **OpenDevin** | Complex setup, Docker required |
| **PicoClaw** | Simple tasks only |
| **IronClaw** | CRM-focused, complex |

### M1-Specific
| Issue | Affected Frameworks | Mitigation |
|-------|---------------------|------------|
| **8GB RAM** | Local LLMs | Use quantized models, cloud APIs |
| **16GB RAM** | Larger models | Acceptable for most |
| **32GB+ RAM** | Full local | Optimal experience |
| **No AutoGPTQ** | AutoGPT | Use cloud API |
| **Heat/Battery** | Local inference | Monitor, use cloud |

---

## Autonomy Spectrum

```
Full Autonomy                  No Autonomy
OpenDevin ──────► Open Interpreter ─────► Tabny
    │                    │                  │
SWE Agent           Aider              Continue
AutoGPT           Cursor             Codeium
BabyAGI
```

**Higher autonomy = higher risk + higher reward**

---

## Quick Start Recommendations

### For Learning
```bash
# Start with these (easiest to install)
brew install ollama
pip install open-interpreter
pip install aider-chat
code --install-extension Continue.continue
```

### For Production
```bash
# Multi-agent: CrewAI
pip install crewai

# SWE: OpenDevin (requires Docker)
# Or Aider for simpler workflows

# Always-on: PicoClaw (lightweight)
```

### For Research
```bash
# RAG: LlamaIndex
pip install llamaindex

# Graph-based: LangGraph
pip install langgraph

# Privacy: IronClaw (complex setup)
```

---

## Installation Commands Cheat Sheet

```bash
# === Chat Platform Agents ===
# OpenClaw
curl -fsSL https://openclaw.ai/install.sh | bash

# PicoClaw (binary download)
wget https://github.com/sipeed/picoclaw/releases/download/v*/picoclaw-darwin-arm64
chmod +x picoclaw-darwin-arm64
sudo mv picoclaw-darwin-arm64 /usr/local/bin/picoclaw

# === Autonomous Agents ===
# CrewAI
pip install crewai

# LangGraph
pip install langgraph

# Phidata
pip install phidata

# LlamaIndex
pip install llamaindex

# AutoGPT/BabyAGI (clone from GitHub)
git clone https://github.com/Significant-Gravitas/AutoGPT.git
git clone https://github.com/yoheinakajima/babyagi.git

# === Coding Assistants ===
# Aider
brew install aider

# Open Interpreter
pip install open-interpreter

# Continue.dev (VS Code)
code --install-extension Continue.continue

# Tabby
brew install tabby

# OpenDevin (complex)
git clone https://github.com/opendevin/opendevin.git

# === Local LLM Backend (M1 optimized) ===
brew install ollama
ollama pull llama2
ollama pull codestral
ollama pull deepseek-coder
```

---

## Security Trade-offs

| Agent | Permissions | Risk Level | Mitigation |
|-------|-------------|------------|------------|
| **OpenClaw** | Full system | 🔴 High | VM, dedicated user |
| **PicoClaw** | Configurable | 🟡 Medium | Limited tools |
| **IronClaw** | WASM sandbox | 🟢 Low | Designed for privacy |
| **OpenDevin** | Docker sandbox | 🟡 Medium | Container isolation |
| **Aider** | Git + files | 🟡 Medium | Review diffs |
| **Open Interpreter** | Code exec | 🔴 High | Review before run |

---

## Next Steps

1. **Install Ollama** first (local LLM backend)
2. **Start simple**: Open Interpreter or Aider
3. **Progress to**: CrewAI or LangGraph for multi-agent
4. **Advanced**: OpenDevin for full SWE
5. **Always-on**: PicoClaw for background tasks

---

## Unresolved Questions

- Which messaging platform integration is best for OpenClaw/PicoClaw on M1?
- How does IronClaw's WASM sandboxing performance compare to Docker on M1?
- What's the actual RAM usage of CrewAI with local LLMs on 8GB M1?
- LangGraph Studio beta stability on M1?
