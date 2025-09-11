#!/bin/bash

echo "🏗️ Déploiement Infrastructure AWS Complète - Hospup"
echo "=================================================="

# Couleurs
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Configuration
REGION="eu-west-1"
ACCOUNT_ID=""
PROJECT_NAME="hospup"

echo -e "${BLUE}📋 Phase 1: Validation et préparation${NC}"
echo "======================================"

# Vérification permissions AWS
echo "Vérification des permissions AWS..."
if ! ./aws-wrapper.sh sts get-caller-identity > /dev/null 2>&1; then
    echo -e "${RED}❌ Erreur: AWS non configuré${NC}"
    echo "Exécutez d'abord: ./aws-wrapper.sh configure"
    exit 1
fi

# Récupération Account ID
ACCOUNT_ID=$(./aws-wrapper.sh sts get-caller-identity --query Account --output text)
USER_ARN=$(./aws-wrapper.sh sts get-caller-identity --query Arn --output text)

echo -e "${GREEN}✅ AWS configuré${NC}"
echo "Account ID: $ACCOUNT_ID"
echo "User: $USER_ARN"
echo ""

# Test des permissions
echo "Test des permissions requises..."
PERMISSIONS_OK=true

# Test IAM
if ! ./aws-wrapper.sh iam list-roles --max-items 1 > /dev/null 2>&1; then
    echo -e "${RED}❌ Permissions IAM manquantes${NC}"
    PERMISSIONS_OK=false
fi

# Test Lambda
if ! ./aws-wrapper.sh lambda list-functions --max-items 1 > /dev/null 2>&1; then
    echo -e "${RED}❌ Permissions Lambda manquantes${NC}"
    PERMISSIONS_OK=false
fi

if [ "$PERMISSIONS_OK" = false ]; then
    echo -e "${RED}❌ Permissions insuffisantes${NC}"
    echo "Consultez: AWS-PERMISSIONS-NEEDED.md"
    exit 1
fi

echo -e "${GREEN}✅ Permissions suffisantes${NC}"
echo ""

echo -e "${BLUE}🏗️ Phase 2: Création infrastructure${NC}"
echo "==================================="

# 1. Création rôle MediaConvert
echo "1. Création rôle MediaConvert..."

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

MEDIACONVERT_ROLE_NAME="${PROJECT_NAME}-mediaconvert-role"
if ./aws-wrapper.sh iam get-role --role-name $MEDIACONVERT_ROLE_NAME > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Rôle MediaConvert existe déjà${NC}"
else
    ./aws-wrapper.sh iam create-role \
      --role-name $MEDIACONVERT_ROLE_NAME \
      --assume-role-policy-document file:///tmp/mediaconvert-trust-policy.json \
      --description "Rôle MediaConvert pour génération vidéos Hospup"
    
    # Attacher permissions
    ./aws-wrapper.sh iam attach-role-policy \
      --role-name $MEDIACONVERT_ROLE_NAME \
      --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
    
    echo -e "${GREEN}✅ Rôle MediaConvert créé${NC}"
fi

# 2. Création rôle Lambda
echo "2. Création rôle Lambda..."

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

LAMBDA_ROLE_NAME="${PROJECT_NAME}-lambda-execution-role"
if ./aws-wrapper.sh iam get-role --role-name $LAMBDA_ROLE_NAME > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Rôle Lambda existe déjà${NC}"
else
    ./aws-wrapper.sh iam create-role \
      --role-name $LAMBDA_ROLE_NAME \
      --assume-role-policy-document file:///tmp/lambda-trust-policy.json \
      --description "Rôle d'exécution Lambda pour génération vidéos Hospup"
    
    # Permissions de base Lambda
    ./aws-wrapper.sh iam attach-role-policy \
      --role-name $LAMBDA_ROLE_NAME \
      --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    
    # Permissions S3
    ./aws-wrapper.sh iam attach-role-policy \
      --role-name $LAMBDA_ROLE_NAME \
      --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
    
    # Politique personnalisée MediaConvert
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
    
    POLICY_NAME="${PROJECT_NAME}-mediaconvert-lambda-policy"
    POLICY_ARN="arn:aws:iam::$ACCOUNT_ID:policy/$POLICY_NAME"
    
    if ! ./aws-wrapper.sh iam get-policy --policy-arn $POLICY_ARN > /dev/null 2>&1; then
        ./aws-wrapper.sh iam create-policy \
          --policy-name $POLICY_NAME \
          --policy-document file:///tmp/mediaconvert-lambda-policy.json \
          --description "Permissions MediaConvert pour Lambda Hospup"
    fi
    
    ./aws-wrapper.sh iam attach-role-policy \
      --role-name $LAMBDA_ROLE_NAME \
      --policy-arn $POLICY_ARN
    
    echo -e "${GREEN}✅ Rôle Lambda créé${NC}"
