# Dynamic Filtering for Web Search - Research

**Research Date:** 2026-02-20
**Source:** [Claude Blog - Improved Web Search with Dynamic Filtering](https://claude.com/blog/improved-web-search-with-dynamic-filtering)

---

## Executive Summary

Claude's web search and web fetch tools now use **code execution to dynamically filter results** before they reach the context window. Benchmarks show:
- **+11% average accuracy improvement**
- **-24% fewer input tokens**

Released alongside Claude Opus 4.6 and Sonnet 4.6 on February 17, 2026.

---

## The Problem: Token-Intensive Web Search

Traditional web search workflows are highly inefficient:

```
┌─────────────────────────────────────────────────────────────┐
│            Traditional Web Search Flow                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Make query ──▶ 2. Pull search results into context     │
│                              │                              │
│                              ▼                              │
│  3. Fetch full HTML from multiple websites                  │
│                              │                              │
│                              ▼                              │
│  4. Load ALL content into context window                    │
│                              │                              │
│                              ▼                              │
│  5. Reason over irrelevant data ──▶ DEGRADED RESPONSE      │
│                                                             │
│  ⚠️ Problem: Most context is irrelevant                     │
└─────────────────────────────────────────────────────────────┘
```

### Key Issues

| Issue | Impact |
|-------|--------|
| Full HTML loading | Context window pollution |
| Irrelevant content | Degraded response quality |
| Token waste | Higher costs |
| No preprocessing | Manual filtering required |

---

## The Solution: Dynamic Filtering

Claude now **writes and executes code during web searches** to post-process results:

```
┌─────────────────────────────────────────────────────────────┐
│            Dynamic Filtering Flow                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Make query ──▶ 2. Pull search results                   │
│                              │                              │
│                              ▼                              │
│  3. Claude writes Python code to FILTER results             │
│                              │                              │
│                              ▼                              │
│  4. Execute code in sandbox ──▶ Keep relevant, discard rest │
│                              │                              │
│                              ▼                              │
│  5. Load only FILTERED content into context                 │
│                              │                              │
│                              ▼                              │
│  6. Reason over RELEVANT data ──▶ IMPROVED RESPONSE        │
│                                                             │
│  ✅ Result: Cleaner context, better answers                 │
└─────────────────────────────────────────────────────────────┘
```

### How It Works

1. **Claude receives search results**
2. **Writes Python code** to parse, filter, and extract relevant information
3. **Executes code** in sandbox environment
4. **Returns only filtered content** to context window

---

## Benchmark Results

### BrowseComp: Finding One Hard-to-Find Answer

**What it tests:** Navigate many websites to find specific, deliberately hard-to-find information.

| Model | Without Filtering | With Dynamic Filtering | Improvement |
|-------|-------------------|------------------------|-------------|
| Sonnet 4.6 | 33.3% | 46.6% | **+13.3%** |
| Opus 4.6 | 45.3% | 61.6% | **+16.3%** |

### DeepsearchQA: Finding Many Answers

**What it tests:** Research queries with many correct answers; tests systematic multi-step searches. Measured by F1 score (precision + recall).

| Model | Without Filtering | With Dynamic Filtering | Improvement |
|-------|-------------------|------------------------|-------------|
| Sonnet 4.6 | 52.6% | 59.4% | **+6.8%** |
| Opus 4.6 | 69.8% | 77.3% | **+7.5%** |

### Token Efficiency

| Metric | Result |
|--------|--------|
| Input tokens | **-24% average reduction** |
| Cost impact | Varies by query complexity |

---

## API Usage

### Enabling Dynamic Filtering

Dynamic filtering is **on by default** for `web_search_20260209` and `web_fetch_20260209` tools with Sonnet 4.6 and Opus 4.6.

```json
{
  "model": "claude-opus-4-6",
  "max_tokens": 4096,
  "tools": [
    {
      "type": "web_search_20260209",
      "name": "web_search"
    },
    {
      "type": "web_fetch_20260209",
      "name": "web_fetch"
    }
  ],
  "messages": [
    {
      "role": "user",
      "content": "Search for the current prices of AAPL and GOOGL, then calculate which has a better P/E ratio."
    }
  ]
}
```

### Supported Tool Types

| Tool | Type Identifier |
|------|-----------------|
| Web Search | `web_search_20260209` |
| Web Fetch | `web_fetch_20260209` |
| Code Execution | `code_execution_20250825` |
| Bash Execution | `bash_code_execution` |
| Text Editor | `text_editor_code_execution` |
| Tool Search (Regex) | `tool_search_tool_regex` |
| Tool Search (BM25) | `tool_search_tool_bm25` |

---

## Related Tools (Now GA)

Released alongside dynamic filtering:

### 1. Code Execution

```json
{
  "type": "code_execution_20250825",
  "name": "code_execution"
}
```

Provides sandbox for agents to:
- Filter context
- Analyze data
- Perform calculations

### 2. Memory

Store and retrieve information across conversations via persistent file directory.

### 3. Programmatic Tool Calling

Execute complex multi-tool workflows in code, keeping intermediate results out of context.

### 4. Tool Search

Dynamically discover tools from large libraries without loading all definitions.

### 5. Tool Use Examples

Provide sample tool calls in definitions to demonstrate usage patterns.

---

## Context Engineering Strategies

Dynamic filtering is part of a broader **Context Engineering** discipline:

### Three Major Strategies

| Strategy | Description | Example |
|----------|-------------|---------|
| **Reduce** | Compress/summarize verbose outputs | Code-based filtering |
| **Offload** | Move data to external storage | Memory tool, Redis |
| **Isolate** | Separate contexts for sub-tasks | Sub-agent architecture |

### Comparison: Prompt Engineering vs Context Engineering

| Aspect | Prompt Engineering | Context Engineering |
|--------|-------------------|---------------------|
| Focus | Input text quality | Context window management |
| Tools | Prompt templates, examples | Filtering, offloading, isolation |
| Scale | Single queries | Multi-turn, long-running agents |
| Complexity | Low | High |

---

## Security Considerations

### Why Sandboxes Are Critical

Running LLM-generated code directly is **extremely dangerous**:

| Threat | Example |
|--------|---------|
| System destruction | File system operations |
| Data exfiltration | Reading env vars, API keys |
| Resource exhaustion | Infinite loops, memory leaks |
| Network attacks | Using as attack vector |

### Sandbox Solutions

| Solution | Features | Use Case |
|----------|----------|----------|
| **E2B** | Firecracker microVMs, <200ms startup | AI-native, used by Claude Code |
| **Docker** | Kernel isolation, network restrictions | General purpose |
| **WASM** | Lightweight, portable | Edge computing |

### Best Practices

1. Never run AI-generated code on production servers
2. Use one-time isolated containers
3. Capture output and immediately destroy container
4. Implement static code analysis (block dangerous calls)
5. Set timeouts for infinite loop prevention
6. Apply output filters for PII (Microsoft Presidio)

---

## Related Benchmarks

### BrowseComp

- Introduced by **OpenAI**
- 1,266 highly challenging questions
- "Online treasure hunt" - hard to find, easy to verify
- GPT-4o: 0.6% | GPT-4.5: 0.9% | Deep Research: 51.5%

### DeepsearchQA

- Research queries with many correct answers
- Tests systematic multi-step searches
- F1 score balances precision and recall

### WideSearch (ByteDance)

- 200 manually curated questions
- 15+ diverse domains
- Best AI: ~5% | Human: ~100%

---

## Customer Spotlight: Quora (Poe)

> "Opus 4.6 with dynamic filtering achieved the highest accuracy on our internal evals when tested against other frontier models. The model behaves like an actual researcher, writing Python to parse, filter, and cross-reference results rather than reasoning over raw HTML in context."
>
> — Gareth Jones, Product and Research Lead, Quora

---

## Key Takeaways

1. **Dynamic filtering** = Claude writes code to filter search results before loading into context
2. **+11% accuracy**, **-24% tokens** on average
3. **Default enabled** for new web_search/web_fetch tools with Sonnet/Opus 4.6
4. Part of broader **Context Engineering** discipline
5. Requires **secure sandbox execution**
6. Best for: technical documentation search, citation verification, complex research

---

## References

### Official Sources

- [Claude Blog - Dynamic Filtering](https://claude.com/blog/improved-web-search-with-dynamic-filtering)
- [Claude API Documentation](https://platform.claude.com/docs)
- [Anthropic Cookbook](https://github.com/anthropics/anthropic-cookbook)

### Related Research

- [Context Window Management Research](https://arxiv.org/html/2510.25423v1)
- [Securing AI Agent Execution](https://arxiv.org/html/2510.21236v1)
- [WideSearch Benchmark](https://next.hyper.ai/cn/papers/2508.07999)
- [BrowseComp Benchmark](https://view.inews.qq.com/a/20250411A01TC900)

### Framework Implementations

- [LobsterAI - Code Execution Sandbox](https://github.com/netease-youdao/LobsterAI)
- [TencentCloudADP/youtu-agent](https://github.com/TencentCloudADP/youtu-agent)
- [xfstudio/skills - Context Management](https://github.com/xfstudio/skills)
