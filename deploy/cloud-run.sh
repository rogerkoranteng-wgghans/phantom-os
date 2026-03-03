#!/usr/bin/env bash
# deploy/cloud-run.sh — Build and deploy Phantom OS backend to Google Cloud Run
#
# Usage:
#   export PROJECT_ID=your-gcp-project
#   export GEMINI_API_KEY=your-key
#   export REDIS_URL=redis://your-redis-host:6379
#   bash deploy/cloud-run.sh
#
# Optional overrides (defaults shown):
#   REGION=us-central1
#   SERVICE_NAME=phantom-backend
#   IMAGE_TAG=latest

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID to your GCP project ID}"
GEMINI_API_KEY="${GEMINI_API_KEY:?Set GEMINI_API_KEY}"
REDIS_URL="${REDIS_URL:?Set REDIS_URL to your Redis connection string}"

REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-phantom-backend}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:${IMAGE_TAG}"

# ── Helpers ───────────────────────────────────────────────────────────────────

info()  { echo "[INFO]  $*"; }
error() { echo "[ERROR] $*" >&2; exit 1; }

command -v gcloud >/dev/null 2>&1 || error "gcloud CLI not found. Install from https://cloud.google.com/sdk"

# ── Build ─────────────────────────────────────────────────────────────────────

info "Building image: ${IMAGE}"
gcloud builds submit ./backend \
  --tag "${IMAGE}" \
  --project "${PROJECT_ID}"

# ── Deploy ────────────────────────────────────────────────────────────────────

info "Deploying ${SERVICE_NAME} to Cloud Run (${REGION})"
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --platform managed \
  --region "${REGION}" \
  --allow-unauthenticated \
  --port 8000 \
  --memory 1Gi \
  --cpu 1 \
  --timeout 3600 \
  --concurrency 80 \
  --set-env-vars "GEMINI_API_KEY=${GEMINI_API_KEY},REDIS_URL=${REDIS_URL},GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
  --project "${PROJECT_ID}"

# ── Output ────────────────────────────────────────────────────────────────────

SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --format "value(status.url)")

info "Deployment complete!"
info "Service URL: ${SERVICE_URL}"
info ""
info "Health check:"
curl -sf "${SERVICE_URL}/health" && echo "" || echo "(health check failed — check Cloud Run logs)"
info ""
info "Update the desktop agent:"
info "  export BACKEND_URL=wss://${SERVICE_URL#https://}"
info "  python agent/main.py"
