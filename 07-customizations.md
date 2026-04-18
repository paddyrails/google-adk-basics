# 7. Customizations — Tools, Prompts, State, Auth, Agent Config

## 1. Custom Tools with ToolContext
```python
async def my_tool(query: str, ctx: ToolContext) -> dict:
    ctx.state["last_query"] = query                    # State access
    ctx.state["user:lifetime_count"] = count + 1       # User-scoped state
    ctx.state["temp:scratch"] = "ephemeral"            # Gone after invocation
    version = await ctx.save_artifact("log.txt", part) # Artifacts
    memories = await ctx.search_memory("preferences")  # Memory
    ctx.actions.transfer_to_agent = "specialist"       # Agent transfer
    return {"status": "ok"}
```
Do NOT document `ctx` in docstring — it's auto-injected.

## 2. Prompt Tuning

| Approach | When to Use |
|----------|-------------|
| **Static string** `instruction="You are {role}"` | Simple, with `{placeholder}` from state |
| **Dynamic callable** `instruction=my_func` | Logic-based instruction generation |
| **`static_instruction`** | Large reference docs (enables context caching) |

```python
# Dynamic instruction
def adaptive_instruction(ctx: ReadonlyContext) -> str:
    tier = ctx.state.get("user:tier", "free")
    return f"You are an assistant. User tier: {tier}."

# Static instruction for caching (no {placeholder} support)
agent = LlmAgent(
    static_instruction="[10K tokens of reference docs...]",  # Cached
    instruction="Current context: {case_topic}",              # Dynamic
)
```

## 3. Agent Behaviors

| Setting | Effect |
|---------|--------|
| `include_contents="none"` | Stateless — no conversation history sent |
| `disallow_transfer_to_parent=True` | Agent can't hand control back |
| `disallow_transfer_to_peers=True` | Agent can't transfer to siblings |
| `output_key="result"` | Saves final text to `state["result"]` |

## 4. State Scoping

| Prefix | Scope | Persisted? |
|--------|-------|------------|
| *(none)* | Session | Yes (with DB service) |
| `user:` | User (all sessions) | Yes |
| `app:` | Application (all users) | Yes |
| `temp:` | Invocation only | Never |

## 5. Structured Output
```python
class Result(BaseModel):
    sentiment: str
    confidence: float
    themes: list[str]

agent = LlmAgent(output_schema=Result)  # Forces JSON. CANNOT use tools!
```
**Workaround for tools+schema:** Chain two agents — tool agent → formatting agent with `output_schema`.

## 6. Tool Authentication
```python
async def protected_tool(query: str, ctx: ToolContext) -> dict:
    cred = ctx.get_auth_response(oauth_config)
    if not cred:
        ctx.request_credential(oauth_config)  # Pauses execution
        return {"status": "pending_auth"}
    return call_api(query, cred)
```

## 7. Agent Config (YAML — No-Code)
```yaml
name: my_agent
model: gemini-2.5-flash
instruction: "You are a helpful assistant."
tools:
  - name: google_search
  - name: my_app.tools.custom_tool
sub_agents:
  - config_path: specialist.yaml
```
