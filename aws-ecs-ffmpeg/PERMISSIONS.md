# 🔐 Permissions AWS requises pour déploiement ECS

## ❌ Problème actuel

Le user AWS actuel (`hospup-s3-uploader`) n'a que les permissions S3.

```
Account: 412655955859
User: hospup-s3-uploader
Permissions actuelles: S3 uniquement
```

## ✅ Permissions nécessaires

Pour déployer l'infrastructure ECS, il faut ajouter ces permissions:

### 1. ECR (Elastic Container Registry)
```json
{
  "Effect": "Allow",
  "Action": [
    "ecr:CreateRepository",
    "ecr:DescribeRepositories",
    "ecr:GetAuthorizationToken",
    "ecr:BatchCheckLayerAvailability",
    "ecr:GetDownloadUrlForLayer",
    "ecr:BatchGetImage",
    "ecr:PutImage",
    "ecr:InitiateLayerUpload",
    "ecr:UploadLayerPart",
    "ecr:CompleteLayerUpload"
  ],
  "Resource": "*"
}
```

### 2. ECS (Elastic Container Service)
```json
{
  "Effect": "Allow",
  "Action": [
    "ecs:CreateCluster",
    "ecs:DescribeClusters",
    "ecs:RegisterTaskDefinition",
    "ecs:DescribeTaskDefinition",
    "ecs:CreateService",
    "ecs:DescribeServices",
    "ecs:UpdateService",
    "ecs:ListTasks",
    "ecs:DescribeTasks"
  ],
  "Resource": "*"
}
```

### 3. SQS
```json
{
  "Effect": "Allow",
  "Action": [
    "sqs:CreateQueue",
    "sqs:GetQueueUrl",
    "sqs:GetQueueAttributes",
    "sqs:SendMessage",
    "sqs:ReceiveMessage",
    "sqs:DeleteMessage"
  ],
  "Resource": "*"
}
```

### 4. IAM (pour créer les rôles ECS)
```json
{
  "Effect": "Allow",
  "Action": [
    "iam:CreateRole",
    "iam:GetRole",
    "iam:AttachRolePolicy",
    "iam:PutRolePolicy",
    "iam:PassRole"
  ],
  "Resource": "*"
}
```

### 5. EC2 (pour VPC/Subnets)
```json
{
  "Effect": "Allow",
  "Action": [
    "ec2:DescribeVpcs",
    "ec2:DescribeSubnets",
    "ec2:DescribeSecurityGroups"
  ],
  "Resource": "*"
}
```

### 6. Application Auto Scaling
```json
{
  "Effect": "Allow",
  "Action": [
    "application-autoscaling:RegisterScalableTarget",
    "application-autoscaling:PutScalingPolicy",
    "application-autoscaling:DescribeScalableTargets",
    "application-autoscaling:DescribeScalingPolicies"
  ],
  "Resource": "*"
}
```

### 7. CloudWatch (pour logs et alarmes)
```json
{
  "Effect": "Allow",
  "Action": [
    "logs:CreateLogGroup",
    "logs:CreateLogStream",
    "logs:PutLogEvents",
    "logs:DescribeLogGroups",
    "cloudwatch:PutMetricAlarm",
    "cloudwatch:DescribeAlarms",
    "cloudwatch:PutDashboard"
  ],
  "Resource": "*"
}
```

## 🚀 Solutions

### Option 1: Ajouter permissions au user existant (Recommandé)

1. **Via AWS Console:**
   - Aller sur IAM: https://console.aws.amazon.com/iam/
   - Chercher user `hospup-s3-uploader`
   - Cliquer "Add permissions" → "Attach policies directly"
   - Ajouter les policies managed AWS:
     - `AmazonECS_FullAccess`
     - `AmazonEC2ContainerRegistryFullAccess`
     - `AmazonSQSFullAccess`
     - `IAMFullAccess` (ou créer custom policy plus restrictive)
     - `CloudWatchFullAccess`
     - `ApplicationAutoScalingFullAccess`

2. **Via AWS CLI:**
```bash
# Attacher les policies managed
aws iam attach-user-policy \
  --user-name hospup-s3-uploader \
  --policy-arn arn:aws:iam::aws:policy/AmazonECS_FullAccess

aws iam attach-user-policy \
  --user-name hospup-s3-uploader \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryFullAccess

aws iam attach-user-policy \
  --user-name hospup-s3-uploader \
  --policy-arn arn:aws:iam::aws:policy/AmazonSQSFullAccess

# Etc...
```

### Option 2: Créer un nouveau user "hospup-deployer"

```bash
# Créer un nouveau user avec toutes les permissions
aws iam create-user --user-name hospup-deployer

# Attacher les policies
aws iam attach-user-policy \
  --user-name hospup-deployer \
  --policy-arn arn:aws:iam::aws:policy/AmazonECS_FullAccess

# Générer access keys
aws iam create-access-key --user-name hospup-deployer

# Configurer dans AWS CLI
aws configure --profile hospup-deployer
```

Puis utiliser:
```bash
AWS_PROFILE=hospup-deployer ./deploy.sh
```

### Option 3: Utiliser AWS CloudFormation (Infrastructure as Code)

Créer un CloudFormation stack qui gère toutes les permissions automatiquement.

## 📋 Policy IAM complète (Custom)

Si tu veux créer une policy custom minimale:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:*",
        "ecs:*",
        "sqs:*",
        "iam:CreateRole",
        "iam:GetRole",
        "iam:AttachRolePolicy",
        "iam:PutRolePolicy",
        "iam:PassRole",
        "ec2:DescribeVpcs",
        "ec2:DescribeSubnets",
        "ec2:DescribeSecurityGroups",
        "application-autoscaling:*",
        "logs:*",
        "cloudwatch:*"
      ],
      "Resource": "*"
    }
  ]
}
```

Sauvegarder dans `hospup-ecs-deployment-policy.json` puis:

```bash
# Créer la policy
aws iam create-policy \
  --policy-name HospupECSDeploymentPolicy \
  --policy-document file://hospup-ecs-deployment-policy.json

# Attacher au user
aws iam attach-user-policy \
  --user-name hospup-s3-uploader \
  --policy-arn arn:aws:iam::412655955859:policy/HospupECSDeploymentPolicy
```

## ⚠️ Sécurité

**Important:** Ces permissions sont larges pour simplifier le déploiement. En production, tu devrais:

1. Créer des policies plus restrictives (limiter aux ressources spécifiques)
2. Utiliser des rôles IAM temporaires au lieu de access keys permanentes
3. Activer MFA sur les comptes avec permissions larges
4. Logger toutes les actions via CloudTrail

## 🎯 Prochaine étape

**Choisis une option et je continuerai le déploiement:**

1. **Option rapide:** Ajouter permissions via AWS Console (2 min)
2. **Option CLI:** Je te génère les commandes à exécuter
3. **Option alternative:** On utilise un autre compte AWS avec plus de permissions
