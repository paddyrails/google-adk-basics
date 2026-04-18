"""
05 - Deployment Hands-On: Production-Ready ADK Agent
======================================================
Creates production deployment artifacts:
  1. Production main.py (FastAPI with get_fast_api_app)
  2. Dockerfile (multi-stage, non-root)
  3. docker-compose.yml (agent + PostgreSQL)
  4. requirements.txt
  5. .dockerignore
  6. Kubernetes deployment.yaml
"""

import os

BASE = os.path.dirname(os.path.abspath(__file__))
DEPLOY_DIR = os.path.join(BASE, "deploy")


def create_file(path, content, description):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    print(f"  Created: {os.path.relpath(path, BASE):40s} <- {description}")


def main():
    print("=" * 60)
    print("DEPLOYMENT HANDS-ON: Production Artifacts")
    print("=" * 60)
    print()

    # 1. Production main.py
    create_file(
        os.path.join(DEPLOY_DIR, "main.py"),
        '''\
"""
Production ADK Agent Server
Run: uvicorn main:app --host 0.0.0.0 --port 8080
"""
import os
import logging
from dotenv import load_dotenv

load_dotenv()

from google.adk.cli.fast_api import get_fast_api_app

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))

app = get_fast_api_app(
    agents_dir=AGENT_DIR,
    session_service_uri=os.environ.get(
        "SESSION_SERVICE_URI",
        "sqlite+aiosqlite:///./sessions.db"
    ),
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "*").split(","),
    web=os.environ.get("SERVE_WEB_UI", "false").lower() == "true",
)
''',
        "FastAPI server using get_fast_api_app",
    )

    # 2. Agent module (copy my_agent structure)
    create_file(
        os.path.join(DEPLOY_DIR, "my_agent", "__init__.py"),
        "from .agent import root_agent\n",
        "Agent package init",
    )

    create_file(
        os.path.join(DEPLOY_DIR, "my_agent", "agent.py"),
        '''\
"""Production agent definition."""
from google.adk.agents import LlmAgent

def get_current_time(city: str) -> dict:
    """Returns the current time for a city.

    Args:
        city: City name.
    """
    import datetime
    return {"city": city, "time": datetime.datetime.now().isoformat(), "timezone": "UTC"}

def get_weather(city: str) -> dict:
    """Returns weather for a city.

    Args:
        city: City name.
    """
    return {"city": city, "temp": "22C", "condition": "Sunny"}

root_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="assistant",
    description="A helpful assistant that can tell time and weather",
    instruction="""You are a helpful assistant. You can:
1. Tell the current time using get_current_time
2. Check weather using get_weather
Be concise.""",
    tools=[get_current_time, get_weather],
)
''',
        "Agent with tools",
    )

    # 3. requirements.txt
    create_file(
        os.path.join(DEPLOY_DIR, "requirements.txt"),
        """\
google-adk>=1.31.0
python-dotenv
uvicorn[standard]
aiosqlite
asyncpg
""",
        "Python dependencies",
    )

    # 4. Dockerfile (multi-stage)
    create_file(
        os.path.join(DEPLOY_DIR, "Dockerfile"),
        """\
# Stage 1: Install dependencies
FROM python:3.13-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.13-slim
WORKDIR /app

COPY --from=builder /install /usr/local

# Non-root user
RUN adduser --disabled-password --gecos "" agentuser && \\
    chown -R agentuser:agentuser /app
USER agentuser
ENV PATH="/home/agentuser/.local/bin:$PATH"

COPY --chown=agentuser:agentuser . .

ENV PYTHONUNBUFFERED=1
ENV PORT=8080
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \\
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/list-apps')" || exit 1

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT --workers 2"]
""",
        "Multi-stage Dockerfile",
    )

    # 5. .dockerignore
    create_file(
        os.path.join(DEPLOY_DIR, ".dockerignore"),
        """\
.venv
__pycache__
*.pyc
.git
.env
sessions.db
*.session.json
.adk/
tests/
""",
        "Docker ignore file",
    )

    # 6. docker-compose.yml
    create_file(
        os.path.join(DEPLOY_DIR, "docker-compose.yml"),
        """\
version: "3.8"
services:
  agent:
    build: .
    ports:
      - "8080:8080"
    environment:
      - PORT=8080
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - GOOGLE_GENAI_USE_VERTEXAI=False
      - SESSION_SERVICE_URI=postgresql+asyncpg://adk:adk_password@postgres:5432/adk_sessions
      - SERVE_WEB_UI=true
      - LOG_LEVEL=INFO
    depends_on:
      postgres:
        condition: service_healthy

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: adk
      POSTGRES_PASSWORD: adk_password
      POSTGRES_DB: adk_sessions
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U adk"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
""",
        "Docker Compose (agent + PostgreSQL)",
    )

    # 7. Kubernetes manifests
    create_file(
        os.path.join(DEPLOY_DIR, "k8s", "deployment.yaml"),
        """\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: adk-agent
  labels:
    app: adk-agent
spec:
  replicas: 2
  selector:
    matchLabels:
      app: adk-agent
  template:
    metadata:
      labels:
        app: adk-agent
    spec:
      serviceAccountName: adk-agent-sa
      containers:
      - name: adk-agent
        image: us-central1-docker.pkg.dev/PROJECT_ID/adk-repo/agent:latest
        resources:
          requests:
            memory: "256Mi"
            cpu: "500m"
          limits:
            memory: "512Mi"
            cpu: "1000m"
        ports:
        - containerPort: 8080
        env:
        - name: PORT
          value: "8080"
        - name: GOOGLE_CLOUD_PROJECT
          value: "PROJECT_ID"
        - name: GOOGLE_CLOUD_LOCATION
          value: "us-central1"
        - name: GOOGLE_GENAI_USE_VERTEXAI
          value: "True"
        - name: SESSION_SERVICE_URI
          valueFrom:
            secretKeyRef:
              name: adk-secrets
              key: session-db-uri
        livenessProbe:
          httpGet:
            path: /list-apps
            port: 8080
          initialDelaySeconds: 15
          periodSeconds: 20
        readinessProbe:
          httpGet:
            path: /list-apps
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: adk-agent
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8080
  selector:
    app: adk-agent
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: adk-agent-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: adk-agent
  minReplicas: 1
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 50
""",
        "K8s Deployment + Service + HPA",
    )

    # 8. Cloud Run deploy script
    create_file(
        os.path.join(DEPLOY_DIR, "deploy-cloudrun.sh"),
        """\
#!/bin/bash
set -euo pipefail

# Configuration
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-my-project}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
SERVICE_NAME="adk-agent"

echo "Deploying to Cloud Run..."
echo "  Project: $PROJECT_ID"
echo "  Region:  $REGION"
echo "  Service: $SERVICE_NAME"

gcloud run deploy $SERVICE_NAME \\
  --source . \\
  --region $REGION \\
  --project $PROJECT_ID \\
  --no-allow-unauthenticated \\
  --min-instances=1 \\
  --max-instances=10 \\
  --concurrency=80 \\
  --cpu=2 \\
  --memory=1Gi \\
  --timeout=300 \\
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$REGION,GOOGLE_GENAI_USE_VERTEXAI=True,LOG_LEVEL=INFO" \\
  --set-secrets="GOOGLE_API_KEY=google-api-key:latest"

echo ""
echo "Deployed! Get URL with:"
echo "  gcloud run services describe $SERVICE_NAME --region $REGION --format='value(status.url)'"
""",
        "Cloud Run deploy script",
    )
    os.chmod(os.path.join(DEPLOY_DIR, "deploy-cloudrun.sh"), 0o755)

    print()
    print("=" * 60)
    print("All deployment artifacts created in deploy/")
    print("=" * 60)
    print(f"""
  deploy/
    main.py                <- Production FastAPI server
    my_agent/
      __init__.py          <- Agent package
      agent.py             <- Agent definition
    requirements.txt       <- Dependencies
    Dockerfile             <- Multi-stage, non-root
    .dockerignore          <- Excludes secrets & dev files
    docker-compose.yml     <- Agent + PostgreSQL
    k8s/deployment.yaml    <- K8s Deployment + Service + HPA
    deploy-cloudrun.sh     <- Cloud Run deploy script

  To run locally with Docker:
    cd deploy
    export GOOGLE_API_KEY=your-key
    docker compose up --build

  To deploy to Cloud Run:
    cd deploy
    ./deploy-cloudrun.sh

  To deploy to GKE:
    cd deploy
    kubectl apply -f k8s/deployment.yaml
""")


if __name__ == "__main__":
    main()