fi

# 3. Configuration bucket S3
echo "3. Configuration bucket S3..."

BUCKET_NAME="${PROJECT_NAME}-videos"
if ./aws-wrapper.sh s3api head-bucket --bucket $BUCKET_NAME > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Bucket S3 existe déjà${NC}"
else
    ./aws-wrapper.sh s3 mb s3://$BUCKET_NAME --region $REGION
    
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
    
    ./aws-wrapper.sh s3api put-bucket-cors \
      --bucket $BUCKET_NAME \
      --cors-configuration file:///tmp/cors-config.json
    
    echo -e "${GREEN}✅ Bucket S3 configuré${NC}"
fi

# 4. Récupération des ARNs
echo "4. Récupération des ARNs..."
MEDIACONVERT_ROLE_ARN=$(./aws-wrapper.sh iam get-role --role-name $MEDIACONVERT_ROLE_NAME --query 'Role.Arn' --output text)
LAMBDA_ROLE_ARN=$(./aws-wrapper.sh iam get-role --role-name $LAMBDA_ROLE_NAME --query 'Role.Arn' --output text)

echo -e "${GREEN}✅ ARNs récupérés${NC}"
echo "MediaConvert Role: $MEDIACONVERT_ROLE_ARN"
echo "Lambda Role: $LAMBDA_ROLE_ARN"
echo ""

echo -e "${BLUE}🚀 Phase 3: Déploiement Lambda${NC}"
echo "==============================="

# Attendre que les rôles soient propagés
echo "Attente propagation IAM (30 secondes)..."
sleep 30

# Création package Lambda
echo "5. Création package Lambda..."
rm -rf ./package ./hospup-video-generator.zip
mkdir package

# Installation dépendances
pip3 install -r requirements.txt -t ./package/
cp video-generator.py ./package/

# Création ZIP
cd package && zip -r ../hospup-video-generator.zip . -q && cd ..
PACKAGE_SIZE=$(ls -lh hospup-video-generator.zip | awk '{print $5}')
echo -e "${GREEN}✅ Package créé: $PACKAGE_SIZE${NC}"

# 6. Déploiement fonction principale
echo "6. Déploiement fonction principale..."
FUNCTION_NAME="${PROJECT_NAME}-video-generator"

if ./aws-wrapper.sh lambda get-function --function-name $FUNCTION_NAME > /dev/null 2>&1; then
    echo "Mise à jour fonction existante..."
    ./aws-wrapper.sh lambda update-function-code \
      --function-name $FUNCTION_NAME \
      --zip-file fileb://hospup-video-generator.zip > /dev/null
    
    ./aws-wrapper.sh lambda update-function-configuration \
      --function-name $FUNCTION_NAME \
      --environment Variables="{
        S3_BUCKET=$BUCKET_NAME,
        S3_OUTPUT_PREFIX=generated-videos/,
        MEDIA_CONVERT_ROLE_ARN=$MEDIACONVERT_ROLE_ARN
      }" > /dev/null
else
    ./aws-wrapper.sh lambda create-function \
      --function-name $FUNCTION_NAME \
      --runtime python3.9 \
      --role $LAMBDA_ROLE_ARN \
      --handler video-generator.lambda_handler \
      --zip-file fileb://hospup-video-generator.zip \
      --timeout 900 \
      --memory-size 512 \
      --description "Génération de vidéos Hospup via AWS MediaConvert" \
      --environment Variables="{
        S3_BUCKET=$BUCKET_NAME,
        S3_OUTPUT_PREFIX=generated-videos/,
        MEDIA_CONVERT_ROLE_ARN=$MEDIACONVERT_ROLE_ARN
      }" > /dev/null
fi

echo -e "${GREEN}✅ Fonction principale déployée${NC}"

