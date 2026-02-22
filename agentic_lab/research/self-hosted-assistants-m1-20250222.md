# Research: Self-Hosted Personal AI Assistants for macOS M1

**Date:** 2025-02-22
**Query:** Open Interpreter, OpenDevin, Aider, Continue.dev, Cursor alternatives, Tabby, Codeium

## Quick Comparison

| Assistant | M1 Support | Local-First | Autonomous | Primary Use |
|-----------|------------|-------------|------------|-------------|
| **Open Interpreter** | ✅ | ✅ | ✅ | Code execution |
| **OpenDevin** | ✅ | ✅ | ✅ | Software engineering |
| **Aider** | ✅ | ✅ | ✅ | Git coding agent |
| **Continue.dev** | ✅ | ✅ | ⚠️ | IDE extension |
| **Cursor** | ✅ | ✅ | ⚠️ | AI IDE |
| **Void Editor** | ✅ | ✅ | ✅ | Agent IDE |
| **Tabby** | ✅ | ✅ | ❌ | Code completion |
| **Codeium** | ✅ | ❌ | ❌ | Cloud completion |

---

## 1. Open Interpreter

**M1 Installation:**
```bash
# Via pip
pip install open-interpreter

# Experimental one-line installer
curl -sL https://interpreter.sh/nightly/install | sh

# Run locally
interpreter --local
```

**Key Features:**
- Runs code locally via natural language
- Supports Ollama, Llamafile, Jan, LM Studio
- Python 3.10/3.11 required
- Autonomous code execution for data analysis, coding, problem-solving

**Capabilities:**
- Local model providers
- Direct environment interaction
- Fully offline operation

---

## 2. OpenDevin

**M1 Installation:**
```bash
# Prerequisites
brew install docker git node python

# Clone and setup
git clone https://github.com/opendevin/opendevin.git
cd opendevin
pip install pipenv
pipenv install

# Or with conda
conda create -n opendevin python=3.11
conda activate opendevin
pip install -e .

# Setup backend/frontend
make setup
make build
```

**Key Features:**
- Autonomous AI software engineer
- Local backend (FastAPI) + frontend (Node.js)
- Docker sandboxed environment
- Supports local LLMs (Ollama)

**Capabilities:**
- Writing code
- Running commands
- Web browsing
- Complex software development in sandbox

---

## 3. Aider

**M1 Installation:**
```bash
# Via Homebrew (recommended for M1)
brew install aider

# Via pip
pip install aider-chat

# With local LLM
aider --model ollama/llama2
```

**Key Features:**
- AI coding agent with high autonomy
- Multi-file edits
- Automatic test running
- Git commit automation
- Codebase context mapping
- Terminal-first interface

**Capabilities:**
- Multi-file edits
- Test → fix cycle automation
- Git integration (commits, diffs)
- Local LLM support via Ollama

---

## 4. Continue.dev

**M1 Installation:**
```bash
# VS Code extension
code --install-extension Continue.continue

# JetBrains extension
# Install from marketplace

# Configure Ollama for local LLM
ollama pull codestral
# In Continue settings: "Ollama" provider
```

**Key Features:**
- VS Code / JetBrains extension
- Agent mode for coding tasks
- Local LLM via Ollama
- Chat + code editing + autocomplete

**Capabilities:**
- Context-aware chat
- Code selection for AI
- Intelligent tab completion
- Offline with local models

---

## 5. Cursor Alternatives

### Void Editor
```bash
# Download macOS Apple Silicon build
# Supports Ollama, DeepSeek, Llama, Gemini, Qwen

# Agent Mode: autonomous file operations
# Gather Mode: read-only exploration
```

### C/ua (OS Control)
```bash
# Optimized for Apple Silicon
# AI agents control OS in lightweight VMs
# Sandbox-based OS control
```

### AutoGen Builder
```bash
# No-code agent workflow builder
# Uses Ollama + LiteLLM for local models
```

---

## 6. Tabby

**M1 Installation:**
```bash
# Via Homebrew (M1/M2 optimized)
brew install tabby

# GPU acceleration via Metal API
# Supports StarCoder, CodeLlama, DeepseekCoder
```

**Key Features:**
- Open-source, self-hosted
- Metal GPU acceleration
- IDE plugins (VS Code, NeoVim, IntelliJ)
- Project context aware

**Capabilities:**
- Code completion
- Coding Q&A
- Project-aware suggestions

---

## 7. Codeium

**Note:** Primarily cloud-based, not local-first.

**M1 Installation:**
```bash
# VS Code extension
code --install-extension Codeium.codeium

# Future MCP integration for local data
```

**Key Features:**
- AI code completions
- Error detection
- Multi-IDE support
- Cloud-based (not local)

---

## Detailed Comparison

| Feature | Open Interpreter | OpenDevin | Aider | Continue | Void |
|---------|-----------------|-----------|-------|----------|------|
| **Autonomous** | ✅ High | ✅ High | ✅ High | ⚠️ Medium | ✅ High |
| **Local LLM** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Sandbox** | ❌ | ✅ Docker | ❌ | ❌ | ❌ |
| **Git Integration** | ❌ | ⚠️ | ✅ Native | ⚠️ Basic | ⚠️ |
| **IDE Integration** | ❌ | ❌ | Terminal | ✅ Full | ✅ Built-in |
| **Terminal Access** | ✅ Native | ✅ Sandbox | ✅ Native | ✅ | ✅ |

---

## Installation Summary

```bash
# Quick install commands for M1

# Open Interpreter
pip install open-interpreter

# Aider (best for Git workflows)
brew install aider

# Continue.dev (IDE extension)
code --install-extension Continue.continue

# Tabby (completion)
brew install tabby

# Ollama (local LLM backend for all)
brew install ollama
ollama run llama2
ollama run codestral
ollama run deepseek-coder
```

---

## M1 Optimization Notes

| Tool | M1 Feature | Benefit |
|------|------------|---------|
| **Ollama** | Apple Neural Engine | Metal acceleration |
| **Tabby** | Metal API | GPU acceleration |
| **LlamaIndex** | Unified memory | Efficient inference |
| **C/ua** | Apple Silicon optimized | Native performance |

---

## Security Considerations

All autonomous assistants with code execution require:
- Isolated environments when possible
- Sandboxing for untrusted code
- File access permissions
- Network access controls

**Recommendations:**
- Use Docker sandboxes (OpenDevin)
- Dedicated user account
- Monitor generated code before execution
- Keep API keys in `.env` files

---

## Decision Matrix

| Use Case | Recommended |
|----------|-------------|
| **Software engineering** | OpenDevin, Aider |
| **Quick code execution** | Open Interpreter |
| **IDE integration** | Continue.dev, Void Editor |
| **Git workflows** | Aider |
| **Code completion** | Tabby |
| **Full autonomy** | Open Interpreter, OpenDevin |
| **Privacy critical** | Any with Ollama local |
