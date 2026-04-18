# 11. Observability — Tracing, Logging, Monitoring, Error Handling

## ADK Has Native OpenTelemetry Tracing

### Automatic Span Hierarchy
```
invocation (top-level)
  └── invoke_agent (per agent)
        ├── generate_content gemini-2.5-flash (per LLM call)
        └── execute_tool my_tool (per tool call)
```

### Enable Cloud Trace
```bash
adk web --trace_to_cloud my_agent          # Traces only
adk web --otel_to_cloud my_agent           # Traces + Metrics + Logs
```

### Programmatic Setup
```python
from google.adk.telemetry.google_cloud import get_gcp_exporters
from google.adk.telemetry.setup import maybe_set_otel_providers
maybe_set_otel_providers(otel_hooks_to_setup=[get_gcp_exporters(
    enable_cloud_tracing=True, enable_cloud_metrics=True, enable_cloud_logging=True
)])
```

## Key Span Attributes (auto-recorded)

| Attribute | Where |
|-----------|-------|
| `gen_ai.agent.name` | Agent spans |
| `gen_ai.request.model` | LLM spans |
| `gen_ai.usage.input_tokens` | LLM spans |
| `gen_ai.usage.output_tokens` | LLM spans |
| `gen_ai.tool.name` | Tool spans |
| `error.type` | Failed spans |

## Token Tracking via Callbacks
```python
def track_tokens(callback_context, llm_response, **kwargs):
    if llm_response.usage_metadata:
        logger.info("tokens: in=%s out=%s",
            llm_response.usage_metadata.prompt_token_count,
            llm_response.usage_metadata.candidates_token_count)
    return None
```

## Error Handling (3 Layers)

| Callback | Signature | Return to Handle |
|----------|-----------|-----------------|
| `on_model_error_callback` | `(ctx, llm_request, error)` | `types.Content` (fallback response) |
| `on_tool_error_callback` | `(tool, args, tool_ctx, error)` | `dict` (fallback tool result) |
| Multiple callbacks | Accept lists — first non-None wins | |

```python
def handle_model_error(callback_context, llm_request, error):
    if "429" in str(error):
        return types.Content(role="model", parts=[types.Part(text="Overloaded. Try again.")])
    return None  # Let error propagate
```

## ADK Dev UI Debugging
- **Event timeline** — every event with author, timestamp
- **Trace waterfall** — nested spans
- **State inspector** — live session state
- **REST API**: `GET /debug/trace/session/{session_id}`

## PII in Spans
```bash
export ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=false  # Strip PII from spans
```

## Latency Monitoring
```python
def before_model_timer(callback_context, llm_request, **kwargs):
    callback_context.state["temp:llm_start"] = time.monotonic()
    return None

def after_model_timer(callback_context, llm_response, **kwargs):
    elapsed = (time.monotonic() - callback_context.state.get("temp:llm_start", 0)) * 1000
    if elapsed > 5000:
        logger.warning("SLOW LLM CALL: %.1fms", elapsed)
    return None
```
