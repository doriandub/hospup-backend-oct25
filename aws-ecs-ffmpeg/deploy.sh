#!/bin/bash
set -e

# 🎬 Script de déploiement ECS Fargate FFmpeg Worker (zéro cold start)

AWS_REGION="eu-west-1"
AWS_ACCOUNT_ID="211125402986"
ECR_REPO_NAME="hospup-ffmpeg-worker"
ECS_CLUSTER_NAME="hospup-video-processing"
ECS_SERVICE_NAME="ffmpeg-worker-service"
SQS_QUEUE_NAME="hospup-video-jobs"

echo "🚀 Déploiement ECS Fargate FFmpeg Worker"
echo "=========================================="

# 1. Create ECR repository
echo "📦 Creating ECR repository..."
aws ecr describe-repositories --repository-names $ECR_REPO_NAME --region $AWS_REGION 2>/dev/null || \
  aws ecr create-repository \
    --repository-name $ECR_REPO_NAME \
    --region $AWS_REGION

# 2. Build and push Docker image
echo "🐳 Building Docker image..."
docker build -t $ECR_REPO_NAME:latest .

echo "🔐 Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

echo "📤 Pushing image to ECR..."
docker tag $ECR_REPO_NAME:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:latest

# 3. Create SQS queue
echo "📬 Creating SQS queue..."
SQS_QUEUE_URL=$(aws sqs create-queue \
  --queue-name $SQS_QUEUE_NAME \
  --region $AWS_REGION \
  --query 'QueueUrl' \
  --output text 2>/dev/null || \
  aws sqs get-queue-url \
  --queue-name $SQS_QUEUE_NAME \
  --region $AWS_REGION \
  --query 'QueueUrl' \
  --output text)

echo "   Queue URL: $SQS_QUEUE_URL"

# 4. Create ECS cluster
echo "☁️  Creating ECS cluster..."
aws ecs describe-clusters --clusters $ECS_CLUSTER_NAME --region $AWS_REGION 2>/dev/null || \
  aws ecs create-cluster \
    --cluster-name $ECS_CLUSTER_NAME \
    --region $AWS_REGION

# 5. Create IAM execution role
echo "🔑 Creating IAM execution role..."
EXECUTION_ROLE_NAME="hospup-ecs-ffmpeg-execution-role"

aws iam get-role --role-name $EXECUTION_ROLE_NAME 2>/dev/null || \
  aws iam create-role \
    --role-name $EXECUTION_ROLE_NAME \
    --assume-role-policy-document '{
      "Version": "2012-10-17",
      "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "ecs-tasks.amazonaws.com"},
        "Action": "sts:AssumeRole"
      }]
    }'

aws iam attach-role-policy \
  --role-name $EXECUTION_ROLE_NAME \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# 6. Create IAM task role (S3 + SQS access)
echo "🔑 Creating IAM task role..."
TASK_ROLE_NAME="hospup-ecs-ffmpeg-task-role"

aws iam get-role --role-name $TASK_ROLE_NAME 2>/dev/null || \
  aws iam create-role \
    --role-name $TASK_ROLE_NAME \
    --assume-role-policy-document '{
      "Version": "2012-10-17",
      "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "ecs-tasks.amazonaws.com"},
        "Action": "sts:AssumeRole"
      }]
    }'

# Attach S3 + SQS policy
aws iam put-role-policy \
  --role-name $TASK_ROLE_NAME \
  --policy-name hospup-ffmpeg-worker-policy \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ],
        "Resource": [
          "arn:aws:s3:::hospup-files",
          "arn:aws:s3:::hospup-files/*"
        ]
      },
      {
        "Effect": "Allow",
        "Action": [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ],
        "Resource": "arn:aws:sqs:'$AWS_REGION':'$AWS_ACCOUNT_ID':'$SQS_QUEUE_NAME'"
      }
    ]
  }'

# 7. Register task definition
echo "📝 Registering ECS task definition..."

EXECUTION_ROLE_ARN="arn:aws:iam::$AWS_ACCOUNT_ID:role/$EXECUTION_ROLE_NAME"
TASK_ROLE_ARN="arn:aws:iam::$AWS_ACCOUNT_ID:role/$TASK_ROLE_NAME"
WEBHOOK_URL="https://hospup-backend-production.up.railway.app/api/v1/videos/ffmpeg-callback"

cat > task-definition.json <<EOF
{
  "family": "hospup-ffmpeg-worker",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "4096",
  "executionRoleArn": "$EXECUTION_ROLE_ARN",
  "taskRoleArn": "$TASK_ROLE_ARN",
  "containerDefinitions": [
    {
      "name": "ffmpeg-worker",
      "image": "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:latest",
      "essential": true,
      "environment": [
        {"name": "AWS_DEFAULT_REGION", "value": "$AWS_REGION"},
        {"name": "SQS_QUEUE_URL", "value": "$SQS_QUEUE_URL"},
        {"name": "WEBHOOK_URL", "value": "$WEBHOOK_URL"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/hospup-ffmpeg-worker",
          "awslogs-region": "$AWS_REGION",
          "awslogs-stream-prefix": "ecs",
          "awslogs-create-group": "true"
        }
      }
    }
  ]
}
EOF

aws ecs register-task-definition \
  --cli-input-json file://task-definition.json \
  --region $AWS_REGION

# 8. Create ECS service with warm pool (10 tasks always running = zéro cold start)
echo "🚀 Creating ECS service (10 tasks warm pool)..."

# Configuration du warm pool (modifiable)
WARM_POOL_SIZE=${WARM_POOL_SIZE:-10}  # Default: 10 workers, override avec: WARM_POOL_SIZE=20 ./deploy.sh

# Get default VPC and subnets
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query 'Vpcs[0].VpcId' --output text --region $AWS_REGION)
SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query 'Subnets[*].SubnetId' --output text --region $AWS_REGION | tr '\t' ',')

aws ecs describe-services \
  --cluster $ECS_CLUSTER_NAME \
  --services $ECS_SERVICE_NAME \
  --region $AWS_REGION 2>/dev/null || \
  aws ecs create-service \
    --cluster $ECS_CLUSTER_NAME \
    --service-name $ECS_SERVICE_NAME \
    --task-definition hospup-ffmpeg-worker \
    --desired-count $WARM_POOL_SIZE \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],assignPublicIp=ENABLED}" \
    --region $AWS_REGION

echo ""
echo "✅ Déploiement terminé!"
echo "========================"
echo "📬 SQS Queue URL: $SQS_QUEUE_URL"
echo "🐳 ECR Image: $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:latest"
echo "☁️  ECS Cluster: $ECS_CLUSTER_NAME"
echo "🚀 ECS Service: $ECS_SERVICE_NAME"
echo "🔥 Warm Pool: $WARM_POOL_SIZE workers toujours actifs (0s cold start)"
echo ""
echo "💰 Coût mensuel: ~\$$(($WARM_POOL_SIZE * 30))/mois (workers 24/7)"
echo ""
echo "⚡ Prochaine étape: Activer autoscaling"
echo "   ./warm-pool-config.sh"
echo ""
echo "🎬 Pour envoyer un job:"
echo "   aws sqs send-message --queue-url $SQS_QUEUE_URL --message-body '{\"job_id\":\"test-123\",\"segments\":[...],\"text_overlays\":[...]}'"
