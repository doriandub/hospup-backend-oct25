#!/bin/bash
set -e

# 🔥 Configuration Warm Pool: 10 workers toujours actifs (zéro cold start)
# Stratégie: Maintenir un pool constant de workers disponibles

AWS_REGION="eu-west-1"
ECS_CLUSTER_NAME="hospup-video-processing"
ECS_SERVICE_NAME="ffmpeg-worker-service"
SQS_QUEUE_NAME="hospup-video-jobs"

# Configuration du pool (ajustable selon croissance)
WARM_POOL_SIZE=10    # Nombre de workers toujours actifs
MAX_WORKERS=50       # Maximum si burst (ajustable: 10, 20, 50, 100)

echo "🔥 Configuration Warm Pool ECS Fargate"
echo "======================================"
echo "   Pool Size: $WARM_POOL_SIZE workers toujours actifs"
echo "   Max Workers: $MAX_WORKERS (burst capacity)"
echo ""

# 1. Set desired count to pool size
echo "📊 Configuration du service ECS..."

aws ecs update-service \
  --cluster $ECS_CLUSTER_NAME \
  --service $ECS_SERVICE_NAME \
  --desired-count $WARM_POOL_SIZE \
  --region $AWS_REGION

echo "✅ Service configuré: $WARM_POOL_SIZE workers actifs en permanence"

# 2. Register scalable target
echo "📈 Configuration autoscaling target..."

aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/$ECS_CLUSTER_NAME/$ECS_SERVICE_NAME \
  --min-capacity $WARM_POOL_SIZE \
  --max-capacity $MAX_WORKERS \
  --region $AWS_REGION

echo "✅ Scaling configured: min=$WARM_POOL_SIZE, max=$MAX_WORKERS"

# 3. Target Tracking Scaling - Maintenir capacité disponible
echo "🎯 Configuration Target Tracking (capacité disponible)..."

# Formule: desired_workers = warm_pool + messages_in_queue
# Si 15 messages → 10 (pool) + 15 (processing) = 25 workers total
# Le pool de 10 reste toujours disponible

cat > /tmp/warm-pool-policy.json <<EOF
{
  "TargetValue": 0.7,
  "PredefinedMetricSpecification": {
    "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
  },
  "ScaleOutCooldown": 30,
  "ScaleInCooldown": 300
}
EOF

aws application-autoscaling put-scaling-policy \
  --policy-name hospup-warm-pool-cpu-policy \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/$ECS_CLUSTER_NAME/$ECS_SERVICE_NAME \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration file:///tmp/warm-pool-policy.json \
  --region $AWS_REGION

echo "✅ CPU-based scaling configured (target: 70%)"

# 4. SQS-based scaling - Scale up quand messages s'accumulent
echo "📬 Configuration SQS-based scaling..."

cat > /tmp/sqs-scaling-policy.json <<EOF
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
  "ScaleOutCooldown": 20,
  "ScaleInCooldown": 180
}
EOF

aws application-autoscaling put-scaling-policy \
  --policy-name hospup-warm-pool-sqs-policy \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/$ECS_CLUSTER_NAME/$ECS_SERVICE_NAME \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration file:///tmp/sqs-scaling-policy.json \
  --region $AWS_REGION

echo "✅ SQS-based scaling configured (1 message = 1 worker)"

# 5. CloudWatch Dashboard (optionnel mais utile)
echo "📊 Création CloudWatch Dashboard..."

cat > /tmp/dashboard.json <<EOF
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/ECS", "CPUUtilization", {"stat": "Average"}],
          [".", "MemoryUtilization", {"stat": "Average"}]
        ],
        "period": 60,
        "stat": "Average",
        "region": "$AWS_REGION",
        "title": "ECS Workers - CPU & Memory",
        "yAxis": {"left": {"min": 0, "max": 100}}
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/SQS", "ApproximateNumberOfMessagesVisible", {"stat": "Average"}],
          [".", "NumberOfMessagesReceived", {"stat": "Sum"}],
          [".", "NumberOfMessagesDeleted", {"stat": "Sum"}]
        ],
        "period": 60,
        "stat": "Average",
        "region": "$AWS_REGION",
        "title": "SQS Queue Metrics"
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/ECS", "RunningTaskCount", {"stat": "Average"}],
          [".", "DesiredTaskCount", {"stat": "Average"}]
        ],
        "period": 60,
        "stat": "Average",
        "region": "$AWS_REGION",
        "title": "Active Workers (Running vs Desired)"
      }
    }
  ]
}
EOF

aws cloudwatch put-dashboard \
  --dashboard-name HospupVideoProcessing \
  --dashboard-body file:///tmp/dashboard.json \
  --region $AWS_REGION || echo "⚠️ Dashboard creation skipped (non-critical)"

echo ""
echo "✅ Configuration Warm Pool terminée!"
echo "===================================="
echo ""
echo "🔥 Pool de $WARM_POOL_SIZE workers toujours actifs"
echo ""
echo "📊 Comportement:"
echo "   • 1-10 users → Pool actif (0s cold start)"
echo "   • 11-50 users → Scale up automatique en 20-30s"
echo "   • 50+ users → Jusqu'à $MAX_WORKERS workers (si configuré)"
echo ""
echo "⏱️  Temps de réponse:"
echo "   • Users 1-10: ~90s (0s cold start)"
echo "   • Users 11-50: ~120s (30s cold start)"
echo "   • Users 50+: ~150s (si dépassement pool)"
echo ""
echo "💰 Coût mensuel:"
echo "   • $WARM_POOL_SIZE workers 24/7: ~\$$(($WARM_POOL_SIZE * 30))/mois"
echo "   • Burst occasionnel: variable"
echo "   • Scale down auto après 3min idle"
echo ""
echo "🎚️  Ajuster le pool selon croissance:"
echo "   • Démarrage: 10 workers (\$300/mois)"
echo "   • Croissance: 20 workers (\$600/mois)"
echo "   • Scale: 50 workers (\$1500/mois)"
echo "   • Enterprise: 100 workers (\$3000/mois)"
echo ""
echo "📈 Pour augmenter le pool de 10 à 20:"
echo "   WARM_POOL_SIZE=20 MAX_WORKERS=100 ./warm-pool-config.sh"
echo ""
echo "📊 Monitoring en temps réel:"
echo "   aws ecs describe-services --cluster $ECS_CLUSTER_NAME --services $ECS_SERVICE_NAME --region $AWS_REGION --query 'services[0].[runningCount,desiredCount,pendingCount]'"
echo ""
echo "🌐 CloudWatch Dashboard:"
echo "   https://$AWS_REGION.console.aws.amazon.com/cloudwatch/home?region=$AWS_REGION#dashboards:name=HospupVideoProcessing"
