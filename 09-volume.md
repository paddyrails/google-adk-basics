# 9. Volume — Batching, Rate Limits, Token Budgets, Cost Optimization

## ADK Has No Built-in Volume Handling
No rate limiting, cost tracking, token counting, or budget enforcement. All DIY.

## 1. Batching with Semaphore
```python
class ADKBatchProcessor:
    def __init__(self, agent, max_concurrent=5):
        self.semaphore = asyncio.Semaphore(max_concurrent)
    async def process_batch(self, requests):
        return await asyncio.gather(*[self._process_one(r) for r in requests])
```

## 2. Rate Limiting + Retry (tenacity)
```python
@retry(
    retry=retry_if_exception_type((ResourceExhausted, TooManyRequests)),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5),
)
async def call_agent_with_backoff(runner, user_id, session_id, query):
    async for event in runner.run_async(...): ...
```

## 3. Token Tracking
```python
# Tokens are on event.usage_metadata (only for LLM call events)
if event.usage_metadata:
    input_tokens = event.usage_metadata.prompt_token_count
    output_tokens = event.usage_metadata.candidates_token_count
    cached = getattr(event.usage_metadata, "cached_content_token_count", 0)
```

## 4. Context Caching (75% input cost savings)
```python
agent = LlmAgent(
    static_instruction="[large reference doc]",  # Cached by Gemini
    instruction="Answer based on above: {query}",  # Dynamic per turn
)
# Or explicit via ContextCacheConfig on Runner
```

## 5. Cost Optimization Strategies

| Strategy | Savings |
|----------|---------|
| Use Flash instead of Pro | 13-33x cheaper |
| Enable context caching | 75% on input tokens |
| Minimize system prompt size | Proportional to prompt reduction |
| Response caching (Redis) | 100% for cache hits |
| `GetSessionConfig(num_recent_events=20)` | Reduces context window |
| Use `include_contents="none"` for stateless agents | Eliminates history tokens |

## 6. Cost Projections

| Scale | Model | Agents | Monthly Cost |
|-------|-------|--------|-------------|
| 100 req/day | Flash | 1 | ~$4.50 |
| 1K req/day | Flash | 2 | ~$90 |
| 10K req/day | Flash | 3 (30% cache) | ~$540 |
| 5K req/day | Pro | 2 | ~$5,250 |

## 7. Queue-Based Architecture
- **Celery + Redis**: `rate_limit="10/m"` on tasks
- **Cloud Tasks**: Built-in retries, rate limiting, deduplication
- **Pub/Sub → Cloud Run**: Auto-scaling consumers
