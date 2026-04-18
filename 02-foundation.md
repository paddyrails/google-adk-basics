# 2. Google ADK Core Concepts -- Deep Dive

---

## 1. Agents in Detail

### LlmAgent Constructor Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `name` | Yes | Unique string identifier. Crucial in multi-agent systems for routing. Avoid `"user"` (reserved). |
| `model` | Yes | LLM identifier string (e.g., `"gemini-flash-latest"`) or model wrapper object (e.g., `LiteLlm(...)`) |
| `instruction` | No | String or callable (`ReadonlyContext -> str`) defining persona, task, constraints, tool-use guidance |
| `description` | No (Recommended) | Concise summary of capabilities -- used by **other agents** to decide routing/delegation |
| `tools` | No | List of tools: Python functions, `BaseTool` instances, `AgentTool` wrappers |
| `sub_agents` | No | List of child `BaseAgent` instances forming the agent tree |
| `generate_content_config` | No | `types.GenerateContentConfig` -- controls temperature, max_output_tokens, top_p, top_k, safety settings, retry |
| `input_schema` | No | Pydantic `BaseModel` (Python) / Zod schema (TS) -- enforces structure on user messages |
| `output_schema` | No | Pydantic `BaseModel` -- enforces JSON output structure. **Incompatible with tools on most models** |
| `output_key` | No | State key where the agent's final text response is auto-saved |
| `include_contents` | No | `'default'` (include conversation history) or `'none'` (stateless, no history) |
| `planner` | No | `BasePlanner` instance for multi-step reasoning |
| `code_executor` | No | `BaseCodeExecutor` instance enabling code execution from LLM responses |
| `before_agent_callback` | No | Called before agent logic runs |
| `after_agent_callback` | No | Called after agent logic completes |
| `before_model_callback` | No | Called before each LLM call |
| `after_model_callback` | No | Called after each LLM response |
| `before_tool_callback` | No | Called before each tool execution |
| `after_tool_callback` | No | Called after each tool execution |

### System Instructions

Instructions define the agent's behavior and are passed to the LLM as system-level context. They support:

**Static strings:**
```python
agent = LlmAgent(
    model="gemini-flash-latest",
    name="weather_agent",
    instruction="You are a weather assistant. Use the get_weather tool for queries."
)
```

**Template variables** -- `{var}` is replaced from session state at runtime:
```python
agent = LlmAgent(
    instruction="You are helping {user:name}. Their preferred language is {user:preferred_language}."
)
```
- Use `{var?}` (trailing `?`) to silently skip undefined variables instead of raising an error.
- For literal braces in instructions (e.g., JSON examples), use a callable `InstructionProvider` instead.

**Dynamic instruction providers:**
```python
def my_instruction(context: ReadonlyContext) -> str:
    user = context.state.get("user:name", "friend")
    return f'Help {user}. Format as JSON: {{"result": "<answer>"}}'

agent = LlmAgent(instruction=my_instruction)
```

### The Agent Loop (Non-Deterministic)

Unlike workflow agents, `LlmAgent` is **non-deterministic** -- the LLM decides what to do at each step. The loop:

```
┌─────────────────────────────────────────┐
│  1. THINK  -- LLM receives:            │
│     - System instruction               │
│     - Conversation history (events)     │
│     - Available tool declarations       │
│     - User's latest message             │
│                                         │
│  2. DECIDE -- LLM outputs one of:      │
│     a) Text response  --> yield Event   │
│     b) Function call   --> execute tool │
│     c) Transfer signal --> hand off     │
│                                         │
│  3. ACT (if function call):             │
│     - Framework executes the tool       │
│     - Tool result wrapped in Event      │
│     - Result sent back to LLM          │
│                                         │
│  4. OBSERVE -- loop back to step 1     │
│     with tool result in context         │
└─────────────────────────────────────────┘
```

The loop continues until the LLM produces a **final text response** (no more tool calls). Each iteration yields Events to the Runner.

### Transfer of Control Between Agents

Three mechanisms:

**1. LLM-driven transfer (`transfer_to_agent`):**
The parent LLM generates a special function call `transfer_to_agent(agent_name="target")`. The `AutoFlow` framework intercepts this, locates the target agent via `root_agent.find_agent()`, and switches `InvocationContext` to the new agent.

