# 6. Limitations — What ADK Cannot Do (Yet)

## Top 10 Things a Senior Engineer Must Know

1. **`output_schema` + tools is fragile** — partially fixed but still causes infinite loops and ignored schemas
2. **Tool failures crash entire workflows** — no built-in retry, circuit breakers, or graceful degradation
3. **`InMemorySessionService` is dev-only** — zero persistence, zero multi-instance support
4. **Free tier was gutted Dec 2025** — 50-92% quota cuts; budget for paid tier from day one
5. **Agent Engine is Python-only and region-locked**
6. **MCP support is incomplete** — only Tools, not Resources or Prompts
7. **Multi-agent costs multiply silently** — each agent gets its own full LLM call
8. **No built-in rate limiting or cost controls** — implement externally or face 429 crashes
9. **Ecosystem is 3+ years behind LangChain** — fewer integrations, smaller community
10. **Bi-weekly releases mean breaking changes** — APIs evolve rapidly

---

## Model Limitations

| Constraint | Details |
|------------|---------|
| **Hallucinations** | No ADK-level guardrails; implement via `before_model_callback` |
| **No fine-tuning integration** | Fine-tune externally, reference model ID in ADK |
| **Thinking + fine-tuning** | Mutually exclusive — thinking disabled on fine-tuned models |
| **Thinking tokens** | Billed as output tokens — significant cost multiplier |
| **Claude max_tokens** | Hardcoded to 8192 in ADK's Anthropic adapter ([#3828](https://github.com/google/adk-python/issues/3828)) |
| **Context window** | State serialization becomes slow with large contexts ([#1246](https://github.com/google/adk-python/issues/1246)) |

## Tool Limitations

| Constraint | Details | Workaround |
|------------|---------|------------|
| **`output_schema` + tools** | Incompatible on many models; infinite loops possible | Chain two agents: tool agent → formatting agent |
| **Built-in tool conflicts** | `google_search` + `code_execution` + custom tools can't coexist in one agent | Use `AgentTool` to wrap as sub-agents, or `bypass_multi_tools_limit` (v1.16+) |
| **MCP incomplete** | Only `list_tools()` — no Resources, no Prompts | Wait for updates or use MCP server directly |
| **MCP schema mismatch** | Draft 7 `definitions` vs Draft 2019-09 `$defs` causes `KeyError` | Monkey-patch `McpTool._get_declaration` |
| **FunctionTool + RAG** | Combining in same agent causes 400 errors | Separate into different agents |

## Session / Memory Limitations

| Service | Limitation |
|---------|------------|
| **InMemorySessionService** | No persistence, single-process, dev-only |
| **InMemoryMemoryService** | Lost on restart, no semantic search, can overwhelm context |
| **State values** | Limited to simple text — no complex objects |
| **No Redis session service** | Not available out of the box |
| **No BigQuery sessions** | Community request, not yet implemented |

## Deployment Limitations

| Platform | Limitation |
|----------|------------|
| **Agent Engine** | Python only, region-locked, cold starts, deploy takes minutes |
| **Cloud Run** | Must bring your own session DB, no managed memory service |
| **GKE** | No Helm charts, full DIY infrastructure |
| **TypeScript SDK** | v0.2.0 — significantly behind Python v1.31 |

## Rate Limits (Gemini API)

| Tier | RPM | TPM | RPD |
|------|-----|-----|-----|
| **Free** | 5-15 | 250K | 20-100 |
| **Paid (Tier 1)** | 150-300 | Higher | Higher |

- **No built-in rate limiting** in ADK — 429 errors crash agents ([#4323](https://github.com/google/adk-python/issues/4323))
- **No retry logic** — implement with `tenacity` or custom callbacks

## Multi-Agent Limitations

- **ParallelAgent race conditions** — all agents share state; use unique `output_key` per agent
- **Predefined sub-agents only** — no dynamic agent creation at runtime
- **Agent instance reuse** — can only be added as sub-agent to ONE parent
- **Debugging is hard** — no built-in distributed tracing across agent trees
- **Token cost multiplication** — 3-agent chain = ~3x token cost

## Cost Traps

| Trap | Impact |
|------|--------|
| **Thinking tokens** | Billed as output ($10-15/1M) — compounds in loops |
| **System prompt re-sent** | 2K-token prompt × 100 turns = 200K input tokens |
| **Multi-agent multiplication** | Each sub-agent gets full LLM call with its own context |
| **Google Search Grounding** | Free for 5K/month, then $14-35 per 1K queries |
| **Context cache storage** | $1-4.50 per 1M tokens/hour — clean up or it accumulates |
| **Image output tokens** | $60/1M tokens — 100x more than text |
| **No built-in cost tracking** | ADK has no token counting, cost estimation, or budgets |

## Ecosystem Maturity vs LangChain

| Dimension | Google ADK | LangChain |
|-----------|-----------|-----------|
| **Age** | 1 year (Apr 2025) | 3.5 years (Oct 2022) |
| **GitHub Stars** | ~30K | 96K+ |
| **Integrations** | Dozens | 600+ |
| **Production deployments** | Limited | 100K+ |
| **Community** | Growing | Massive |
| **Breaking changes** | Frequent (bi-weekly) | Rare (stable v1.x) |

## Known GitHub Issues

| Issue | Description |
|-------|-------------|
| [#53](https://github.com/google/adk-python/issues/53) | Sub-agents + built-in tools = "unsupported" error |
| [#701](https://github.com/google/adk-python/issues/701) | output_schema + tools incompatibility |
| [#1779](https://github.com/google/adk-python/issues/1779) | MCP Resources not supported |
| [#1900](https://github.com/google/adk-python/issues/1900) | Bearer token auth not accessible in tools |
| [#3413](https://github.com/google/adk-python/issues/3413) | output_schema + tools infinite loop |
| [#3628](https://github.com/google/adk-python/issues/3628) | Cannot use Gemini 3 with Agent Engine |
| [#3789](https://github.com/google/adk-python/issues/3789) | before_model_callback fails on Agent Engine |
| [#3828](https://github.com/google/adk-python/issues/3828) | Claude max_tokens hardcoded to 8192 |
| [#4323](https://github.com/google/adk-python/issues/4323) | 429 errors when triggering agents rapidly |
