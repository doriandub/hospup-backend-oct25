#!/bin/bash
set -e

# 🚀 Configuration autoscaling pour ECS Fargate (100+ vidéos simultanées)

AWS_REGION="eu-west-1"
ECS_CLUSTER_NAME="hospup-video-processing"
ECS_SERVICE_NAME="ffmpeg-worker-service"
SQS_QUEUE_NAME="hospup-video-jobs"

echo "🚀 Configuration autoscaling ECS pour traitement parallèle massif"
echo "=================================================================="

# 1. Register scalable target (min=1, max=100)
echo "📊 Configuration scaling target (min=1, max=100)..."

aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/$ECS_CLUSTER_NAME/$ECS_SERVICE_NAME \
  --min-capacity 1 \
  --max-capacity 100 \
  --region $AWS_REGION

echo "✅ Scaling target configured: 1-100 workers"

# 2. Target Tracking Scaling Policy - SQS-based
echo "📈 Configuration Target Tracking Policy (basé sur SQS)..."

cat > /tmp/autoscaling-policy.json <<EOF
{
  "TargetValue": 1.0,
  "CustomizedMetricSpecification": {
    "MetricName": "ApproximateNumberOfMessagesVisible",
    "Namespace": "AWS/SQS",
    "Dimensions": [
      {
        "Name": "QueueName",
        "Value": "$SQS_QUEUE_NAME"
      }
    ],
    "Statistic": "Average"
  },
  "ScaleOutCooldown": 10,
  "ScaleInCooldown": 300
}
EOF

aws application-autoscaling put-scaling-policy \
  --policy-name hospup-sqs-scaling-policy \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/$ECS_CLUSTER_NAME/$ECS_SERVICE_NAME \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration file:///tmp/autoscaling-policy.json \
  --region $AWS_REGION

echo "✅ Autoscaling policy configured:"
echo "   • Target: 1 message per worker (ratio 1:1)"
echo "   • Scale OUT: 10s cooldown (très rapide)"
echo "   • Scale IN: 300s cooldown (évite flip-flop)"

# 3. Step Scaling Policy - Burst protection
echo "⚡ Configuration Step Scaling Policy (protection burst)..."

cat > /tmp/step-scaling-policy.json <<EOF
{
  "AdjustmentType": "ExactCapacity",
  "StepAdjustments": [
    {
      "MetricIntervalLowerBound": 0,
      "MetricIntervalUpperBound": 10,
      "ScalingAdjustment": 10
    },
    {
      "MetricIntervalLowerBound": 10,
      "MetricIntervalUpperBound": 50,
      "ScalingAdjustment": 50
    },
    {
      "MetricIntervalLowerBound": 50,
      "ScalingAdjustment": 100
    }
  ],
  "MetricAggregationType": "Average"
}
EOF

aws application-autoscaling put-scaling-policy \
  --policy-name hospup-burst-scaling-policy \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/$ECS_CLUSTER_NAME/$ECS_SERVICE_NAME \
  --policy-type StepScaling \
  --step-scaling-policy-configuration file:///tmp/step-scaling-policy.json \
  --region $AWS_REGION

echo "✅ Step Scaling configured:"
echo "   • 0-10 messages → 10 workers"
echo "   • 10-50 messages → 50 workers"
echo "   • 50+ messages → 100 workers"

# 4. CloudWatch Alarm - Trigger Step Scaling
echo "🔔 Configuration CloudWatch Alarm..."

aws cloudwatch put-metric-alarm \
  --alarm-name hospup-sqs-burst-alarm \
  --alarm-description "Trigger burst scaling when SQS has many messages" \
  --metric-name ApproximateNumberOfMessagesVisible \
  --namespace AWS/SQS \
  --statistic Average \
  --period 60 \
  --evaluation-periods 1 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=QueueName,Value=$SQS_QUEUE_NAME \
  --alarm-actions arn:aws:autoscaling:$AWS_REGION:$(aws sts get-caller-identity --query Account --output text):scalingPolicy:*:resource/ecs/service/$ECS_CLUSTER_NAME/$ECS_SERVICE_NAME:policyName/hospup-burst-scaling-policy \
  --region $AWS_REGION

echo "✅ CloudWatch Alarm configured"

echo ""
echo "✅ Autoscaling configuration terminée!"
echo "======================================"
echo ""
echo "📊 Comportement attendu:"
echo "   • 1 user → 1 worker (déjà actif, 0s cold start)"
echo "   • 10 users → 10 workers en 10-20s"
echo "   • 50 users → 50 workers en 30-40s"
echo "   • 100 users → 100 workers en 60-90s"
echo ""
echo "⏱️  Temps de réponse utilisateur:"
echo "   • User 1: ~90s (0s cold + 90s FFmpeg)"
echo "   • Users 2-100: ~120-180s (30-60s cold + 90s FFmpeg)"
echo ""
echo "💰 Coût:"
echo "   • 1 worker 24/7: ~$30/mois"
echo "   • 100 vidéos burst: ~$0.50"
echo "   • Auto scale down après 5 min idle"
echo ""
echo "🔍 Monitoring:"
echo "   aws ecs describe-services --cluster $ECS_CLUSTER_NAME --services $ECS_SERVICE_NAME --region $AWS_REGION"