**2. Explicit invocation via `AgentTool`:**
```python
from google.adk.tools import agent_tool

specialist = LlmAgent(name="specialist", ...)
parent = LlmAgent(
    name="coordinator",
    tools=[agent_tool.AgentTool(agent=specialist)]
)
```
The specialist runs as a tool call -- its final response becomes the tool result returned to the parent.

**3. Programmatic transfer via `ToolContext.actions`:**
```python
def check_and_route(query: str, tool_context: ToolContext) -> str:
    if "billing" in query.lower():
        tool_context.actions.transfer_to_agent = "billing_agent"
        return "Transferring to billing..."
    return "Handled normally."
```

**4. Escalation:**
A sub-agent can set `EventActions(escalate=True)` to signal it cannot handle the request and pass control back to its parent.

### Workflow Agents (Deterministic Orchestrators)

| Agent | Behavior |
|-------|----------|
| `SequentialAgent` | Runs `sub_agents` in listed order. State shared via `InvocationContext`. |
| `ParallelAgent` | Runs `sub_agents` concurrently. Each gets a unique `branch` in context. |
| `LoopAgent` | Runs `sub_agents` sequentially in a loop until `max_iterations` or `escalate=True`. |

### Planners

| Planner | Description |
|---------|-------------|
| `BuiltInPlanner` | Uses model's native thinking (e.g., Gemini thinking). Configurable `thinking_budget` and `include_thoughts`. |
| `PlanReActPlanner` | For models without built-in thinking. Structures output as: `/*PLANNING*/` then `/*ACTION*/` then `/*REASONING*/` then `/*FINAL_ANSWER*/`. |

---

## 2. Tools in Detail

### Tool Categories

| Category | Examples |
|----------|----------|
| **FunctionTool** | Wraps a Python function with type hints and docstring |
| **Built-in tools** | `google_search`, `code_execution` |
| **OpenAPI tools** | Auto-generated from OpenAPI v3.x specs |
| **MCP tools** | Connected via Model Context Protocol servers |
| **AgentTool** | Wraps another agent as a callable tool |
| **Long-running tools** | Async operations with extended execution times |

### FunctionTool -- Creation and Conventions

```python
from google.adk.tools import FunctionTool

def get_weather(city: str) -> dict:
    """Retrieves current weather for a specified city.

    Args:
        city: The name of the city to look up.

    Returns:
        dict with 'status' and 'report' or 'error_message'.
    """
    if city.lower() == "london":
        return {"status": "success", "report": "Cloudy, 18C"}
    return {"status": "error", "error_message": f"No data for {city}"}

weather_tool = FunctionTool(func=get_weather)
```

Key rules:
- **Docstrings are critical** -- the LLM uses them to decide when/how to call the tool.
- **Type hints are required** -- they generate the function declaration schema.
- **Do NOT document `ToolContext`** in the docstring -- it is auto-injected by the framework.
- **Return `dict`** -- the result is sent back to the LLM as a function response.

### Built-in Tools

```python
from google.adk.tools import google_search, code_execution

agent = LlmAgent(
    model="gemini-flash-latest",
    name="researcher",
    tools=[google_search, code_execution]
)
```
- `google_search` -- grounded web search via Google Search.
- `code_execution` -- sandboxed code execution; the LLM generates code, the executor runs it, and the result is returned.

### OpenAPI Tools

```python
from google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset import OpenAPIToolset

toolset = OpenAPIToolset(
    spec_str=open("petstore.json").read(),
    spec_str_type="json"
)

# Each operationId becomes a RestApiTool
# Tool names: operationId -> snake_case (max 60 chars)

agent = LlmAgent(
    name="api_agent",
    model="gemini-flash-latest",
    tools=[toolset]  # pass the entire toolset
)
```

**Authentication** is configured globally at `OpenAPIToolset` initialization via `auth_scheme` and `auth_credential` parameters, automatically applied to all generated `RestApiTool` instances.

### MCP Tools

ADK can consume tools from external MCP servers:
```python
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, SseServerParams

mcp_tools = MCPToolset(
    connection_params=SseServerParams(url="http://localhost:3001/sse")
)

agent = LlmAgent(
    name="mcp_agent",
    tools=[mcp_tools]
)
```

