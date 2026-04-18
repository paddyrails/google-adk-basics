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

gcloud run deploy $SERVICE_NAME \
  --source . \
  --region $REGION \
  --project $PROJECT_ID \
  --no-allow-unauthenticated \
  --min-instances=1 \
  --max-instances=10 \
  --concurrency=80 \
  --cpu=2 \
  --memory=1Gi \
  --timeout=300 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$REGION,GOOGLE_GENAI_USE_VERTEXAI=True,LOG_LEVEL=INFO" \
  --set-secrets="GOOGLE_API_KEY=google-api-key:latest"

echo ""
echo "Deployed! Get URL with:"
echo "  gcloud run services describe $SERVICE_NAME --region $REGION --format='value(status.url)'"
