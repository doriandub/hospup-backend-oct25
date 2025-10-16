#!/bin/bash
set -e

REGION="eu-west-1"
ACCOUNT_ID="412655955859"
CLUSTER="hospup-video-processing"
SERVICE="ffmpeg-worker-service"
ECR_REPO="hospup-ffmpeg-worker"

echo "🚀 Quick ECS deployment"

# Tag image
echo "📦 Tagging image..."
docker tag hospup-ffmpeg-worker:latest $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO:latest

# Login to ECR
echo "🔐 Login to ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

# Push image
echo "📤 Pushing to ECR..."
docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO:latest

# Force new deployment
echo "🔄 Forcing ECS service update..."
aws ecs update-service --cluster $CLUSTER --service $SERVICE --force-new-deployment --region $REGION

echo "✅ Deployment initiated! Workers will restart with new code in ~2 minutes"
