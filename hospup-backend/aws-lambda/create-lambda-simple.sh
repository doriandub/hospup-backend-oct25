#!/bin/bash

echo "🚀 Création Simple AWS Lambda - hospup-video-generator"
echo "===================================================="

# Configuration
FUNCTION_NAME="hospup-video-generator"
ACCOUNT_ID="412655955859"
REGION="eu-west-1"
BUCKET_NAME="hospup-files"

echo "🔧 Configuration:"
echo "Function: $FUNCTION_NAME"
echo "Bucket: $BUCKET_NAME" 
echo "Region: $REGION"
echo ""

echo "1️⃣ Test permissions existantes..."
if ! ./aws-wrapper.sh sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS non configuré"
    exit 1
fi

echo "✅ AWS configuré"
echo ""

echo "2️⃣ Création de la fonction Lambda..."

# Vérifier si la fonction existe déjà
if ./aws-wrapper.sh lambda get-function --function-name $FUNCTION_NAME > /dev/null 2>&1; then
    echo "⚠️ Fonction existe déjà - Mise à jour du code..."
    
    ./aws-wrapper.sh lambda update-function-code \
      --function-name $FUNCTION_NAME \
      --zip-file fileb://hospup-video-generator.zip > /dev/null
    
    if [ $? -eq 0 ]; then
        echo "✅ Code Lambda mis à jour"
    else
        echo "❌ Échec mise à jour code"
        exit 1
    fi
else
    echo "📦 Création nouvelle fonction Lambda..."
    
    # Pour créer la Lambda, on a besoin d'un rôle IAM minimal
    # On va essayer avec un rôle basique AWS géré
    LAMBDA_ROLE_ARN="arn:aws:iam::$ACCOUNT_ID:role/lambda-execution-role"
    
    ./aws-wrapper.sh lambda create-function \
      --function-name $FUNCTION_NAME \
      --runtime python3.9 \
      --role $LAMBDA_ROLE_ARN \
      --handler video-generator.lambda_handler \
      --zip-file fileb://hospup-video-generator.zip \
      --timeout 900 \
      --memory-size 512 \
      --description "Hospup video generation via AWS MediaConvert" > /dev/null
    
    if [ $? -eq 0 ]; then
        echo "✅ Fonction Lambda créée"
    else
        echo "❌ Échec création Lambda - Il faut créer manuellement via console AWS"
        echo ""
        echo "🎯 SOLUTION MANUELLE:"
        echo "1. Aller sur https://console.aws.amazon.com/lambda/"
        echo "2. Créer fonction '$FUNCTION_NAME'"
        echo "3. Runtime: Python 3.9"
        echo "4. Uploader: hospup-video-generator.zip"
        echo "5. Handler: video-generator.lambda_handler"
        echo "6. Timeout: 15 minutes"
        echo "7. Memory: 512 MB"
        exit 1
    fi
fi

echo ""
echo "3️⃣ Configuration variables d'environnement..."

./aws-wrapper.sh lambda update-function-configuration \
  --function-name $FUNCTION_NAME \
  --environment Variables="{
    \"S3_BUCKET\": \"$BUCKET_NAME\",
    \"S3_OUTPUT_PREFIX\": \"generated-videos/\",
    \"MEDIA_CONVERT_ROLE_ARN\": \"arn:aws:iam::$ACCOUNT_ID:role/hospup-mediaconvert-role\"
  }" > /dev/null

if [ $? -eq 0 ]; then
    echo "✅ Variables d'environnement configurées"
else
    echo "⚠️ Échec configuration variables - Continuer manuellement"
fi

echo ""
echo "4️⃣ Test de la fonction..."

# Test simple
cat > /tmp/test-payload.json << 'EOF'
{
  "body": "{\"property_id\":\"1\",\"template_id\":\"test\",\"segments\":[],\"text_overlays\":[],\"total_duration\":30}"
}
EOF

./aws-wrapper.sh lambda invoke \
  --function-name $FUNCTION_NAME \
  --payload file:///tmp/test-payload.json \
  /tmp/lambda-response.json > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✅ Test Lambda réussi"
    echo "Réponse:"
    cat /tmp/lambda-response.json | python3 -c "import sys, json; print(json.dumps(json.load(sys.stdin), indent=2))" 2>/dev/null || cat /tmp/lambda-response.json
else
    echo "⚠️ Test Lambda échoué - La fonction existe mais peut avoir besoin de rôles IAM"
fi

echo ""
echo "🎉 LAMBDA DÉPLOYÉE!"
echo "ARN: arn:aws:lambda:$REGION:$ACCOUNT_ID:function:$FUNCTION_NAME"
echo ""
echo "🔗 Railway peut maintenant appeler cette Lambda!"
echo "Les erreurs 'Function not found' vont disparaître."

# Nettoyage
rm -f /tmp/test-payload.json /tmp/lambda-response.json