### How Tool Calls Flow Through the System

```
1. LLM generates function_call in response
   └── Event with content.parts[].function_call = {name, args}
       └── Runner yields this Event upstream (for UI visibility)

2. Framework locates the matching tool by name

3. before_tool_callback fires (if set)
   └── Returns None -> proceed | Returns dict -> skip tool, use this result

4. Tool function executes
   └── ToolContext injected automatically if parameter exists
   └── Tool accesses state, artifacts, memory via ToolContext

5. after_tool_callback fires (if set)
   └── Returns None -> use original result | Returns dict -> replace result

6. Result wrapped as function_response Event
   └── Event with content.parts[].function_response = {name, response}

7. function_response Event sent back to LLM as context

8. LLM decides: generate another tool call or produce final text
```

### Tool Authentication

Inside a tool function, authentication follows this pattern:

```python
def call_protected_api(query: str, tool_context: ToolContext) -> dict:
    # 1. Check for existing credentials
    cred = tool_context.state.get("user:api_credential")
    if cred:
        return make_api_call(query, cred)

    # 2. Check if auth response is available (from prior turn)
    auth = tool_context.get_auth_response(auth_config)
    if auth:
        tool_context.state["user:api_credential"] = auth.model_dump()
        return make_api_call(query, auth)

    # 3. Request credentials -- execution stops here for this turn
    tool_context.request_credential(auth_config)
    return {"status": "pending", "message": "Authentication required"}
```

---

## 3. Sessions

### Session Object Structure

| Field | Description |
|-------|-------------|
| `id` | Unique session identifier |
| `app_name` | Application that owns this session |
| `user_id` | User this session belongs to |
| `events` | Chronological list of all `Event` objects |
| `state` | Key-value dict (session + user + app state merged) |
| `last_update_time` | Timestamp of the last event |

### Session Lifecycle

```
1. CREATE:   session = await session_service.create_session(app_name, user_id, state={...})
2. RETRIEVE: session = await session_service.get_session(app_name, user_id, session_id)
3. USE:      Runner obtains session, passes to agent via InvocationContext
4. UPDATE:   Agent yields Events -> Runner calls session_service.append_event(session, event)
             -> state_delta merged into session.state, event appended to history
5. LIST:     sessions = await session_service.list_sessions(app_name, user_id)
6. DELETE:   await session_service.delete_session(app_name, user_id, session_id)
```

### SessionService Implementations

**InMemorySessionService** -- RAM only, no persistence:
```python
from google.adk.sessions import InMemorySessionService
session_service = InMemorySessionService()
```

**DatabaseSessionService** -- persistent via SQLAlchemy async:
```python
from google.adk.sessions import DatabaseSessionService

# SQLite (must use aiosqlite driver)
session_service = DatabaseSessionService(db_url="sqlite+aiosqlite:///./agent.db")

# PostgreSQL
session_service = DatabaseSessionService(db_url="postgresql+asyncpg://user:pass@host/db")
```
Creates tables: `sessions`, `raw_events`, `app_state`, `user_state`.

**VertexAiSessionService** -- managed Google Cloud:
```python
from google.adk.sessions import VertexAiSessionService
session_service = VertexAiSessionService(project="my-project", location="us-central1")
```

### State Scoping with Prefixes

| Prefix | Scope | Persistence | Shared Across |
|--------|-------|-------------|---------------|
| *(none)* | Session | With DB/Vertex service | This session only |
| `user:` | User | With DB/Vertex service | All sessions for this user |
| `app:` | Application | With DB/Vertex service | All users and sessions |
| `temp:` | Invocation | **Never** (discarded after invocation) | Parent + sub-agents in same invocation |

### How State Flows Between Agents

- All agents in the same invocation share the **same `InvocationContext`** and thus the same `Session` object.
- Sub-agents can read state set by the parent or siblings.
- `output_key` on an agent auto-saves its final text response to state, making it available to downstream agents:

```python
agent_a = LlmAgent(name="Researcher", output_key="research_result", ...)
agent_b = LlmAgent(name="Writer", instruction="Write about: {research_result}", ...)
pipeline = SequentialAgent(sub_agents=[agent_a, agent_b])
```

