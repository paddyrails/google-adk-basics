# 5. Deployment — Local, Cloud Run, GKE, Vertex AI Agent Engine

## Deployment Options at a Glance

| Option | Effort | Scaling | Best For |
|--------|--------|---------|----------|
| **Local** (`adk run/web`) | Zero | None | Development |
| **Agent Engine** (Vertex AI) | Low | Fully managed | Quick production (Python only) |
| **Cloud Run** | Medium | Managed + config | Production with customization |
| **GKE** | High | Full HPA control | Enterprise, multi-agent |

## 1. Local Development

```bash
adk run my_agent                           # Interactive terminal
adk web --port 8000                        # Dev UI (browser)
adk api_server --port 8000                 # Headless REST API
```

Key flags:
```bash
adk web \
  --session_service_uri "sqlite+aiosqlite:///./sessions.db" \
  --log_level DEBUG \
  --trace_to_cloud \
  --reload
```

API endpoints: `/list-apps`, `/run`, `/run_sse`, session CRUD.

## 2. Vertex AI Agent Engine (Fully Managed)

```bash
adk deploy agent_engine \
  --project=$PROJECT_ID \
  --region=us-central1 \
  --display_name="My Agent" \
  my_agent
```

Or programmatically:
```python
import vertexai
from vertexai import agent_engines

vertexai.init(project="my-project", location="us-central1")
remote_agent = agent_engines.create(
    agent=root_agent,
    config={"requirements": ["google-cloud-aiplatform[agent_engines,adk]"]}
)
response = remote_agent.query(input="Hello")
```

**Limitations:** Python only, no custom Web UI, cold start latency.

## 3. Cloud Run

### Automated
```bash
adk deploy cloud_run \
  --project=$PROJECT_ID \
  --region=us-central1 \
  --service_name=my-agent \
  --with_ui \
  my_agent
```

### Manual (Full Control)

**main.py:**
```python
from google.adk.cli.fast_api import get_fast_api_app
app = get_fast_api_app(
    agents_dir=AGENT_DIR,
    session_service_uri=os.environ.get("SESSION_SERVICE_URI", "sqlite+aiosqlite:///./sessions.db"),
    web=False,  # No dev UI in production
)
```

**Dockerfile:**
```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN adduser --disabled-password agentuser && chown -R agentuser /app
COPY . .
USER agentuser
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]
```

**Deploy:**
```bash
gcloud run deploy my-agent \
  --source . \
  --region us-central1 \
  --min-instances=1 --max-instances=10 \
  --set-env-vars="GOOGLE_GENAI_USE_VERTEXAI=True" \
  --set-secrets="GOOGLE_API_KEY=google-api-key:latest"
```

## 4. GKE / Kubernetes

```bash
adk deploy gke --project myproject --cluster_name my-cluster --region us-central1
```

Or manual K8s manifests with Deployment + Service + HPA:
```yaml
spec:
  replicas: 2
  containers:
  - image: us-central1-docker.pkg.dev/project/repo/agent:latest
    resources:
      requests: { memory: "256Mi", cpu: "500m" }
    livenessProbe:
      httpGet: { path: /list-apps, port: 8080 }
```

## 5. Session Persistence

| Service | URI Format | Use Case |
|---------|-----------|----------|
| **InMemory** | (default) | Dev only, data lost on restart |
| **SQLite** | `sqlite+aiosqlite:///./sessions.db` | Local dev with persistence |
| **PostgreSQL** | `postgresql+asyncpg://user:pass@host/db` | Production |
| **VertexAI** | `VertexAiSessionService(project=..., location=...)` | Managed cloud |

**Critical:** Must use async drivers (`asyncpg`, `aiosqlite`, `aiomysql`).

## 6. Secrets Management

```bash
# Cloud Run + Secret Manager
gcloud secrets create api-key --data-file=-
gcloud run deploy --set-secrets="GOOGLE_API_KEY=api-key:latest"

# GKE + K8s Secrets
kubectl create secret generic adk-secrets --from-literal=db-uri="postgresql+asyncpg://..."
```

**Never bake secrets into Docker images.** Use env vars or Secret Manager.

## 7. Production Checklist

1. Use **Vertex AI** (`GOOGLE_GENAI_USE_VERTEXAI=True`) — IAM, audit logs, VPC
2. **PostgreSQL** for sessions via Cloud SQL
3. **Non-root** container user
4. **Secret Manager** for all credentials
5. **Min 1 instance** on Cloud Run (avoid cold starts)
6. **Workload Identity** on GKE (no JSON keys)
7. **Cloud Trace** enabled for debugging
8. **Session TTL** to prevent unbounded storage
9. Proper **`.dockerignore`** (exclude `.env`, `.venv`, `sessions.db`)
10. **CI/CD** with `adk eval` for automated testing

## 8. CI/CD with GitHub Actions

```yaml
jobs:
  test:
    steps:
    - run: adk eval my_agent tests/fixtures/ --config_file_path=tests/test_config.json
  deploy:
    needs: test
    steps:
    - run: gcloud run deploy my-agent --source . --region us-central1
```
