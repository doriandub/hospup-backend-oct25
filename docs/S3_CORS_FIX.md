# S3 CORS Configuration Fix

## Problem
Images from S3 bucket `hospup-files` are blocked by CORS policy:
```
Access to image at 'https://hospup-files.s3.eu-west-1.amazonaws.com/...'
from origin 'https://hospup-frontend-2-kappa.vercel.app' has been blocked by CORS policy
```

## Solution
Configure CORS policy on S3 bucket `hospup-files`:

```json
[
    {
        "AllowedHeaders": ["*"],
        "AllowedMethods": ["GET", "HEAD"],
        "AllowedOrigins": [
            "https://hospup-frontend-2-kappa.vercel.app",
            "https://*.vercel.app",
            "http://localhost:3000",
            "http://localhost:3001"
        ],
        "ExposeHeaders": [],
        "MaxAgeSeconds": 3000
    }
]
```

## How to Apply
1. Go to AWS S3 Console
2. Select bucket `hospup-files`
3. Go to Permissions tab
4. Scroll down to Cross-origin resource sharing (CORS)
5. Edit and paste the JSON above
6. Save changes

## Alternative: Use CloudFront
If CORS doesn't work, serve images through CloudFront distribution instead of direct S3 URLs.