- **Critical rule:** Never modify `session.state` directly. Always use `context.state[key] = value` (in callbacks/tools) or `EventActions(state_delta={...})` to ensure changes are tracked, persisted, and thread-safe.

---

## 4. Memory

### MemoryService Interface

```python
class BaseMemoryService:
    async def add_session_to_memory(self, session: Session) -> None:
        """Ingest a completed session's content into long-term memory."""

    async def search_memory(self, *, app_name, user_id, query) -> SearchMemoryResponse:
        """Search long-term memory. Returns list of MemoryResult objects."""
```

### Implementations

**InMemoryMemoryService** -- basic keyword matching, no persistence:
```python
from google.adk.memory import InMemoryMemoryService
memory_service = InMemoryMemoryService()
```

**VertexAiMemoryBankService** -- persistent, LLM-powered consolidation, semantic search:
```python
from google.adk.memory import VertexAiMemoryBankService

memory_service = VertexAiMemoryBankService(
    project="PROJECT_ID",
    location="us-central1",
    agent_engine_id="your-engine-id"
)
```
Requires: Vertex AI API enabled, Agent Engine instance, `gcloud auth`.

### Memory Tools

| Tool | Behavior |
|------|----------|
| `PreloadMemoryTool` | **Automatic.** Retrieves relevant memories at the start of each turn and injects them into the system instruction. Good for baseline user context. |
| `LoadMemoryTool` | **On-demand.** The LLM decides when to call it. Good for selective retrieval when the agent recognizes it needs context. |

```python
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.adk.tools.load_memory_tool import LoadMemoryTool

# Auto-preload approach
agent = LlmAgent(tools=[PreloadMemoryTool()])

# On-demand approach
agent = LlmAgent(tools=[LoadMemoryTool()])
```

### Memory Workflow

```
1. User interacts with agent via Session
2. Session ends -> app calls: await memory_service.add_session_to_memory(session)
3. MemoryService extracts and consolidates information
   - New info is merged with existing memories
   - Contradictory info updates/replaces old memories
4. Next session: agent uses PreloadMemoryTool or LoadMemoryTool
5. Tool calls memory_service.search_memory(query) -> SearchMemoryResponse with MemoryResult list
```

### Saving Memory via Callback

```python
async def save_memory_callback(callback_context: CallbackContext):
    await callback_context._invocation_context.memory_service.add_session_to_memory(
        callback_context._invocation_context.session
    )

agent = LlmAgent(after_agent_callback=save_memory_callback)
```

### Memory Search in Tools

```python
def my_tool(query: str, tool_context: ToolContext) -> dict:
    results = tool_context.search_memory("user preferences")
    return {"memories": [r.text for r in results.memories]}
```

---

## 5. Models

### Model Configuration

Every `LlmAgent` requires a `model` parameter. Two integration approaches:

**1. String identifier (Google-native models):**
```python
agent = LlmAgent(model="gemini-flash-latest", ...)   # Latest stable Flash
agent = LlmAgent(model="gemini-2.0-flash", ...)       # Specific version
```

**2. Model wrapper object (third-party models):**
```python
from google.adk.models.lite_llm import LiteLlm

agent = LlmAgent(model=LiteLlm(model="openai/gpt-4o"), ...)
agent = LlmAgent(model=LiteLlm(model="anthropic/claude-3-haiku-20240307"), ...)
```

### Gemini Authentication Options

| Method | Environment Variables | Use Case |
|--------|----------------------|----------|
| Google AI Studio | `GOOGLE_API_KEY`, `GOOGLE_GENAI_USE_VERTEXAI=FALSE` | Quick prototyping |
| Vertex AI (user creds) | `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `GOOGLE_GENAI_USE_VERTEXAI=TRUE` | Local dev |
| Vertex AI (Express) | `GOOGLE_GENAI_API_KEY`, `GOOGLE_GENAI_USE_VERTEXAI=TRUE` | Simplified Vertex |
| Service Account | `GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json`, `GOOGLE_GENAI_USE_VERTEXAI=TRUE` | Production |

### generate_content_config

```python
from google.genai import types

