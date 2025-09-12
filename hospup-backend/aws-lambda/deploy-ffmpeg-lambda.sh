#!/bin/bash
# Script pour déployer le Lambda avec FFmpeg direct au lieu de MediaConvert

set -e

echo "🚀 Deploying FFmpeg Lambda video generator..."

# Configuration
LAMBDA_FUNCTION_NAME="hospup-video-generator"
REGION="eu-west-1"
ROLE_ARN="arn:aws:iam::412655955859:role/lambda-execution-role"
FFMPEG_LAYER_ARN="arn:aws:lambda:eu-west-1:533267276448:layer:ffmpeg:1"  # FFmpeg public layer

# Créer le package Lambda
echo "📦 Creating Lambda deployment package..."

# Nettoyer les anciens packages
rm -rf package/
rm -f hospup-video-generator-ffmpeg.zip

# Créer le répertoire package
mkdir -p package

# Installer les dépendances Python
pip3 install --target ./package -r requirements.txt

# Copier le code Lambda
cp video-generator.py package/

# Créer l'archive ZIP
cd package
zip -r ../hospup-video-generator-ffmpeg.zip .
cd ..

echo "✅ Lambda package created: $(du -h hospup-video-generator-ffmpeg.zip)"

# Déployer ou mettre à jour le Lambda
echo "☁️ Deploying to AWS Lambda..."

# Vérifier si la fonction existe déjà
if aws lambda get-function --function-name $LAMBDA_FUNCTION_NAME --region $REGION >/dev/null 2>&1; then
    echo "🔄 Updating existing Lambda function..."
    
    # Mettre à jour le code
    aws lambda update-function-code \
        --function-name $LAMBDA_FUNCTION_NAME \
        --zip-file fileb://hospup-video-generator-ffmpeg.zip \
        --region $REGION
    
    # Mettre à jour la configuration (ajouter la layer FFmpeg)
    aws lambda update-function-configuration \
        --function-name $LAMBDA_FUNCTION_NAME \
        --timeout 900 \
        --memory-size 3008 \
        --layers $FFMPEG_LAYER_ARN \
        --environment Variables='{
            "S3_BUCKET":"hospup-files",
            "S3_OUTPUT_PREFIX":"generated-videos/",
            "TEMP_DIR":"/tmp"
        }' \
        --region $REGION
    
    echo "✅ Lambda function updated successfully"
else
    echo "🆕 Creating new Lambda function..."
    
    # Créer la fonction
    aws lambda create-function \
        --function-name $LAMBDA_FUNCTION_NAME \
        --runtime python3.9 \
        --role $ROLE_ARN \
        --handler video-generator.lambda_handler \
        --zip-file fileb://hospup-video-generator-ffmpeg.zip \
        --timeout 900 \
        --memory-size 3008 \
        --layers $FFMPEG_LAYER_ARN \
        --environment Variables='{
            "S3_BUCKET":"hospup-files",
            "S3_OUTPUT_PREFIX":"generated-videos/",
            "TEMP_DIR":"/tmp"
        }' \
        --region $REGION
    
    echo "✅ Lambda function created successfully"
fi

# Nettoyer les fichiers temporaires
echo "🧹 Cleaning up..."
rm -rf package/
rm -f hospup-video-generator-ffmpeg.zip

echo "🎉 FFmpeg Lambda deployment completed!"
echo "📋 Configuration:"
echo "   - Function: $LAMBDA_FUNCTION_NAME"
echo "   - Region: $REGION"
echo "   - Memory: 3008 MB"
echo "   - Timeout: 15 minutes"
echo "   - FFmpeg Layer: $FFMPEG_LAYER_ARN"
echo ""
echo "🚨 Important: FFmpeg Lambda should be 10x faster than MediaConvert!"