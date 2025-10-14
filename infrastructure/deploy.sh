#!/bin/bash
set -e

# 🚀 Script de déploiement simplifié pour infrastructure CDK

WARM_POOL_SIZE=${WARM_POOL_SIZE:-10}
MAX_WORKERS=${MAX_WORKERS:-50}

echo "🚀 Déploiement Hospup Video Processing Infrastructure (CDK)"
echo "============================================================"
echo "   Warm Pool: $WARM_POOL_SIZE workers"
echo "   Max Workers: $MAX_WORKERS"
echo ""

# Vérifier que AWS CLI est configuré
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS CLI n'est pas configuré correctement"
    echo "   Exécuter: aws configure"
    exit 1
fi

AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${AWS_REGION:-eu-west-1}

echo "✅ AWS Account: $AWS_ACCOUNT"
echo "✅ AWS Region: $AWS_REGION"
echo ""

# Bootstrap CDK (si pas déjà fait)
echo "🔧 Vérification bootstrap CDK..."
if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region $AWS_REGION > /dev/null 2>&1; then
    echo "📦 Bootstrap CDK (première fois)..."
    npx cdk bootstrap aws://$AWS_ACCOUNT/$AWS_REGION
else
    echo "✅ CDK déjà bootstrappé"
fi

echo ""
echo "📦 Installation dépendances Python..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt

echo ""
echo "🔍 Synthèse CloudFormation..."
npx cdk synth -c warm_pool_size=$WARM_POOL_SIZE -c max_workers=$MAX_WORKERS

echo ""
echo "🚀 Déploiement infrastructure..."
npx cdk deploy \
  -c warm_pool_size=$WARM_POOL_SIZE \
  -c max_workers=$MAX_WORKERS \
  --outputs-file outputs.json \
  --require-approval never

echo ""
echo "✅ Déploiement terminé!"
echo "======================"
echo ""

# Afficher outputs importants
if [ -f outputs.json ]; then
    echo "📋 Outputs:"
    SQS_URL=$(cat outputs.json | python3 -c "import sys, json; print(json.load(sys.stdin)['HospupVideoProcessing']['SQSQueueURL'])")
    ECR_URI=$(cat outputs.json | python3 -c "import sys, json; print(json.load(sys.stdin)['HospupVideoProcessing']['ECRRepositoryURI'])")
    DASHBOARD_URL=$(cat outputs.json | python3 -c "import sys, json; print(json.load(sys.stdin)['HospupVideoProcessing']['DashboardURL'])")

    echo ""
    echo "   📬 SQS Queue URL:"
    echo "      $SQS_URL"
    echo ""
    echo "   🐳 ECR Repository:"
    echo "      $ECR_URI"
    echo ""
    echo "   📊 Dashboard:"
    echo "      $DASHBOARD_URL"
    echo ""
fi

echo "🎯 Prochaines étapes:"
echo ""
echo "1. Ajouter dans Railway (.env):"
echo "   SQS_QUEUE_URL=$SQS_URL"
echo ""
echo "2. Build et push image Docker:"
echo "   cd ../aws-ecs-ffmpeg"
echo "   docker build -t hospup-ffmpeg-worker ."
echo "   docker tag hospup-ffmpeg-worker:latest $ECR_URI:latest"
echo "   aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_URI"
echo "   docker push $ECR_URI:latest"
echo ""
echo "3. Forcer redéploiement workers:"
echo "   aws ecs update-service --cluster hospup-video-processing --service ffmpeg-worker-service --force-new-deployment --region $AWS_REGION"
echo ""
echo "4. Tester sur video-debug!"
echo ""

echo "💰 Coût mensuel estimé: ~\$$(($WARM_POOL_SIZE * 30))/mois"
