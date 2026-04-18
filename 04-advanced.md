# 4. Advanced — Multi-Agent Systems, Orchestration, Callbacks, Planning

## 1. Multi-Agent Systems (Workflow Agents)

Workflow agents are **deterministic** orchestrators — no LLM decides the flow.

### SequentialAgent — Pipeline
Runs sub-agents in order. Data flows via **output_key → {placeholder}**.

```python
researcher = LlmAgent(name="researcher", output_key="research", ...)
writer = LlmAgent(name="writer", instruction="Write about: {research}", output_key="draft", ...)
editor = LlmAgent(name="editor", instruction="Edit: {draft}", ...)
pipeline = SequentialAgent(name="pipeline", sub_agents=[researcher, writer, editor])
```

### ParallelAgent — Fan-Out
Runs sub-agents concurrently. Each writes to a **unique state key** (avoid race conditions).

```python
sentiment = LlmAgent(name="sentiment", output_key="sentiment_result", ...)
topics = LlmAgent(name="topics", output_key="topics_result", ...)
parallel = ParallelAgent(name="analysis", sub_agents=[sentiment, topics])
```

### LoopAgent — Iterate Until Done
Loops sub-agents until `exit_loop` is called or `max_iterations` reached.

```python
from google.adk.tools import exit_loop
generator = LlmAgent(name="gen", output_key="code", ...)
critic = LlmAgent(name="critic", tools=[exit_loop], output_key="feedback", ...)
loop = LoopAgent(name="refine", sub_agents=[generator, critic], max_iterations=5)
```

## 2. Orchestration Patterns

| Pattern | Mechanism | Control | Use Case |
|---------|-----------|---------|----------|
| **LLM-driven routing** | `sub_agents` on parent | LLM decides | Customer support triage |
| **AgentTool** | Wrap agent as tool | Parent retains control | Summarize → Translate chain |
| **Programmatic transfer** | `tool_context.actions.transfer_to_agent` | Code decides | Rule-based routing |
| **Escalation** | `tool_context.actions.escalate = True` | Bubble up | Loop exit, tier escalation |

### LLM-Driven Routing
```python
coordinator = LlmAgent(
    name="coordinator",
    instruction="Route to billing_agent or tech_agent based on the query.",
    sub_agents=[billing_agent, tech_agent],  # ADK auto-generates transfer_to_agent tool
)
```

### AgentTool (Parent Retains Control)
```python
from google.adk.tools import AgentTool
coordinator = LlmAgent(
    tools=[AgentTool(agent=summarizer), AgentTool(agent=translator)],
)
# Sub-agent output comes back as tool result — parent can chain them
```

### Programmatic Transfer
```python
def route(query: str, tool_context: ToolContext) -> dict:
    if "billing" in query.lower():
        tool_context.actions.transfer_to_agent = "billing_agent"
    return {"status": "routed"}
```

## 3. Custom Agents

Extend `BaseAgent` for deterministic, non-LLM orchestration:

```python
class ConditionalRouter(BaseAgent):
    route_map: dict[str, str] = {}

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        route = ctx.session.state.get("route", "")
        target = self.find_sub_agent(self.route_map.get(route, ""))
        if target:
            async for event in target.run_async(ctx):
                yield event
```

## 4. Callbacks (v1.31 Signatures)

| Hook | Signature | Return to Skip |
|------|-----------|----------------|
| `before_model` | `(callback_context, llm_request, **kwargs)` | `LlmResponse` |
| `after_model` | `(callback_context, llm_response, **kwargs)` | `LlmResponse` |
| `before_tool` | `(tool, args, tool_context, **kwargs)` | `dict` |
| `after_tool` | `(tool, args, tool_context, tool_response, **kwargs)` | `dict` |
| `before_agent` | `(callback_context)` | `types.Content` |
| `after_agent` | `(callback_context)` | `types.Content` |

**Rule:** Return `None` = proceed normally. Return a value = skip/replace.

Callbacks accept **lists** — execute in order, first non-None return wins:
```python
agent = LlmAgent(before_model_callback=[rate_limiter, pii_guard, cache_check])
```

## 5. Planning / Extended Thinking

### BuiltInPlanner (Gemini Thinking Mode)
```python
from google.adk.planners import BuiltInPlanner
agent = LlmAgent(
    planner=BuiltInPlanner(thinking_config=types.ThinkingConfig(
        include_thoughts=True, thinking_budget=2048
    ))
)
```

### PlanReActPlanner (Model-Agnostic)
```python
from google.adk.planners import PlanReActPlanner
agent = LlmAgent(planner=PlanReActPlanner())  # Works with any model
```

## 6. Structured Output

```python
class Result(BaseModel):
    sentiment: str
    confidence: float
    themes: list[str]

agent = LlmAgent(output_schema=Result)  # Forces JSON output. CANNOT use tools!
```

## 7. Agentic Patterns Summary

| Pattern | ADK Implementation |
|---------|-------------------|
| **Pipeline** | SequentialAgent |
| **Fan-out / Fan-in** | ParallelAgent → SequentialAgent with aggregator |
| **Self-correction** | LoopAgent (generator + critic + exit_loop) |
| **Escalation tiers** | Nested sub_agents (L1 → L2 → L3) |
| **ReAct** | LlmAgent + PlanReActPlanner |
| **Tool chaining** | SequentialAgent with output_key flow |
| **Router** | LlmAgent with sub_agents (LLM decides) or CustomAgent (code decides) |
