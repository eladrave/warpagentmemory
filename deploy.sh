#!/bin/bash

# Exit on error
set -e

echo "=== AgentMemory GCP Cloud Run Deployment ==="

if [[ -z "$GCP_PROJECT" ]]; then
    read -p "Enter GCP Project [chkp-gcp-prd-kenobi-box]: " GCP_PROJECT
fi
GCP_PROJECT=${GCP_PROJECT:-chkp-gcp-prd-kenobi-box}

if [[ -z "$APP_NAME" ]]; then
    read -p "Enter Application Name [agentmemory]: " APP_NAME
fi
APP_NAME=${APP_NAME:-agentmemory}

if [[ -z "$REGION" ]]; then
    read -p "Enter GCP Region [us-central1]: " REGION
fi
REGION=${REGION:-us-central1}


SA_NAME="agentmemory-sa"
# Create a GCS bucket for users.json if it doesn't exist
BUCKET_NAME="${GCP_PROJECT}-agentmemory-users"
echo "Ensuring GCS bucket gs://${BUCKET_NAME} exists..."
if ! gsutil ls -b "gs://${BUCKET_NAME}" >/dev/null 2>&1; then
    gsutil mb -p $GCP_PROJECT -l $REGION "gs://${BUCKET_NAME}"
    echo "Created bucket gs://${BUCKET_NAME}"
else
    echo "Bucket gs://${BUCKET_NAME} already exists."
fi

# Set active project
gcloud config set project $GCP_PROJECT

echo "Deploying to Cloud Run..."
gcloud run deploy $APP_NAME \
  --source . \
  --region $REGION \
  --allow-unauthenticated \
  --service-account=${SA_NAME}@${GCP_PROJECT}.iam.gserviceaccount.com \
  --execution-environment=gen2 \
  --add-volume=name=users-vol,type=cloud-storage,bucket=${BUCKET_NAME} \
  --add-volume-mount=volume=users-vol,mount-path=/mnt/gcs \
  --set-env-vars=USERS_FILE_PATH=/mnt/gcs/users.json \
  --update-env-vars=DREAM_INTERVAL_HOURS=24

echo "Deployment complete! Make sure to upload your .env secrets (GEMINI_API_KEY) via Cloud Run Secret Manager in the GCP Console."
