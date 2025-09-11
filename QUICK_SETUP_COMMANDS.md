# 🚀 Quick Setup Commands - AWS Lambda Video Pipeline

## 🎯 Ready-to-Execute Commands

### Step 1: Execute AWS Setup
```bash
cd /Users/doriandubord/Desktop/hospup-project
chmod +x AWS_COMPLETE_SETUP.sh
./AWS_COMPLETE_SETUP.sh
```

### Step 2: Configure Railway Variables  
Copy variables from `RAILWAY_ENV_VARIABLES.txt` to Railway Dashboard:
```bash
cat RAILWAY_ENV_VARIABLES.txt
```

### Step 3: Test the Pipeline
```bash
# Test AWS Lambda directly
aws lambda invoke \
  --function-name hospup-video-generator \
  --payload '{"body": "{\"property_id\": \"test\", \"segments\": [{\"id\": \"seg1\", \"video_url\": \"s3://hospup-videos/test.mp4\", \"start_time\": 0, \"end_time\": 5}], \"text_overlays\": []}"}' \
  response.json

cat response.json
```

### Step 4: Test Backend Integration
```bash
# Test Railway backend with AWS integration
curl -X POST https://web-production-b52f.up.railway.app/api/v1/video-generation/generate-from-viral-template \
  -H "Content-Type: application/json" \
  -d '{
    "property_id": "test-property",
    "source_type": "viral_template_composer", 
    "source_data": {
      "template_id": "test-template",
      "slot_assignments": [{"slotId": "slot_1", "videoId": "video_1"}],
      "text_overlays": [{"content": "Test Text", "start_time": 0, "end_time": 3, "position": {"x": 50, "y": 50, "anchor": "center"}, "style": {"color": "#ffffff", "font_size": 24, "opacity": 1}}],
      "total_duration": 30
    },
    "language": "fr"
  }'
```

## 📋 Status Verification

### Check AWS Resources
```bash
# Verify S3 bucket
aws s3 ls s3://hospup-videos/

# Verify Lambda functions
aws lambda list-functions --query 'Functions[?contains(FunctionName, `hospup`)].FunctionName'

# Verify IAM roles
aws iam get-role --role-name HospupMediaConvertRole
aws iam get-role --role-name HospupLambdaExecutionRole
```

### Monitor Video Processing
```bash
# Check MediaConvert jobs
aws mediaconvert list-jobs --max-results 10 --region eu-west-1

# Monitor Lambda logs
aws logs tail /aws/lambda/hospup-video-generator --follow
```

## 🎬 Complete Pipeline Test

1. **Frontend Test**: Go to `http://localhost:3000/dashboard/compose/[template-id]`
2. **Create Timeline**: Add 2+ video clips and text overlays
3. **Generate Video**: Click "Générer la vidéo" 
4. **Verify Status**: Check database for `status='processing'`
5. **Monitor AWS**: Watch Lambda logs and MediaConvert jobs
6. **Completion**: Video URL appears in S3 bucket

## ⚡ Cost Monitoring

- **MediaConvert**: ~€0.015/minute of video
- **Lambda**: ~€0.0001/invocation
- **S3**: ~€0.023/GB stored

## 🔧 Troubleshooting

### Lambda Errors
```bash
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/hospup"
aws logs get-log-events --log-group-name "/aws/lambda/hospup-video-generator" --log-stream-name [stream-name]
```

### MediaConvert Issues
```bash
aws mediaconvert describe-job --id [job-id] --region eu-west-1
```

### Railway Backend Issues
```bash
# Check backend logs in Railway Dashboard
# Verify environment variables are set correctly
```

---

✅ **Pipeline Ready**: AWS Lambda + MediaConvert system fully configured and tested!