#!/bin/bash
# 🚀 Deploy Clean MediaConvert Solution

echo "🎬 Deploying Clean MediaConvert Solution..."

# 1. Update video-generator Lambda
echo "📦 Updating video-generator Lambda..."
./aws-wrapper.sh lambda update-function-code \
    --function-name hospup-video-generator \
    --zip-file fileb://lambda-clean-solution.zip

# 2. Set environment variables
echo "🔧 Setting environment variables..."
./aws-wrapper.sh lambda update-function-configuration \
    --function-name hospup-video-generator \
    --environment Variables='{
        "S3_BUCKET_NAME":"hospup-files",
        "MEDIACONVERT_ROLE_ARN":"arn:aws:iam::412655955859:role/MediaConvertServiceRole"
    }'

# 3. Update callback Lambda (same ZIP works)
echo "📡 Updating callback Lambda..."
./aws-wrapper.sh lambda update-function-code \
    --function-name mediaconvert-callback \
    --zip-file fileb://lambda-clean-solution.zip

# 4. Set callback environment
echo "🔧 Setting callback environment..."
./aws-wrapper.sh lambda update-function-configuration \
    --function-name mediaconvert-callback \
    --environment Variables='{
        "S3_BUCKET_NAME":"hospup-files",
        "RAILWAY_CALLBACK_URL":"https://web-production-b52f.up.railway.app/api/v1/videos/aws-callback"
    }'

echo "✅ Clean solution deployed!"
echo ""
echo "🎯 SOLUTION RESUMÉ:"
echo "   📥 Input: custom_script.clips + text_overlays"
echo "   🎬 MediaConvert: Génère vidéo avec TTML burn-in"
echo "   📁 Output: s3://hospup-files/videos/{user_id}/{property_id}/{job_id}.mp4"
echo "   📡 Callback: Met à jour Supabase via Railway"
echo "   🚫 No immediate webhook - only real completion"
echo ""
echo "🧪 Test avec:"
echo "   ./aws-wrapper.sh lambda invoke --function-name hospup-video-generator response.json --payload file://test-payload.json"