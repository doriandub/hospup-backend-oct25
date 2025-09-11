#!/bin/bash

echo "🚀 Configuration AWS pour Hospup - Système Vidéo"
echo "================================================="

# Couleurs pour l'affichage
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Vérification AWS CLI
echo -e "${BLUE}1. Vérification AWS CLI...${NC}"
if ! command -v aws &> /dev/null; then
    echo -e "${YELLOW}AWS CLI non trouvé. Installation en cours...${NC}"
    
    # Installation AWS CLI via curl (méthode alternative)
    echo "Téléchargement AWS CLI..."
    cd /tmp
    curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
    sudo installer -pkg AWSCLIV2.pkg -target /
    
    # Vérification
    if command -v aws &> /dev/null; then
        echo -e "${GREEN}✅ AWS CLI installé avec succès${NC}"
    else
        echo -e "${RED}❌ Échec installation AWS CLI${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ AWS CLI déjà installé${NC}"
fi

aws --version

# Vérification configuration AWS
echo -e "${BLUE}2. Vérification configuration AWS...${NC}"
if aws sts get-caller-identity &> /dev/null; then
    echo -e "${GREEN}✅ AWS configuré correctement${NC}"
    aws sts get-caller-identity
else
    echo -e "${YELLOW}⚠️  AWS non configuré. Veuillez exécuter:${NC}"
    echo "aws configure"
    echo "Puis relancer ce script."
    exit 1
fi

# Récupération Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Account ID: $ACCOUNT_ID"

echo -e "${BLUE}3. Création des rôles IAM...${NC}"

# Trust policy pour MediaConvert
cat > /tmp/mediaconvert-trust-policy.json << EOF
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

# Création rôle MediaConvert
echo "Création du rôle MediaConvert..."
if aws iam get-role --role-name HospupMediaConvertRole &> /dev/null; then
    echo -e "${YELLOW}Rôle MediaConvert existe déjà${NC}"
else
    aws iam create-role \
      --role-name HospupMediaConvertRole \
      --assume-role-policy-document file:///tmp/mediaconvert-trust-policy.json \
      --description "Rôle pour MediaConvert génération vidéos Hospup"
    
    # Attacher permissions
    aws iam attach-role-policy \
      --role-name HospupMediaConvertRole \
      --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
    
    echo -e "${GREEN}✅ Rôle MediaConvert créé${NC}"
fi

# Trust policy pour Lambda
cat > /tmp/lambda-trust-policy.json << EOF
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

# Création rôle Lambda
echo "Création du rôle Lambda..."
if aws iam get-role --role-name HospupLambdaExecutionRole &> /dev/null; then
    echo -e "${YELLOW}Rôle Lambda existe déjà${NC}"
else
    aws iam create-role \
      --role-name HospupLambdaExecutionRole \
      --assume-role-policy-document file:///tmp/lambda-trust-policy.json \
      --description "Rôle d'exécution Lambda pour génération vidéos Hospup"
    
    # Attacher permissions de base
    aws iam attach-role-policy \
      --role-name HospupLambdaExecutionRole \
      --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    
    aws iam attach-role-policy \
      --role-name HospupLambdaExecutionRole \
      --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
    
    # Politique personnalisée MediaConvert
    cat > /tmp/mediaconvert-lambda-policy.json << EOF
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
    
    # Créer et attacher la politique personnalisée
    if ! aws iam get-policy --policy-arn arn:aws:iam::$ACCOUNT_ID:policy/HospupMediaConvertLambdaPolicy &> /dev/null; then
        aws iam create-policy \
          --policy-name HospupMediaConvertLambdaPolicy \
          --policy-document file:///tmp/mediaconvert-lambda-policy.json \
          --description "Permissions MediaConvert pour Lambda Hospup"
    fi
    
    aws iam attach-role-policy \
      --role-name HospupLambdaExecutionRole \
      --policy-arn arn:aws:iam::$ACCOUNT_ID:policy/HospupMediaConvertLambdaPolicy
    
    echo -e "${GREEN}✅ Rôle Lambda créé${NC}"
fi

echo -e "${BLUE}4. Vérification bucket S3...${NC}"
if aws s3 ls s3://hospup-videos/ &> /dev/null; then
    echo -e "${GREEN}✅ Bucket S3 existe${NC}"
else
    echo "Création du bucket S3..."
    aws s3 mb s3://hospup-videos --region eu-west-1
    
    # Configuration CORS
    cat > /tmp/cors-config.json << EOF
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
    
    aws s3api put-bucket-cors \
      --bucket hospup-videos \
      --cors-configuration file:///tmp/cors-config.json
    
    echo -e "${GREEN}✅ Bucket S3 créé et configuré${NC}"
fi

echo -e "${BLUE}5. Récupération des ARNs...${NC}"
MEDIACONVERT_ROLE_ARN=$(aws iam get-role --role-name HospupMediaConvertRole --query 'Role.Arn' --output text)
LAMBDA_ROLE_ARN=$(aws iam get-role --role-name HospupLambdaExecutionRole --query 'Role.Arn' --output text)

echo -e "${GREEN}📋 INFORMATIONS DE CONFIGURATION:${NC}"
echo "================================="
echo "Account ID: $ACCOUNT_ID"
echo "MediaConvert Role ARN: $MEDIACONVERT_ROLE_ARN"
echo "Lambda Role ARN: $LAMBDA_ROLE_ARN"
echo ""

echo -e "${YELLOW}📝 Variables d'environnement pour Railway:${NC}"
echo "MEDIA_CONVERT_ROLE_ARN=$MEDIACONVERT_ROLE_ARN"
echo "AWS_ACCESS_KEY_ID=<your-access-key>"
echo "AWS_SECRET_ACCESS_KEY=<your-secret-key>"
echo "AWS_REGION=eu-west-1"
echo "S3_BUCKET=hospup-videos"
echo ""

# Sauvegarde dans un fichier
cat > ./aws-config.env << EOF
# Configuration AWS pour Hospup
ACCOUNT_ID=$ACCOUNT_ID
MEDIACONVERT_ROLE_ARN=$MEDIACONVERT_ROLE_ARN
LAMBDA_ROLE_ARN=$LAMBDA_ROLE_ARN
S3_BUCKET=hospup-videos
AWS_REGION=eu-west-1
EOF

echo -e "${GREEN}✅ Configuration sauvegardée dans aws-config.env${NC}"
echo -e "${BLUE}Prochaine étape: Déploiement de la Lambda function${NC}"
echo "Exécutez: ./deploy-lambda.sh"