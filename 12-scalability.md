# 12. Scalability — Horizontal Scaling, Async, Sessions, Caching

## 1. Horizontal Scaling

**Problem**: `InMemorySessionService` is single-process, dev-only.
**Solution**: `DatabaseSessionService` with PostgreSQL — all instances share state.

```python
session_service = DatabaseSessionService(
    db_url="postgresql+asyncpg://user:pass@host/db",
    pool_size=20, max_overflow=10, pool_recycle=1800,
)
runner = Runner(app_name="app", agent=agent, session_service=session_service)
# Runner is STATELESS — safe to share across requests
```

**Dual-layer locking**: In-process asyncio.Lock + database `SELECT ... FOR UPDATE`.

## 2. Async Patterns

```python
# Semaphore-bounded concurrency
semaphore = asyncio.Semaphore(10)
async with semaphore:
    async for event in runner.run_async(...): ...

# Timeout protection (ADK has none built-in)
result = await asyncio.wait_for(run_agent(), timeout=30.0)
```

## 3. Session Management at Scale

| Problem | Solution |
|---------|----------|
| Unbounded event growth | `GetSessionConfig(num_recent_events=20)` |
| Old sessions consuming storage | Scheduled cleanup cron (DELETE WHERE age > 30d) |
| Large context windows | `SlidingWindowCompactionConfig` (experimental) |
| No TTL | Implement via scheduled Cloud Function |

## 4. Caching Layers

| Layer | What | Savings |
|-------|------|---------|
| **Gemini Context Cache** | `static_instruction` + `ContextCacheConfig` | 75% input tokens |
| **Response Cache (Redis)** | Cache final responses by query hash | 100% for hits |
| **Custom Redis Sessions** | Sub-ms reads vs 2-10ms PostgreSQL | Latency |

## 5. Database Scaling

| Pattern | When |
|---------|------|
| **Connection pooling** | `pool_size=20, max_overflow=10` |
| **PgBouncer** | Many replicas exhausting PostgreSQL connections |
| **Read replicas** | Cross-region reads, read-heavy workloads |
| **Cloud SQL IAM auth** | No password management |

## 6. Load Balancing

| Platform | Key Config |
|----------|-----------|
| **Cloud Run** | `--concurrency=40 --min-instances=1 --max-instances=100` |
| **GKE HPA** | Scale on CPU 60% or custom p95 latency metric |

## 7. Cost at Scale

```
100 req/day,  Flash, 1 agent:  ~$4.50/month
1K req/day,   Flash, 2 agents: ~$90/month
10K req/day,  Flash, 3 agents: ~$540/month (with 30% cache)
5K req/day,   Pro,   2 agents: ~$5,250/month
```

## 8. Performance Benchmarks

| Component | P50 | P95 |
|-----------|-----|-----|
| Gemini Flash full response | 800ms | 2.5s |
| Session get (PostgreSQL) | 2ms | 5ms |
| Session get (Redis) | 0.3ms | 1ms |
| 3-agent sequential pipeline | 3s | 9s |
| 3-agent parallel pipeline | 1.2s | 3.5s |

**Bottleneck is almost always the LLM API, not ADK itself.** ADK adds <5ms overhead per event.

## 9. Multi-Region

```
Global LB → us-central1 (primary DB) + europe-west1 (read replica) + asia-east1 (read replica)
```
- Gemini API is region-specific — set `GOOGLE_CLOUD_LOCATION` per region
- Session writes go to primary, reads to local replica
- Vertex AI Agent Engine is single-region only

## 10. Queue-Based Architecture

| Pattern | Best For |
|---------|----------|
| **Pub/Sub → Cloud Run** | Auto-scaling, GCP native |
| **Cloud Tasks** | Delayed/scheduled, rate limiting |
| **Celery + Redis** | Hybrid / non-GCP |