agent = LlmAgent(
    model="gemini-flash-latest",
    generate_content_config=types.GenerateContentConfig(
        temperature=0.7,
        max_output_tokens=2048,
        top_p=0.95,
        top_k=40,
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(
                initial_delay=1,
                attempts=2
            )
        )
    )
)
```

### LiteLLM Adapter

```python
from google.adk.models.lite_llm import LiteLlm

# Provides standardized OpenAI-compatible interface to 100+ models
agent_openai = LlmAgent(model=LiteLlm(model="openai/gpt-4o"), name="gpt_agent", ...)
agent_claude = LlmAgent(model=LiteLlm(model="anthropic/claude-3-haiku-20240307"), ...)
agent_local = LlmAgent(model=LiteLlm(model="ollama/llama3"), ...)  # Local via Ollama
```

Requires `pip install litellm` and appropriate API keys set as environment variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.).

### Interactions API (Gemini Stateful)

```python
from google.adk.models.google_llm import Gemini

agent = LlmAgent(
    model=Gemini(model="gemini-flash-latest", use_interactions_api=True),
    name="stateful_agent"
)
```
Limitation: Cannot mix custom function tools with built-in tools unless `bypass_multi_tools_limit=True`.

### Multi-Model Agent Trees

Different agents in the same tree can use different models:
```python
fast_agent = LlmAgent(model="gemini-flash-latest", name="fast", ...)
smart_agent = LlmAgent(model=LiteLlm(model="openai/gpt-4o"), name="smart", ...)
coordinator = LlmAgent(model="gemini-flash-latest", sub_agents=[fast_agent, smart_agent])
```

---

## 6. Runner

### Runner Architecture

The Runner is the **execution engine** that sits between your application code and the agent hierarchy. It manages message flow, state persistence, and service coordination.

### Constructor

```python
from google.adk.runners import Runner

runner = Runner(
    agent=root_agent,               # BaseAgent -- the root of your agent tree
    app_name="my_app",              # Application identifier
    session_service=session_service, # BaseSessionService implementation
    artifact_service=artifact_service, # Optional: BaseArtifactService
    memory_service=memory_service,   # Optional: BaseMemoryService
)
```

### InMemoryRunner (Convenience Wrapper)

```python
from google.adk.runners import InMemoryRunner

runner = InMemoryRunner(agent=root_agent)
# Internally creates:
#   session_service = InMemorySessionService()
#   artifact_service = InMemoryArtifactService()
```
Perfect for prototyping. No persistence -- all data lost on restart.

### run_async -- Primary Entry Point

```python
async for event in runner.run_async(
    user_id="user123",
    session_id="session456",
    new_message=types.Content(
        role="user",
        parts=[types.Part.from_text("What's the weather in London?")]
    )
):
    if event.is_final_response():
        print(event.content.parts[0].text)
```

Returns an `AsyncGenerator[Event, None]` -- yields events as they are produced.

### Execution Pipeline (8 Steps)

```
1. SESSION RETRIEVAL    -- SessionService.get_session(user_id, session_id)
2. MESSAGE INGESTION    -- Append user message as Event(author='user') to session
3. AGENT SELECTION      -- Determine which agent to run (root or last active)
4. CONTEXT ASSEMBLY     -- Build InvocationContext with session, services, config
5. AGENT INVOCATION     -- Call agent.run_async(invocation_context)
6. EVENT PROCESSING     -- Agent yields Events; Runner processes each:
                           a) Merge state_delta into session.state
                           b) Process artifact_delta
                           c) Append event to session history
7. EVENT STREAMING      -- Yield processed events to the caller
8. SESSION PERSISTENCE  -- Only non-partial events are persisted
```

### The Yield/Resume Cycle

```
Agent Logic                              Runner
    │                                        │
    ├── Determines action needed             │
    ├── Constructs Event object              │
    ├── yield event ─────────────────────>   │
    │   (PAUSES immediately)                 ├── Receives event
    │                                        ├── Calls SessionService.append_event()
    │                                        ├── Merges state_delta
    │                                        ├── Yields event upstream (to UI)
    │   <──────────────────── resume ────────┤
    ├── Continues from next statement        │
    │   (committed state now visible)        │
    │                                        │
