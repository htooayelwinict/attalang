# Research: OpenClaw Variants on macOS M1

**Date:** 2025-02-22
**Query:** PicoClaw, MiniClaw, IronClaw differences and installation on M1 Mac

## Summary

| Agent | Language | Focus | Resource Use | Sandboxing |
|-------|----------|-------|--------------|------------|
| **PicoClaw** | Go | Embedded/Portable | Ultra-lightweight (<10MB RAM) | Docker (optional) |
| **IronClaw** | Rust | Privacy/Security | Native performance | WASM sandboxes |
| **MiniClaw** | N/A | Does not exist | N/A | N/A |

---

## PicoClaw

**What it is:**
Ultra-lightweight, open-source personal AI assistant by Sipeed. Complete rewrite of OpenClaw in Go, optimized for resource-constrained embedded Linux boards (RISC-V), but fully functional on macOS.

**Key Features:**
- Single static binary
- <10MB RAM, sub-second startup
- Supports external LLM providers (OpenRouter, Zhipu)
- Local AI via Ollama integration
- Optimized for $10 hardware

**macOS M1 Installation:**
```bash
# Download prebuilt binary for macOS arm64
wget https://github.com/sipeed/picoclaw/releases/download/v*/picoclaw-darwin-arm64

# Make executable
chmod +x picoclaw-darwin-arm64

# Move to PATH
sudo mv picoclaw-darwin-arm64 /usr/local/bin/picoclaw

# Initialize
picoclaw onboard
```

**Configuration:** `~/.picoclaw/config.json`

**Capabilities:**
- Workflow management
- Tool utilization
- Command execution
- API interaction

**Limitations:**
- Designed for low-resource environments
- Efficiency over complex multi-agent orchestration

---

## IronClaw

**What it is:**
OpenClaw-inspired implementation in Rust, emphasizing privacy and security. Local AI CRM application hosted on Mac, integrates with Chrome.

**Key Features:**
- Rust-based (single binary)
- WebAssembly (WASM) sandboxes for tool execution
- PostgreSQL for persistence
- Privacy-focused, local data storage
- Protection against prompt injection

**macOS M1 Installation:**
```bash
# Visit GitHub repository for Rust-based IronClaw
# Follow setup instructions
ironclaw onboard
```

**Capabilities:**
- Secure, private AI agent operations
- Local data handling
- CRM functionality
- Robust WASM sandboxing

**Limitations:**
- More complex setup
- Requires technical understanding for customization
- Tied to CRM application use case

---

## MiniClaw

**Status:** Does not exist as an AI agent variant.
Search results refer to physical toy vending machines only.

---

## Comparison Matrix

| Feature | PicoClaw | IronClaw |
|---------|----------|----------|
| **Language** | Go | Rust |
| **RAM** | <10MB | Native efficient |
| **Startup** | Sub-second | Fast |
| **Persistence** | `config.json` | PostgreSQL |
| **Security** | Standard | WASM sandboxes |
| **Primary Use** | Embedded/portable | Privacy/CRM |
| **Installation** | Binary/Docker | Source/wizard |

---

## References

- [PicoClaw GitHub](https://github.com/sipeed/picoclaw)
- [IronClaw Research](https://github.com/search?q=ironclaw+ai+assistant)
