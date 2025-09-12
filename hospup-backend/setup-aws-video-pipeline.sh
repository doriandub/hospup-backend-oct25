#!/bin/bash

# 🚀 Script automatisé pour configurer le pipeline vidéo AWS Hospup
# Usage: ./setup-aws-video-pipeline.sh

set -e  # Arrêter en cas d'erreur

echo "🚀 Configuration du pipeline vidéo AWS Hospup"
echo "============================================="

# Vérifier que AWS CLI est installé
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI n'est pas installé. Installation..."
    brew install awscli
fi

echo "✅ AWS CLI détecté"

# Vérifier les credentials AWS
if ! aws sts get-caller-identity &> /dev/null; then
    echo "⚠️  Credentials AWS non configurés"
    echo "📝 Veuillez configurer AWS CLI avec vos credentials:"
    echo ""
    echo "   aws configure"
    echo ""
    echo "   AWS Access Key ID: [Votre Access Key]"
    echo "   AWS Secret Access Key: [Votre Secret Key]"
    echo "   Default region name: eu-west-1"
    echo "   Default output format: json"
    echo ""
    echo "🔗 Comment obtenir vos credentials:"
    echo "   1. Connexion AWS Console → IAM"
    echo "   2. Users → Votre utilisateur → Security credentials"
    echo "   3. Create access key → CLI access"
    echo ""
    read -p "Appuyez sur Entrée quand c'est fait..."
    
    # Vérifier à nouveau
    if ! aws sts get-caller-identity &> /dev/null; then
        echo "❌ Credentials toujours incorrects. Arrêt du script."
        exit 1
    fi
fi

# Récupérer l'Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "🆔 AWS Account ID: $ACCOUNT_ID"

echo ""
echo "🔑 Étape 1: Création des rôles IAM"
echo "================================="

# Trust policy pour MediaConvert
cat > /tmp/mediaconvert-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "mediaconvert.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Trust policy pour Lambda
cat > /tmp/lambda-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Politique personnalisée pour MediaConvert
cat > /tmp/mediaconvert-lambda-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "mediaconvert:*",
        "iam:PassRole"
      ],
      "Resource": "*"
    }
  ]
}
EOF

echo "📋 Création du rôle MediaConvert..."
aws iam create-role \
  --role-name HospupMediaConvertRole \
  --assume-role-policy-document file:///tmp/mediaconvert-trust-policy.json \
  --description "Rôle pour MediaConvert génération vidéos Hospup" 2>/dev/null || echo "   (Rôle déjà existant)"

aws iam attach-role-policy \
  --role-name HospupMediaConvertRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess 2>/dev/null || true

aws iam attach-role-policy \
  --role-name HospupMediaConvertRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonAPIGatewayInvokeFullAccess 2>/dev/null || true

echo "📋 Création du rôle Lambda..."
aws iam create-role \
  --role-name HospupLambdaExecutionRole \
  --assume-role-policy-document file:///tmp/lambda-trust-policy.json \
  --description "Rôle d'exécution Lambda pour génération vidéos Hospup" 2>/dev/null || echo "   (Rôle déjà existant)"

aws iam attach-role-policy \
  --role-name HospupLambdaExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 2>/dev/null || true

aws iam attach-role-policy \
  --role-name HospupLambdaExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess 2>/dev/null || true

# Créer et attacher la politique personnalisée MediaConvert
aws iam create-policy \
  --policy-name HospupMediaConvertLambdaPolicy \
  --policy-document file:///tmp/mediaconvert-lambda-policy.json \
  --description "Permissions MediaConvert pour Lambda Hospup" 2>/dev/null || echo "   (Politique déjà existante)"

POLICY_ARN="arn:aws:iam::$ACCOUNT_ID:policy/HospupMediaConvertLambdaPolicy"
aws iam attach-role-policy \
  --role-name HospupLambdaExecutionRole \
  --policy-arn $POLICY_ARN 2>/dev/null || true

echo ""
echo "🪣 Étape 2: Configuration du bucket S3"
echo "======================================"

# Vérifier et créer le bucket S3
if aws s3 ls s3://hospup-videos/ 2>/dev/null; then
    echo "✅ Bucket hospup-videos existe déjà"
else
    echo "📋 Création du bucket hospup-videos..."
    aws s3 mb s3://hospup-videos --region eu-west-1
fi

# Configuration CORS
cat > /tmp/cors-config.json << 'EOF'
{
  "CORSRules": [
    {
      "AllowedOrigins": ["*"],
      "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
      "AllowedHeaders": ["*"],
      "MaxAgeSeconds": 3000
    }
  ]
}
EOF

