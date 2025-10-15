#!/bin/bash

# Deploy ECS FFmpeg Worker with video normalization support
set -e

echo "🚀 Deploying FFmpeg Worker to ECS..."

# Variables
AWS_REGION="eu-west-1"
AWS_ACCOUNT_ID="412655955859"
ECR_REPO="hospup-ffmpeg-worker"
IMAGE_TAG="latest"
ECS_CLUSTER="hospup-video-processing"
ECS_SERVICE="ffmpeg-worker-service"

# Full ECR image path
ECR_IMAGE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${IMAGE_TAG}"

echo "📦 Building Docker image..."
docker build -t ${ECR_REPO}:${IMAGE_TAG} .

echo "🏷️  Tagging image for ECR..."
docker tag ${ECR_REPO}:${IMAGE_TAG} ${ECR_IMAGE}

echo "🔐 Logging in to ECR..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

echo "📤 Pushing image to ECR..."
docker push ${ECR_IMAGE}

echo "🔄 Forcing new ECS deployment..."
aws ecs update-service \
    --cluster ${ECS_CLUSTER} \
    --service ${ECS_SERVICE} \
    --force-new-deployment \
    --region ${AWS_REGION}

echo "✅ Deployment initiated! Workers will restart with new code in ~2-3 minutes"
echo "📊 Monitor deployment:"
echo "   aws ecs describe-services --cluster ${ECS_CLUSTER} --services ${ECS_SERVICE} --region ${AWS_REGION}"
