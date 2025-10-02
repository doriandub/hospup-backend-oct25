# 🚀 S3 Configuration Required for Upload Functionality

## ⚠️ Critical Issue Identified

The upload functionality is failing because **S3 environment variables are missing** in the Railway deployment.

## 📋 Required Railway Environment Variables

Add these variables in Railway Dashboard > hospup-backend > Variables:

```bash
# S3 Storage Configuration
S3_BUCKET=hospup-assets-production
S3_REGION=eu-west-1
S3_ACCESS_KEY_ID=your-aws-access-key-here
S3_SECRET_ACCESS_KEY=your-aws-secret-access-key-here
STORAGE_PUBLIC_BASE=https://hospup-assets-production.s3-eu-west-1.amazonaws.com
```

## 🛠️ Setup Steps

### 1. AWS S3 Setup
1. Create S3 bucket: `hospup-assets-production`
2. Configure bucket policy for public read access
3. Create IAM user with S3 permissions
4. Get Access Key ID and Secret Access Key

### 2. Railway Configuration
1. Login to Railway dashboard
2. Go to hospup-backend project
3. Click "Variables" tab  
4. Add all 5 environment variables above
5. Click "Deploy" to apply changes

### 3. Verify Configuration
Once configured, test with:
```bash
curl "https://web-production-b52f.up.railway.app/api/v1/diagnostic/s3-config"
```

## 🔍 Current Error Analysis

**From logs analysis:**
- ❌ `S3_BUCKET` is missing
- ❌ `S3_ACCESS_KEY_ID` is missing  
- ❌ `S3_SECRET_ACCESS_KEY` is missing
- ❌ `STORAGE_PUBLIC_BASE` is missing

**Frontend errors:**
- `405 Method Not Allowed` on `/api/v1/upload/` → Fixed ✅
- `401 Unauthorized` → Normal behavior without auth
- Upload functionality completely broken without S3 config

## 📁 Alternative: Test Bucket Configuration

For testing, you can use these sample values:
```bash
S3_BUCKET=hospup-test-uploads
S3_REGION=eu-west-1  
S3_ACCESS_KEY_ID=(your AWS key)
S3_SECRET_ACCESS_KEY=(your AWS secret)
STORAGE_PUBLIC_BASE=https://hospup-test-uploads.s3-eu-west-1.amazonaws.com
```

## ✅ Expected Behavior After Configuration

1. Upload endpoints will accept requests
2. Presigned URLs will be generated successfully  
3. Direct S3 uploads will work
4. Video records will be created in database
5. Assets page will show uploaded videos

## 🚨 Priority: HIGH

This is **blocking all upload functionality** and must be configured before the Assets system can be used.

---

## 🌐 S3 CORS Configuration

### Problem
Images/videos from S3 bucket may be blocked by CORS policy when accessed from the frontend:
```
Access to file at 'https://hospup-files.s3.eu-west-1.amazonaws.com/...'
from origin 'https://your-frontend.vercel.app' has been blocked by CORS policy
```

### Solution
Configure CORS policy on your S3 bucket:

```json
[
    {
        "AllowedHeaders": ["*"],
        "AllowedMethods": ["GET", "HEAD", "PUT", "POST"],
        "AllowedOrigins": [
            "https://*.vercel.app",
            "http://localhost:3000",
            "http://localhost:3001"
        ],
        "ExposeHeaders": ["ETag"],
        "MaxAgeSeconds": 3000
    }
]
```

### How to Apply CORS Configuration

1. Go to **AWS S3 Console**
2. Select your bucket (e.g., `hospup-files`)
3. Go to **Permissions** tab
4. Scroll down to **Cross-origin resource sharing (CORS)**
5. Click **Edit**
6. Paste the JSON configuration above
7. Click **Save changes**

### Testing CORS

After applying, test by:
1. Opening your frontend in browser
2. Uploading a video/image
3. Check browser console for CORS errors
4. Verify files load correctly

### Alternative: CloudFront CDN

For better performance and CORS handling, consider using CloudFront:
- Create CloudFront distribution pointing to S3 bucket
- Use CloudFront URL in `STORAGE_PUBLIC_BASE`
- CloudFront handles CORS automatically