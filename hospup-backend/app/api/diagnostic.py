"""
S3 Configuration Diagnostic Endpoint
"""
from fastapi import APIRouter, HTTPException
from app.core.config import settings
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()

@router.get("/s3-config")
async def check_s3_configuration():
    """Check if S3 configuration is properly set up"""
    
    config_status = {
        "s3_configuration": {
            "status": "healthy",
            "issues": []
        }
    }
    
    # Check required S3 environment variables
    required_vars = {
        "S3_BUCKET": getattr(settings, 'S3_BUCKET', None),
        "S3_REGION": getattr(settings, 'S3_REGION', None), 
        "S3_ACCESS_KEY_ID": getattr(settings, 'S3_ACCESS_KEY_ID', None),
        "S3_SECRET_ACCESS_KEY": getattr(settings, 'S3_SECRET_ACCESS_KEY', None),
        "STORAGE_PUBLIC_BASE": getattr(settings, 'STORAGE_PUBLIC_BASE', None)
    }
    
    missing_vars = []
    configured_vars = {}
    
    for var_name, var_value in required_vars.items():
        if not var_value:
            missing_vars.append(var_name)
        else:
            # Show first 3 and last 3 chars for security
            if var_name in ["S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY"]:
                configured_vars[var_name] = f"{var_value[:3]}...{var_value[-3:]}" if len(var_value) > 6 else "***"
            else:
                configured_vars[var_name] = var_value
    
    if missing_vars:
        config_status["s3_configuration"]["status"] = "missing_variables"
        config_status["s3_configuration"]["issues"] = missing_vars
        config_status["s3_configuration"]["missing_count"] = len(missing_vars)
    
    config_status["s3_configuration"]["configured_variables"] = configured_vars
    config_status["s3_configuration"]["total_required"] = len(required_vars)
    config_status["s3_configuration"]["configured_count"] = len(configured_vars)
    
    # Add instructions if variables are missing
    if missing_vars:
        config_status["instructions"] = {
            "platform": "Railway",
            "required_variables": {
                "S3_BUCKET": "Your S3 bucket name (e.g., hospup-assets)",
                "S3_REGION": "AWS region (e.g., eu-west-1)", 
                "S3_ACCESS_KEY_ID": "AWS Access Key ID",
                "S3_SECRET_ACCESS_KEY": "AWS Secret Access Key",
                "STORAGE_PUBLIC_BASE": "Public CDN URL (e.g., https://cdn.hospup.app)"
            },
            "setup_steps": [
                "1. Login to Railway dashboard",
                "2. Go to your hospup-backend project",
                "3. Click on 'Variables' tab",
                "4. Add the missing environment variables above",
                "5. Redeploy the service"
            ]
        }
    
    return config_status

@router.post("/test-s3-connection")
async def test_s3_connection():
    """Test actual S3 connection and bucket access"""
    
    # Check if variables are available
    if not all([
        getattr(settings, 'S3_BUCKET', None),
        getattr(settings, 'S3_ACCESS_KEY_ID', None),
        getattr(settings, 'S3_SECRET_ACCESS_KEY', None)
    ]):
        raise HTTPException(
            status_code=503,
            detail="S3 configuration incomplete. Use /diagnostic/s3-config to see missing variables."
        )
    
    try:
        # Import here to avoid startup errors if boto3 isn't configured
        import boto3
        from botocore.exceptions import ClientError
        
        # Create S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION,
            endpoint_url=f"https://s3.{settings.S3_REGION}.amazonaws.com"
        )
        
        # Test bucket access
        s3_client.head_bucket(Bucket=settings.S3_BUCKET)
        
        # Test basic operations
        test_key = "test/connection-test.txt"
        test_content = "S3 connection test successful"
        
        # Upload test object
        s3_client.put_object(
            Bucket=settings.S3_BUCKET,
            Key=test_key,
            Body=test_content,
            ContentType="text/plain"
        )
        
        # Delete test object
        s3_client.delete_object(
            Bucket=settings.S3_BUCKET,
            Key=test_key
        )
        
        return {
            "status": "success",
            "message": "S3 connection and bucket access verified",
            "bucket": settings.S3_BUCKET,
            "region": settings.S3_REGION,
            "operations_tested": ["head_bucket", "put_object", "delete_object"]
        }
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        
        return {
            "status": "error",
            "error_type": "aws_client_error", 
            "error_code": error_code,
            "message": f"S3 Error: {error_message}",
            "suggestion": get_s3_error_suggestion(error_code)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error_type": "unexpected_error",
            "message": str(e)[:200]
        }

def get_s3_error_suggestion(error_code: str) -> str:
    """Get suggestion based on S3 error code"""
    suggestions = {
        "NoSuchBucket": "Bucket does not exist. Check S3_BUCKET name.",
        "InvalidAccessKeyId": "Invalid Access Key ID. Check S3_ACCESS_KEY_ID.",
        "SignatureDoesNotMatch": "Invalid Secret Key. Check S3_SECRET_ACCESS_KEY.",
        "AccessDenied": "Access denied. Check IAM permissions for the bucket.",
        "TokenRefreshRequired": "Token expired. Regenerate AWS credentials."
    }
    return suggestions.get(error_code, "Check AWS credentials and bucket configuration.")