```

### Streaming Behavior

- **Partial events** (`partial=True`): yielded for token-by-token display, but the Runner **skips processing their `actions`** (no state commits).
- **Final events** (`partial=False` or `turn_complete=True`): fully processed, state changes applied atomically.
- This enables progressive UI display without inconsistent state.

### Synchronous Wrapper

```python
for event in runner.run(user_id="u1", session_id="s1", new_message=msg):
    print(event)
```
Internally delegates to `run_async` using threads/asyncio. Use `run_async` in production for performance.

---

## 7. Callbacks

### Overview

Callbacks hook into **six points** in the agent execution lifecycle:

```
before_agent  -->  [Agent Logic]  -->  after_agent
                       │
               before_model  -->  [LLM Call]  -->  after_model
                       │
               before_tool   -->  [Tool Exec] -->  after_tool
```

### Return Value Contract

**Universal rule:**
- `before_*` returns `None` --> proceed normally
- `before_*` returns a value --> **skip** the next step, use the returned value instead
- `after_*` returns `None` --> use the original result
- `after_*` returns a value --> **replace** the original result

### before_model_callback

```python
def before_model_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest
) -> Optional[LlmResponse]:
```

- **Receives:** `CallbackContext` + the full `LlmRequest` (contents, config, system instruction)
- **Can modify:** `llm_request.contents`, `llm_request.config` in-place before the LLM call
- **Returns `None`:** modified request proceeds to LLM
- **Returns `LlmResponse`:** LLM call is **skipped entirely**; returned response used as-if from LLM
- **Use cases:** input guardrails, prompt injection detection, request caching, dynamic few-shot injection

```python
def safety_guardrail(callback_context, llm_request):
    user_text = llm_request.contents[-1].parts[0].text
    if contains_profanity(user_text):
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part.from_text("I can't process that request.")]
            )
        )
    return None  # proceed to LLM
```

### after_model_callback

```python
def after_model_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse
) -> Optional[LlmResponse]:
```

- **Receives:** the LLM's response
- **Returns `None`:** original response used
- **Returns `LlmResponse`:** replaces the LLM's response
- **Use cases:** output sanitization, PII removal, adding disclaimers, response caching

### before_tool_callback

```python
def before_tool_callback(
    callback_context: CallbackContext,
    tool_call: ToolCall
) -> Optional[dict]:
```

- **Receives:** the tool call details (name, args)
- **Returns `None`:** tool executes normally
- **Returns `dict`:** tool execution is **skipped**; returned dict used as the tool result
- **Use cases:** argument validation, permission checks, cached results, mocking in tests

```python
def validate_tool_args(callback_context, tool_call):
    if tool_call.name == "delete_record" and not callback_context.state.get("user:is_admin"):
        return {"error": "Permission denied. Admin access required."}
    return None  # proceed with tool execution
```

### after_tool_callback

```python
def after_tool_callback(
    callback_context: CallbackContext,
    tool_call_result: ToolCallResult
) -> Optional[dict]:
```

- **Receives:** the tool's result
- **Returns `None`:** original result used
- **Returns `dict`:** replaces the tool result sent to the LLM
- **Use cases:** result filtering, enrichment, logging, PII redaction

### before_agent_callback / after_agent_callback

```python
def before_agent_callback(callback_context: CallbackContext) -> Optional[types.Content]:
def after_agent_callback(callback_context: CallbackContext) -> Optional[types.Content]:
```

- `before_agent` returning `Content` --> agent logic is skipped entirely
- `after_agent` returning `Content` --> replaces/augments agent output
- `after_agent` does NOT fire if `before_agent` skipped the agent or `end_invocation` was set

---

## 8. Context Objects

### Inheritance Hierarchy

```
ReadonlyContext (base -- read-only state)
    └── CallbackContext (adds mutable state + artifacts)
        └── ToolContext (adds auth, memory, actions, function_call_id)

