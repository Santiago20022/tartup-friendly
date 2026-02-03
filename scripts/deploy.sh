#!/bin/bash
set -e

# VetUltrasound API Deployment Script
# Usage: ./scripts/deploy.sh [project-id] [region]

PROJECT_ID=${1:-$(gcloud config get-value project)}
REGION=${2:-us-central1}
SERVICE_NAME="vet-ultrasound-api"

echo "=========================================="
echo "Deploying VetUltrasound API"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "=========================================="

# Check if logged in
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1 > /dev/null 2>&1; then
    echo "Error: Not logged in to gcloud. Run 'gcloud auth login' first."
    exit 1
fi

# Enable required APIs
echo "Enabling required APIs..."
gcloud services enable \
    run.googleapis.com \
    documentai.googleapis.com \
    storage.googleapis.com \
    firestore.googleapis.com \
    cloudbuild.googleapis.com \
    --project=$PROJECT_ID

# Create storage buckets if they don't exist
UPLOADS_BUCKET="${PROJECT_ID}-ultrasound-uploads"
IMAGES_BUCKET="${PROJECT_ID}-ultrasound-images"

echo "Creating storage buckets..."
gsutil ls -b gs://$UPLOADS_BUCKET > /dev/null 2>&1 || \
    gsutil mb -l $REGION -p $PROJECT_ID gs://$UPLOADS_BUCKET

gsutil ls -b gs://$IMAGES_BUCKET > /dev/null 2>&1 || \
    gsutil mb -l $REGION -p $PROJECT_ID gs://$IMAGES_BUCKET

# Enable uniform bucket access
gsutil uniformbucketlevelaccess set on gs://$UPLOADS_BUCKET
gsutil uniformbucketlevelaccess set on gs://$IMAGES_BUCKET

# Build container
echo "Building container image..."
gcloud builds submit \
    --tag gcr.io/$PROJECT_ID/$SERVICE_NAME \
    --project=$PROJECT_ID

# Deploy to Cloud Run
echo "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
    --platform managed \
    --region $REGION \
    --project $PROJECT_ID \
    --allow-unauthenticated \
    --memory 1Gi \
    --cpu 1 \
    --timeout 300 \
    --min-instances 0 \
    --max-instances 10 \
    --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID,GCS_BUCKET_UPLOADS=$UPLOADS_BUCKET,GCS_BUCKET_IMAGES=$IMAGES_BUCKET"

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
    --platform managed \
    --region $REGION \
    --project $PROJECT_ID \
    --format='value(status.url)')

echo ""
echo "=========================================="
echo "Deployment complete!"
echo "API URL: $SERVICE_URL"
echo ""
echo "Test with:"
echo "curl $SERVICE_URL/health"
echo "=========================================="
