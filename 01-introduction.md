# 1. Introduction — What is Google ADK?

## What
**Google ADK (Agent Development Kit)** is Google's open-source agent development framework that lets you build, debug, and deploy reliable AI agents at enterprise scale.

- **Built by:** Google (Cloud / DeepMind teams)
- **Released:** April 9, 2025 at Google Cloud NEXT
- **License:** Apache 2.0
- **SDKs:** Python, TypeScript, Go, Java
- **Docs:** [adk.dev](https://adk.dev/)
- **GitHub:** [google/adk-python](https://github.com/google/adk-python) (19k+ stars)

## Core Architecture at a Glance

ADK uses a **code-first, hierarchical agent tree** model:

```
Runner
  └── Root Agent (LlmAgent)
        ├── Sub-Agent A (SequentialAgent)
        │     ├── Step 1 Agent
        │     └── Step 2 Agent
        ├── Sub-Agent B (ParallelAgent)
        │     ├── Worker 1
        │     └── Worker 2
        └── Tools (functions, APIs, MCP)
```

| Concept | Role |
|---------|------|
| **LlmAgent (Agent)** | Core agent — wraps an LLM, system instruction, and tools |
| **SequentialAgent** | Runs sub-agents in order |
| **ParallelAgent** | Runs sub-agents concurrently |
| **LoopAgent** | Iterates until a condition is met |
| **CustomAgent** | Extend for arbitrary orchestration |
| **Tools** | Functions the agent can call (Python functions, OpenAPI, MCP, Google Search) |
| **Session** | Single conversation thread (short-term memory + state dict) |
| **Memory** | Long-term recall across sessions |
| **Artifacts** | Binary/structured outputs (files, images) |
| **Runner** | Executes the agent tree, manages event flow and streaming |

## Supported LLMs

ADK is **optimized for Gemini but model-agnostic**:

| Provider | Integration |
|----------|-------------|
| **Gemini** (2.0, 1.5 Pro/Flash) | Native, first-class |
| **Claude** (Anthropic) | Built-in |
| **OpenAI, Mistral, Grok, etc.** | Via **LiteLLM** (100+ models) |
| **Local models** | Via **Ollama**, **vLLM** |
| **Any LangChain4j model** (Java) | Via LangChain4j integration |

Different agents in the same tree can use **different models**.

## Key Features
- **Multi-agent orchestration** — hierarchical trees with Sequential, Parallel, Loop agents
- **A2A Protocol** — Agent-to-Agent protocol for cross-framework interop (unique to ADK)
- **MCP Support** — Model Context Protocol for standardized tool integration
- **Built-in Dev UI** — browser-based UI for testing and debugging
- **Streaming** — full streaming support, including Gemini Live API (audio/video)
- **Evaluation framework** — built-in user simulation, metrics, trajectory evaluation
- **Prompt caching, state management, artifacts** — production-ready primitives

## ADK vs Other Agent Frameworks

| Dimension | Google ADK | LangChain/LangGraph | CrewAI | AutoGen (Microsoft) |
|-----------|-----------|---------------------|--------|---------------------|
| Orchestration | Hierarchical agent tree | Directed graph (LangGraph) | Role-based crews | Conversational GroupChat |
| Model lock-in | Gemini-optimized, model-agnostic | Fully agnostic | Fully agnostic | Fully agnostic |
| Inter-agent protocol | **A2A** (unique) | None built-in | None built-in | None built-in |
| Tool protocol | MCP + OpenAPI + functions | MCP + large ecosystem | Built-in + MCP | Function calling |
| Deployment | Vertex AI Agent Engine, Cloud Run, GKE | Self-managed / LangServe | Self-managed | Self-managed |
| Dev UI | Built-in | LangSmith (paid) | None | AutoGen Studio |
| Maturity | Rapidly maturing (bi-weekly releases) | Most mature | Medium | Medium |

## Deployment Options

| Option | Best For |
|--------|----------|
| **Local** (`adk run` / `adk web`) | Development & debugging |
| **Vertex AI Agent Engine** | Fully managed production (no infra) |
| **Cloud Run** | Custom infrastructure, containerized |
| **GKE / Any K8s** | Full infrastructure control |

## Why Pick ADK?
1. **A2A Protocol** — only framework with native cross-framework agent interop
2. **Google Cloud integration** — Vertex AI Agent Engine for zero-infra deployment
3. **Hierarchical multi-agent** — clean architecture for complex agent systems
4. **Model-agnostic** — use Gemini, Claude, OpenAI, or local models in the same tree
5. **Apache 2.0** — fully open source, active community
