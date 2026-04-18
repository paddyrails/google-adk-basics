# 3. Integration — Connecting, Serving, and Extending ADK Agents

## 1. Project Setup

**Recommended structure for `adk web` / `adk run`:**
```
parent_dir/                   # Run `adk web` FROM HERE
  my_agent/                   # Each subdirectory = one agent
    __init__.py               # Must exist
    agent.py                  # Must define `root_agent`
    .env                      # API keys (auto-loaded by CLI)
```

**CLI commands:**
```bash
adk create my_agent           # Scaffold a new agent
adk run my_agent              # Interactive terminal chat
adk web --port 8000           # Dev UI (browser)
adk api_server                # Headless REST API
```

## 2. Connecting to Different LLMs

| Provider | Model String | Extra Install | Env Var |
|----------|-------------|---------------|---------|
| **Gemini** | `"gemini-2.5-flash"` | None | `GOOGLE_API_KEY` |
| **OpenAI** | `LiteLlm(model="openai/gpt-4o")` | `pip install litellm` | `OPENAI_API_KEY` |
| **Claude** | `LiteLlm(model="anthropic/claude-3-haiku-20240307")` | `pip install litellm` | `ANTHROPIC_API_KEY` |
| **Ollama** | `LiteLlm(model="ollama_chat/gemma3:latest")` | `pip install litellm` | `OLLAMA_API_BASE` |

**Important:** For Ollama, use `ollama_chat/` prefix (NOT `ollama/`) to avoid infinite tool-call loops.

**Multi-model trees** — different agents can use different models:
```python
fast = LlmAgent(model="gemini-2.5-flash", name="fast", ...)
smart = LlmAgent(model=LiteLlm(model="openai/gpt-4o"), name="smart", ...)
coordinator = LlmAgent(model="gemini-2.5-flash", sub_agents=[fast, smart])
```

## 3. Tool Creation Patterns

### FunctionTool with ToolContext
```python
def my_tool(query: str, tool_context: ToolContext) -> dict:
    """Does something with the query.
    Args:
        query: The user's question.
    """
    tool_context.state["last_query"] = query                          # state access
    tool_context.actions.transfer_to_agent = "specialist"             # agent transfer
    tool_context.save_artifact("log.txt", types.Part(text=query))     # artifacts
    memories = tool_context.search_memory("preferences")              # memory
    return {"status": "ok"}
```
Do NOT document `tool_context` in docstring — it's auto-injected.

### OpenAPI Toolset
```python
from google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset import OpenAPIToolset
toolset = OpenAPIToolset(spec_str=open("petstore.json").read(), spec_str_type="json")
agent = LlmAgent(tools=[toolset])
```

### MCP Tools (stdio)
```python
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

agent = LlmAgent(tools=[
    McpToolset(connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(command='npx', args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]),
    ))
])
```

### MCP Tools (Streamable HTTP)
```python
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
agent = LlmAgent(tools=[
    McpToolset(connection_params=StreamableHTTPConnectionParams(url="https://server.example.com/mcp"))
])
```

## 4. Streaming

```python
async for event in runner.run_async(user_id="u1", session_id="s1", new_message=msg):
    if event.partial:                    # streaming chunk (state NOT committed)
        print(part.text, end="", flush=True)
    elif event.is_final_response():      # final response (state committed)
        print(event.content.parts[0].text)
```

- `partial=True` → intermediate token, skipped by Runner for state
- `turn_complete=True` → agent's turn finished, state applied atomically

## 5. Multimodal Inputs

```python
with open("photo.png", "rb") as f:
    image_bytes = f.read()

msg = types.Content(role="user", parts=[
    types.Part(text="What's in this image?"),
    types.Part(inline_data=types.Blob(mime_type="image/png", data=image_bytes)),
])
```

## 6. ADK Dev UI (`adk web`)

```bash
adk web --port 8000
```
Provides: agent selector, chat, session management, state inspector, event history, traces, artifact viewer.

**Dev only — NOT for production.**

## 7. FastAPI Integration

### Option A: Built-in `get_fast_api_app` (zero custom code)
```python
from google.adk.cli.fast_api import get_fast_api_app
app = get_fast_api_app(agents_dir=AGENT_DIR, web=False)
```

### Option B: Custom FastAPI (full control)
```python
runner = Runner(app_name="my_app", agent=root_agent, session_service=session_service)

@app.post("/chat")
async def chat(request: Request):
    async for event in runner.run_async(user_id=uid, session_id=sid, new_message=msg):
        if event.is_final_response():
            return {"response": event.content.parts[0].text}
```

## 8. A2A Protocol (Agent-to-Agent)

### Expose an agent as A2A server
```python
from google.adk.a2a.utils.agent_to_a2a import to_a2a
a2a_app = to_a2a(root_agent, port=8001)  # Starlette app
```

### Consume a remote A2A agent
```python
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
prime_agent = RemoteA2aAgent(name="prime", description="...", agent_card="http://localhost:8001/...")
coordinator = LlmAgent(sub_agents=[prime_agent])
```

**A2A is unique to ADK** — no other framework has native cross-framework agent interop.