InvocationContext (separate -- comprehensive internal container)
```

### ReadonlyContext

Available in: instruction providers (dynamic instructions)

| Property | Type | Description |
|----------|------|-------------|
| `invocation_id` | `str` | Unique ID for this request-response cycle |
| `agent_name` | `str` | Name of the currently executing agent |
| `state` | `MappingProxyType` | **Read-only** view of session state |

### CallbackContext

Available in: all callbacks (`before_agent`, `after_agent`, `before_model`, `after_model`, `before_tool`, `after_tool`)

| Property/Method | Description |
|-----------------|-------------|
| `invocation_id` | Inherited from ReadonlyContext |
| `agent_name` | Inherited from ReadonlyContext |
| `state` | **Mutable** dict -- writes automatically tracked in `EventActions.state_delta` |
| `user_content` | The initial user message for this invocation |
| `load_artifact(filename)` | Retrieve a stored artifact |
| `save_artifact(filename, part)` | Store an artifact, returns version number |

```python
def my_callback(callback_context: CallbackContext):
    # Read state
    count = callback_context.state.get("call_count", 0)
    # Write state (automatically tracked)
    callback_context.state["call_count"] = count + 1
    # Access artifacts
    doc = callback_context.load_artifact("report.pdf")
```

### ToolContext

Available in: tool functions (when parameter is declared)

Inherits everything from `CallbackContext`, plus:

| Property/Method | Description |
|-----------------|-------------|
| `function_call_id` | Unique ID of the specific LLM function call that triggered this tool |
| `function_call_event_id` | Event ID containing the function call |
| `actions` | Direct access to `EventActions` (state_delta, transfer_to_agent, escalate, skip_summarization) |
| `auth_response` | Credentials from a completed auth flow |
| `request_credential(auth_config)` | Initiate an authentication flow (stops tool execution for this turn) |
| `get_auth_response(auth_config)` | Retrieve credentials from a prior auth flow |
| `search_memory(query)` | Query the configured memory service |
| `list_artifacts()` | Discover all available artifact keys |

```python
def my_tool(query: str, tool_context: ToolContext) -> dict:
    # State access (mutable)
    tool_context.state["last_query"] = query

    # Control flow
    tool_context.actions.transfer_to_agent = "specialist_agent"
    tool_context.actions.skip_summarization = True

    # Memory
    memories = tool_context.search_memory("user preferences")

    # Artifacts
    keys = tool_context.list_artifacts()
    doc = tool_context.load_artifact("data.csv")
    version = tool_context.save_artifact("result.txt", types.Part.from_text("done"))

    # Authentication
    cred = tool_context.get_auth_response(oauth_config)

    return {"status": "ok"}
```

### InvocationContext

Available in: agent core methods (`_run_async_impl`, `_run_live_impl`). Created by the framework -- you do not instantiate it directly.

| Property | Description |
|----------|-------------|
| `session` | Full `Session` object (events, state, metadata) |
| `agent` | Reference to the currently executing agent instance |
| `invocation_id` | Unique invocation identifier |
| `user_content` | Initial user input |
| `session_service` | Configured `BaseSessionService` |
| `artifact_service` | Configured `BaseArtifactService` |
| `memory_service` | Configured `BaseMemoryService` |
| `branch` | Current branch path (set by `ParallelAgent`) |
| `end_invocation` | Boolean -- set to `True` to stop the invocation |

---

## 9. Events

### Event Class Structure

`Event` extends `LlmResponse` with ADK metadata:

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique event identifier (assigned by SessionService) |
| `invocation_id` | `str` | ID of the invocation this event belongs to |
| `author` | `str` | `'user'` or the agent's name |
| `timestamp` | `float` | Creation timestamp |
| `content` | `Content` | Optional -- contains `parts` (text, function_call, function_response) |
| `partial` | `bool` | `True` for streaming intermediate chunks |
| `actions` | `EventActions` | Side effects and control signals |
| `turn_complete` | `bool` | Indicates the agent's turn is finished |
| `error_code` | `str` | Error code if something failed |
| `error_message` | `str` | Error description |
| `long_running_tool_ids` | `list` | IDs of async tools still running |
| `branch` | `str` | Branch path (for parallel execution) |

### Content Parts

Events carry content via `content.parts[]`, which can contain:

```python
# Text
event.content.parts[0].text  # "Hello, how can I help?"

# Function call (LLM wants to call a tool)
event.content.parts[0].function_call.name  # "get_weather"
event.content.parts[0].function_call.args  # {"city": "London"}

