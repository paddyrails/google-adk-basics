# 8. Hacks/Alternates — Interop, Workarounds, Cross-Framework

## 1. Framework Interop (Built into ADK)

| Integration | ADK Module | Install |
|------------|-----------|---------|
| LangChain tools | `google.adk.integrations.langchain.LangchainTool` | `pip install langchain-core` |
| LangGraph agents | `google.adk.agents.LangGraphAgent` | `pip install langgraph` |
| CrewAI tools | `google.adk.integrations.crewai.CrewaiTool` | `pip install google-adk[extensions]` |
| A2A server | `google.adk.a2a.utils.agent_to_a2a.to_a2a` | `pip install google-adk[a2a]` |
| A2A client | `google.adk.agents.remote_a2a_agent.RemoteA2aAgent` | `pip install google-adk[a2a]` |

```python
# LangChain tool in ADK
from google.adk.integrations.langchain import LangchainTool
from langchain_community.tools import DuckDuckGoSearchRun
agent = LlmAgent(tools=[LangchainTool(DuckDuckGoSearchRun())])

# LangGraph agent in ADK
from google.adk.agents import LangGraphAgent
langgraph_agent = LangGraphAgent(name="lg", graph=compiled_graph)
```

## 2. ADK vs Other Frameworks

| Dimension | ADK | LangChain/LangGraph | CrewAI | AutoGen |
|-----------|-----|---------------------|--------|---------|
| Best for | Structured pipelines, GCP | Mature ecosystem | Role-based crews | Conversational agents |
| Orchestration | DAG (Seq/Par/Loop) | Directed graph | Manager delegation | Group chat |
| Interop | A2A protocol | None built-in | None | None |

## 3. Key Workarounds

### output_schema + tools (broken) → Two-agent chain
```python
worker = LlmAgent(tools=[my_tool], output_key="raw")
formatter = LlmAgent(instruction="Format: {raw}", output_schema=MySchema)
pipeline = SequentialAgent(sub_agents=[worker, formatter])
```

### Built-in tool conflicts → AgentTool wrapping
```python
search_agent = LlmAgent(tools=[GoogleSearchTool()])
orchestrator = LlmAgent(tools=[AgentTool(agent=search_agent), my_tool])
```

### MCP schema mismatch → Patch definitions→$defs
### FunctionTool + RAG → Separate into different agents

## 4. Prompt Injection Defense
```python
def injection_guard(callback_context, llm_request, **kwargs):
    text = llm_request.contents[-1].parts[0].text
    if re.search(r"ignore.*previous.*instructions", text, re.I):
        return types.Content(role="model", parts=[types.Part(text="Blocked.")])
    return None
```

## 5. Model Fallback Strategy
```python
# Via LiteLLM Router (automatic failover)
models = [
    {"model_name": "primary", "litellm_params": {"model": "gemini/gemini-2.5-flash"}},
    {"model_name": "primary", "litellm_params": {"model": "openai/gpt-4o"}},
]
router = Router(model_list=models, fallbacks=[{"primary": ["primary"]}])
```

## 6. Non-Google Cloud Deployment
- **AWS**: Lambda via Mangum, ECS/Fargate, Bedrock models via LiteLLM
- **Azure**: Container Apps, Azure OpenAI via LiteLLM, Cosmos DB for sessions
- ADK is cloud-agnostic for deployment; only Vertex AI features are GCP-locked

## 7. Local Models
```python
# Ollama (use ollama_chat/ prefix, NOT ollama/)
agent = LlmAgent(model=LiteLlm(model="ollama_chat/llama3.1"))
# vLLM (OpenAI-compatible API)
agent = LlmAgent(model=LiteLlm(model="openai/llama3.1", api_base="http://localhost:8000/v1"))
```