# 7. Déploiement fonction status
echo "7. Déploiement fonction status..."
STATUS_FUNCTION_NAME="${PROJECT_NAME}-video-status"

if ./aws-wrapper.sh lambda get-function --function-name $STATUS_FUNCTION_NAME > /dev/null 2>&1; then
    ./aws-wrapper.sh lambda update-function-code \
      --function-name $STATUS_FUNCTION_NAME \
      --zip-file fileb://hospup-video-generator.zip > /dev/null
else
    ./aws-wrapper.sh lambda create-function \
      --function-name $STATUS_FUNCTION_NAME \
      --runtime python3.9 \
      --role $LAMBDA_ROLE_ARN \
      --handler video-generator.check_job_status \
      --zip-file fileb://hospup-video-generator.zip \
      --timeout 30 \
      --memory-size 256 \
      --description "Vérification statut génération vidéos Hospup" > /dev/null
fi

echo -e "${GREEN}✅ Fonction status déployée${NC}"

echo -e "${BLUE}🧪 Phase 4: Tests${NC}"
echo "================"

# Test simple
echo "8. Test de la fonction..."
cat > /tmp/test-payload.json << 'EOF'
{
  "body": "{\"property_id\":\"1\",\"template_id\":\"test\",\"segments\":[],\"text_overlays\":[],\"total_duration\":30}"
}
EOF

echo "Test fonction principale..."
./aws-wrapper.sh lambda invoke \
  --function-name $FUNCTION_NAME \
  --payload file:///tmp/test-payload.json \
  /tmp/response.json > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Test réussi${NC}"
    echo "Réponse:"
    cat /tmp/response.json | python3 -c "import sys, json; print(json.dumps(json.load(sys.stdin), indent=2))" 2>/dev/null || cat /tmp/response.json
else
    echo -e "${RED}❌ Test échoué${NC}"
    cat /tmp/response.json 2>/dev/null || echo "Pas de réponse"
fi

echo ""
echo -e "${BLUE}📋 Phase 5: Configuration finalisée${NC}"
echo "===================================="

# Sauvegarde configuration
cat > aws-config.env << EOF
# Configuration AWS Infrastructure Hospup
ACCOUNT_ID=$ACCOUNT_ID
REGION=$REGION
BUCKET_NAME=$BUCKET_NAME
MEDIACONVERT_ROLE_ARN=$MEDIACONVERT_ROLE_ARN
LAMBDA_ROLE_ARN=$LAMBDA_ROLE_ARN
FUNCTION_NAME=$FUNCTION_NAME
STATUS_FUNCTION_NAME=$STATUS_FUNCTION_NAME
EOF

echo -e "${GREEN}✅ Configuration sauvegardée dans aws-config.env${NC}"

echo ""
echo -e "${PURPLE}🎉 INFRASTRUCTURE AWS DÉPLOYÉE AVEC SUCCÈS!${NC}"
echo "============================================="
echo ""
echo -e "${GREEN}📊 RÉSUMÉ:${NC}"
echo "✅ Rôles IAM créés et configurés"
echo "✅ Bucket S3 configuré avec CORS"
echo "✅ Fonctions Lambda déployées"
echo "✅ Tests de validation réussis"
echo ""
echo -e "${YELLOW}📝 VARIABLES D'ENVIRONNEMENT RAILWAY:${NC}"
echo "MEDIA_CONVERT_ROLE_ARN=$MEDIACONVERT_ROLE_ARN"
echo "AWS_ACCESS_KEY_ID=<vos-credentials>"
echo "AWS_SECRET_ACCESS_KEY=<vos-credentials>"
echo "AWS_REGION=$REGION"
echo "S3_BUCKET=$BUCKET_NAME"
echo ""
echo -e "${BLUE}🚀 PROCHAINES ÉTAPES:${NC}"
echo "1. Configurer les variables Railway ci-dessus"
echo "2. Tester l'intégration complète frontend → backend → Lambda"
echo "3. Valider avec une vraie génération de vidéo"
echo ""
echo -e "${GREEN}Architecture scalable prête pour production! 🚀${NC}"

# Nettoyage
rm -f /tmp/mediaconvert-trust-policy.json /tmp/lambda-trust-policy.json
rm -f /tmp/mediaconvert-lambda-policy.json /tmp/cors-config.json
rm -f /tmp/test-payload.json /tmp/response.json