# Function response (tool result sent back to LLM)
event.content.parts[0].function_response.name      # "get_weather"
event.content.parts[0].function_response.response   # {"status": "success", "report": "..."}
```

Helper methods:
```python
event.get_function_calls()      # List of function_call objects
event.get_function_responses()  # List of function_response objects
event.is_final_response()       # True if this is the final user-facing response
```

### EventActions

| Field | Type | Description |
|-------|------|-------------|
| `state_delta` | `dict` | Key-value pairs to merge into session state |
| `artifact_delta` | `dict` | Artifact keys and version numbers saved |
| `transfer_to_agent` | `str` | Target agent name to transfer control to |
| `escalate` | `bool` | Signal to terminate loop / pass control to parent |
| `skip_summarization` | `bool` | If `True`, tool result is sent directly to user without LLM processing |

### How Events Flow Through the System

```
User Input
    │
    ▼
Runner wraps as Event(author='user')
    │
    ▼
Runner appends to session via SessionService
    │
    ▼
Runner calls agent.run_async(InvocationContext)
    │
    ▼
Agent processes, calls LLM
    │
    ├── LLM returns text ──> Agent yields Event(author=agent.name, content=text)
    │                              │
    │                              ▼
    │                         Runner receives, processes:
    │                           - merge state_delta
    │                           - process artifact_delta
    │                           - append to session history
    │                           - yield upstream to caller
    │
    ├── LLM returns function_call ──> Agent yields Event with function_call
    │                                      │
    │                                      ▼
    │                                 Runner yields upstream (UI shows tool call)
    │                                      │
    │                                      ▼
    │                                 Agent executes tool
    │                                      │
    │                                      ▼
    │                                 Agent yields Event with function_response
    │                                      │
    │                                      ▼
    │                                 Runner processes, yields upstream
    │                                      │
    │                                      ▼
    │                                 function_response sent to LLM (loop back)
    │
    └── LLM returns transfer_to_agent ──> AutoFlow switches InvocationContext
                                              to target agent, loop continues
```

### Detecting Final Response

```python
async for event in runner.run_async(user_id=uid, session_id=sid, new_message=msg):
    # is_final_response() returns True when:
    # 1. Tool result with skip_summarization=True
    # 2. Long-running tool call (long_running_tool_ids not empty)
    # 3. Complete text message (no tool calls, partial=False)
    if event.is_final_response():
        final_text = event.content.parts[0].text
```

---

## Quick Reference -- What Goes Where

| I want to... | Use this |
|--------------|----------|
| Define agent behavior | `instruction` parameter |
| Control LLM generation | `generate_content_config` |
| Save agent output to state | `output_key` |
| Give agent capabilities | `tools` list |
| Build agent hierarchy | `sub_agents` list |
| Intercept before LLM call | `before_model_callback` |
| Modify LLM response | `after_model_callback` |
| Validate tool args | `before_tool_callback` |
| Modify tool results | `after_tool_callback` |
| Access state in tools | `tool_context.state` |
| Transfer to another agent | `tool_context.actions.transfer_to_agent` |
| Search long-term memory | `tool_context.search_memory(query)` |
| Store files/data | `context.save_artifact(name, part)` |
| Persist sessions | `DatabaseSessionService` or `VertexAiSessionService` |
| Use non-Google models | `LiteLlm(model="provider/model")` |

---

Sources:
- [LLM Agents](https://adk.dev/agents/llm-agents/)
- [Multi-Agent Systems](https://adk.dev/agents/multi-agents/)
- [Custom Tools](https://adk.dev/tools-custom/)
- [OpenAPI Tools](https://adk.dev/tools-custom/openapi-tools/)
- [Sessions](https://adk.dev/sessions/session/)
- [State](https://adk.dev/sessions/state/)
- [Memory](https://adk.dev/sessions/memory/)
- [Models](https://adk.dev/agents/models/)
- [Gemini Integration](https://adk.dev/agents/models/google-gemini/)
- [LiteLLM Integration](https://adk.dev/agents/models/litellm/)
- [Runtime](https://adk.dev/runtime/)
- [Event Loop](https://adk.dev/runtime/event-loop/)
- [Events](https://adk.dev/events/)
- [Callbacks](https://adk.dev/callbacks/)
- [Callback Types](https://adk.dev/callbacks/types-of-callbacks/)
- [Context](https://adk.dev/context/)
- [ADK Python GitHub](https://github.com/google/adk-python)
