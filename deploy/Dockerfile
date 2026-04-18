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
RUN adduser --disabled-password --gecos "" agentuser && \
    chown -R agentuser:agentuser /app
USER agentuser
ENV PATH="/home/agentuser/.local/bin:$PATH"

COPY --chown=agentuser:agentuser . .

ENV PYTHONUNBUFFERED=1
ENV PORT=8080
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/list-apps')" || exit 1

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT --workers 2"]