echo "📋 Configuration CORS du bucket..."
aws s3api put-bucket-cors \
  --bucket hospup-videos \
  --cors-configuration file:///tmp/cors-config.json

echo ""
echo "⚡ Étape 3: Déploiement de la fonction Lambda"
echo "==========================================="

# Aller dans le répertoire AWS Lambda
cd aws-lambda

echo "📦 Installation des dépendances Python..."
pip3 install -r requirements.txt -t .

echo "📋 Création du package de déploiement..."
zip -r hospup-video-generator.zip . -x "*.git*" "*.DS_Store*" "*.pyc*" "__pycache__*"

# Récupérer les ARNs
MEDIACONVERT_ROLE_ARN=$(aws iam get-role --role-name HospupMediaConvertRole --query 'Role.Arn' --output text)
LAMBDA_ROLE_ARN=$(aws iam get-role --role-name HospupLambdaExecutionRole --query 'Role.Arn' --output text)

echo "📋 Déploiement de la fonction Lambda principale..."
aws lambda create-function \
  --function-name hospup-video-generator \
  --runtime python3.9 \
  --role $LAMBDA_ROLE_ARN \
  --handler video-generator.lambda_handler \
  --zip-file fileb://hospup-video-generator.zip \
  --timeout 900 \
  --memory-size 512 \
  --environment Variables="{S3_BUCKET=hospup-videos,S3_OUTPUT_PREFIX=generated-videos/,MEDIA_CONVERT_ROLE_ARN=$MEDIACONVERT_ROLE_ARN}" 2>/dev/null || {
    echo "   Fonction existe déjà, mise à jour du code..."
    aws lambda update-function-code \
      --function-name hospup-video-generator \
      --zip-file fileb://hospup-video-generator.zip
}

echo "📋 Déploiement de la fonction de statut..."
aws lambda create-function \
  --function-name hospup-video-status \
  --runtime python3.9 \
  --role $LAMBDA_ROLE_ARN \
  --handler video-generator.check_job_status \
  --zip-file fileb://hospup-video-generator.zip \
  --timeout 30 \
  --memory-size 256 2>/dev/null || {
    echo "   Fonction existe déjà, mise à jour du code..."
    aws lambda update-function-code \
      --function-name hospup-video-status \
      --zip-file fileb://hospup-video-generator.zip
}

# Retour au répertoire parent
cd ..

echo ""
echo "🚦 Étape 4: Variables d'environnement Railway"
echo "============================================"

echo ""
echo "📝 Ajouter ces variables dans Railway Dashboard:"
echo ""
echo "MEDIA_CONVERT_ROLE_ARN=$MEDIACONVERT_ROLE_ARN"
echo "AWS_ACCESS_KEY_ID=$(aws configure get aws_access_key_id)"
echo "AWS_SECRET_ACCESS_KEY=$(aws configure get aws_secret_access_key)"
echo "AWS_REGION=eu-west-1"
echo "S3_BUCKET=hospup-videos"
echo "AWS_LAMBDA_FUNCTION_NAME=hospup-video-generator"
echo ""

echo ""
echo "🧪 Étape 5: Test du pipeline"
echo "============================"

echo "📋 Test de la fonction Lambda..."
aws lambda invoke \
  --function-name hospup-video-generator \
  --payload '{"body": "{\"property_id\": \"test\", \"template_id\": \"test\", \"segments\": [{\"id\": \"seg1\", \"video_url\": \"s3://hospup-videos/test.mp4\", \"start_time\": 0, \"end_time\": 5, \"duration\": 5, \"order\": 1}], \"text_overlays\": [], \"total_duration\": 5}"}' \
  /tmp/lambda-response.json

echo "📋 Réponse Lambda:"
cat /tmp/lambda-response.json
echo ""

# Nettoyer les fichiers temporaires
rm -f /tmp/*.json
rm -f aws-lambda/hospup-video-generator.zip

echo ""
echo "✅ CONFIGURATION TERMINÉE !"
echo "=========================="
echo ""
echo "🎯 Prochaines étapes:"
echo "1. ✅ Ajouter les variables d'environnement dans Railway"
echo "2. ✅ Redéployer votre application Railway"
echo "3. ✅ Tester la génération de vidéo depuis /compose"
echo ""
echo "💰 Coûts estimés:"
echo "   • MediaConvert: ~0.015€/min de vidéo générée"
echo "   • Lambda: ~0.0001€ par invocation"
echo "   • S3: ~0.023€/GB stocké"
echo ""
echo "🎬 Le pipeline vidéo Hospup est prêt !"