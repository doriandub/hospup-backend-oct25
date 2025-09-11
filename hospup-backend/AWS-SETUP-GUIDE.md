# 🚀 Configuration AWS - Système Vidéo Hospup

## Étape 1: Configuration AWS CLI

```bash
# Installer AWS CLI (si pas encore fait)
brew install awscli

# Configurer AWS CLI avec vos credentials
aws configure
# AWS Access Key ID: [Votre Access Key]
# AWS Secret Access Key: [Votre Secret Key] 
# Default region name: eu-west-1
# Default output format: json
```

## Étape 2: Création des Rôles IAM

### 2.1 Rôle MediaConvert

```bash
# Créer le trust policy pour MediaConvert
cat > mediaconvert-trust-policy.json << EOF
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

# Créer le rôle MediaConvert
aws iam create-role \
  --role-name HospupMediaConvertRole \
  --assume-role-policy-document file://mediaconvert-trust-policy.json \
  --description "Rôle pour MediaConvert génération vidéos Hospup"

# Attacher les permissions S3
aws iam attach-role-policy \
  --role-name HospupMediaConvertRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

# Attacher les permissions MediaConvert
aws iam attach-role-policy \
  --role-name HospupMediaConvertRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonAPIGatewayInvokeFullAccess
```

### 2.2 Rôle Lambda

```bash
# Créer le trust policy pour Lambda
cat > lambda-trust-policy.json << EOF
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

# Créer le rôle Lambda
aws iam create-role \
  --role-name HospupLambdaExecutionRole \
  --assume-role-policy-document file://lambda-trust-policy.json \
  --description "Rôle d'exécution Lambda pour génération vidéos Hospup"

# Attacher les permissions de base Lambda
aws iam attach-role-policy \
  --role-name HospupLambdaExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Attacher les permissions S3
aws iam attach-role-policy \
  --role-name HospupLambdaExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

# Créer une politique personnalisée pour MediaConvert
cat > mediaconvert-lambda-policy.json << EOF
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

aws iam create-policy \
  --policy-name HospupMediaConvertLambdaPolicy \
  --policy-document file://mediaconvert-lambda-policy.json \
  --description "Permissions MediaConvert pour Lambda Hospup"

# Récupérer l'ARN de la politique et l'attacher
POLICY_ARN=$(aws iam list-policies --query 'Policies[?PolicyName==`HospupMediaConvertLambdaPolicy`].Arn' --output text)
aws iam attach-role-policy \
  --role-name HospupLambdaExecutionRole \
  --policy-arn $POLICY_ARN
```

## Étape 3: Vérification du Bucket S3

```bash
# Vérifier si le bucket existe
aws s3 ls s3://hospup-videos/ 2>/dev/null && echo "✅ Bucket existe" || echo "❌ Bucket n'existe pas"

# Si le bucket n'existe pas, le créer
aws s3 mb s3://hospup-videos --region eu-west-1

# Configurer les permissions CORS pour le bucket
cat > cors-config.json << EOF
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
  --cors-configuration file://cors-config.json
```

## Étape 4: Récupérer les ARNs

```bash
# Récupérer l'ARN du rôle MediaConvert
MEDIACONVERT_ROLE_ARN=$(aws iam get-role --role-name HospupMediaConvertRole --query 'Role.Arn' --output text)
echo "MediaConvert Role ARN: $MEDIACONVERT_ROLE_ARN"

# Récupérer l'ARN du rôle Lambda
LAMBDA_ROLE_ARN=$(aws iam get-role --role-name HospupLambdaExecutionRole --query 'Role.Arn' --output text)
echo "Lambda Role ARN: $LAMBDA_ROLE_ARN"

# Récupérer l'Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Account ID: $ACCOUNT_ID"
```

## Étape 5: Variables d'Environnement

### Variables pour Railway Backend:

```bash
MEDIA_CONVERT_ROLE_ARN=arn:aws:iam::ACCOUNT_ID:role/HospupMediaConvertRole
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
AWS_REGION=eu-west-1
S3_BUCKET=hospup-videos
```

### Variables pour Lambda:

```bash
S3_BUCKET=hospup-videos
S3_OUTPUT_PREFIX=generated-videos/
MEDIA_CONVERT_ROLE_ARN=arn:aws:iam::ACCOUNT_ID:role/HospupMediaConvertRole
```

## Étape 6: Déploiement de la Lambda

```bash
# Aller dans le répertoire AWS Lambda
cd /Users/doriandubord/Desktop/hospup-project/hospup-backend/aws-lambda

# Installer les dépendances
pip install -r requirements.txt -t .

# Créer le package de déploiement
zip -r hospup-video-generator.zip . -x "*.git*" "*.DS_Store*"

# Créer la fonction Lambda
aws lambda create-function \
  --function-name hospup-video-generator \
  --runtime python3.9 \
  --role $LAMBDA_ROLE_ARN \
  --handler video-generator.lambda_handler \
  --zip-file fileb://hospup-video-generator.zip \
  --timeout 900 \
  --memory-size 512 \
  --environment Variables="{
    S3_BUCKET=hospup-videos,
    S3_OUTPUT_PREFIX=generated-videos/,
    MEDIA_CONVERT_ROLE_ARN=$MEDIACONVERT_ROLE_ARN
  }"

# Créer une seconde fonction pour le status check
aws lambda create-function \
  --function-name hospup-video-status \
  --runtime python3.9 \
  --role $LAMBDA_ROLE_ARN \
  --handler video-generator.check_job_status \
  --zip-file fileb://hospup-video-generator.zip \
  --timeout 30 \
  --memory-size 256
```

## Étape 7: Tester la Configuration

```bash
# Test simple de génération
aws lambda invoke \
  --function-name hospup-video-generator \
  --payload '{
    "body": "{
      \"property_id\": \"1\",
      \"template_id\": \"test\",
      \"segments\": [
        {
          \"id\": \"seg1\",
          \"video_url\": \"s3://hospup-videos/test-video.mp4\",
          \"start_time\": 0,
          \"end_time\": 10,
          \"duration\": 10,
          \"order\": 1
        }
      ],
      \"text_overlays\": [],
      \"total_duration\": 10
    }"
  }' \
  response.json

cat response.json
```

## ✅ Checklist de Validation

- [ ] AWS CLI installé et configuré
- [ ] Rôle MediaConvert créé
- [ ] Rôle Lambda créé  
- [ ] Bucket S3 existant et configuré
- [ ] Lambda function déployée
- [ ] Variables d'environnement Railway configurées
- [ ] Test de génération réussi

## 🚨 Points d'Attention

1. **Coûts**: MediaConvert coûte ~$0.015/min de vidéo générée
2. **Timeouts**: Lambda limitée à 15 minutes max
3. **Permissions**: Bien vérifier tous les ARNs et permissions
4. **Région**: Tout doit être dans la même région (eu-west-1)

## 📞 Support

En cas de problème:
1. Vérifier les logs CloudWatch
2. Tester les permissions avec AWS CLI
3. Vérifier que tous les ARNs sont corrects