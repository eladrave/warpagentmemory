#!/bin/bash

# Exit on error
set -e

echo "=== AgentMemory Service Account Setup ==="

if [[ -z "$GCP_PROJECT" ]]; then
    read -p "Enter GCP Project [chkp-gcp-prd-kenobi-box]: " GCP_PROJECT
fi
GCP_PROJECT=${GCP_PROJECT:-chkp-gcp-prd-kenobi-box}

SA_NAME="agentmemory-sa"
SA_EMAIL="${SA_NAME}@${GCP_PROJECT}.iam.gserviceaccount.com"

# Set active project
gcloud config set project $GCP_PROJECT

echo "Creating service account $SA_NAME..."
if gcloud iam service-accounts list --filter="email:${SA_EMAIL}" | grep -q "${SA_EMAIL}"; then
    echo "Service account already exists."
else
    gcloud iam service-accounts create $SA_NAME \
        --description="Service account for AgentMemory Google Drive & Gemini sync" \
        --display-name="AgentMemory Service Account"
fi

echo "Assigning necessary roles to $SA_EMAIL..."
# In this case, Gemini API currently relies on the user's API Key instead of Vertex AI SA impersonation by default 
# based on our code, but if we need Cloud Storage or Vertex AI later:
gcloud projects add-iam-policy-binding $GCP_PROJECT \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/storage.admin" > /dev/null

echo "Generating new keys for $SA_EMAIL..."
# Remove old key file if exists
rm -f service_account.json
gcloud iam service-accounts keys create service_account.json \
    --iam-account=${SA_EMAIL}

echo "✅ Success! Service account created and key saved to service_account.json."
echo "✅ SA Email: ${SA_EMAIL}"
