# 🔐 Permissions AWS Requises pour Déploiement Lambda

## Problème Identifié

L'user AWS `hospup-s3-uploader` (Account: 412655955859) n'a pas les permissions nécessaires pour déployer l'infrastructure Lambda complète.

## Permissions Manquantes

### 1. Permissions IAM Requises
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:AttachRolePolicy", 
        "iam:GetRole",
        "iam:PassRole",
        "iam:CreatePolicy",
        "iam:GetPolicy",
        "iam:ListRoles"
      ],
      "Resource": "*"
    }
  ]
}
```

### 2. Permissions Lambda Requises
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration", 
        "lambda:GetFunction",
        "lambda:InvokeFunction",
        "lambda:ListFunctions"
      ],
      "Resource": "*"
    }
  ]
}
```

### 3. Permissions S3 Additionnelles
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow", 
      "Action": [
        "s3:CreateBucket",
        "s3:PutBucketCors",
        "s3:GetBucketLocation"
      ],
      "Resource": "*"
    }
  ]
}
```

## Solution Rapide

### Option 1: Ajouter Permissions (Recommandé)
Dans la console AWS IAM:
1. Aller sur l'user `hospup-s3-uploader`
2. Attacher la policy `IAMFullAccess` (temporairement)
3. Attacher la policy `AWSLambdaFullAccess` (temporairement)  
4. Réexécuter le déploiement
5. Retirer les permissions après déploiement

### Option 2: Déploiement Manuel Lambda
Si pas possible d'ajouter permissions, créer manuellement:

1. **Créer rôle IAM MediaConvert** dans console AWS
2. **Créer rôle IAM Lambda** dans console AWS  
3. **Créer fonction Lambda** avec le code de `video-generator.py`
4. **Configurer variables d'environnement** Lambda

## Variables Lambda Requises

Une fois la Lambda créée, configurer ces variables:

```bash
S3_BUCKET=hospup-videos
S3_OUTPUT_PREFIX=generated-videos/
MEDIA_CONVERT_ROLE_ARN=arn:aws:iam::412655955859:role/hospup-mediaconvert-role
```

## Test après Déploiement

La Lambda doit répondre à cet ARN: 
`arn:aws:lambda:eu-west-1:412655955859:function:hospup-video-generator`

Test avec:
```bash
aws lambda invoke \
  --function-name hospup-video-generator \
  --payload '{"body": "{\"property_id\":\"1\"}"}' \
  response.json
```

## Impact sur Railway

Une fois Lambda déployée, les erreurs "Function not found" dans Railway disparaîtront et la génération vidéo fonctionnera.