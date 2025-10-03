"""
Configuration Diagnostic Endpoints
"""
from fastapi import APIRouter, HTTPException
from app.core.config import settings
import structlog
import os

logger = structlog.get_logger(__name__)
router = APIRouter()

@router.get("/db-config")
async def check_database_configuration():
    """Check if database configuration is properly set up"""

    config_status = {
        "database_configuration": {
            "status": "healthy",
            "issues": []
        }
    }

    # Check database environment variables
    db_vars = {
        "DATABASE_URL": os.getenv('DATABASE_URL', None),
        "DB_USERNAME": os.getenv('DB_USERNAME', None),
        "DB_PASSWORD": os.getenv('DB_PASSWORD', None),
        "DB_HOSTNAME": os.getenv('DB_HOSTNAME', None),
        "DB_PORT": os.getenv('DB_PORT', None),
        "DB_NAME": os.getenv('DB_NAME', None)
    }

    missing_vars = []
    configured_vars = {}

    for var_name, var_value in db_vars.items():
        if not var_value:
            missing_vars.append(var_name)
        else:
            # Mask sensitive values
            if var_name in ["DB_PASSWORD", "DATABASE_URL"]:
                if len(var_value) > 10:
                    configured_vars[var_name] = f"{var_value[:3]}...{var_value[-3:]}"
                else:
                    configured_vars[var_name] = "***"
            else:
                configured_vars[var_name] = var_value

    # Check if we're using DATABASE_URL or individual credentials
    if db_vars["DATABASE_URL"]:
        config_status["database_configuration"]["mode"] = "DATABASE_URL"
        config_status["database_configuration"]["note"] = "Using full DATABASE_URL connection string"
    elif all([db_vars["DB_USERNAME"], db_vars["DB_PASSWORD"], db_vars["DB_HOSTNAME"]]):
        config_status["database_configuration"]["mode"] = "individual_credentials"
        config_status["database_configuration"]["note"] = "Using individual DB credentials (DB_USERNAME, DB_PASSWORD, DB_HOSTNAME)"
    else:
        config_status["database_configuration"]["status"] = "missing_variables"
        config_status["database_configuration"]["issues"] = missing_vars or ["No complete database configuration found"]

    config_status["database_configuration"]["configured_variables"] = configured_vars
    config_status["database_configuration"]["missing_variables"] = missing_vars

    # Add setup instructions if needed
    if missing_vars and not db_vars["DATABASE_URL"]:
        config_status["instructions"] = {
            "platform": "Railway",
            "required_variables_option_1": {
                "DATABASE_URL": "Full PostgreSQL connection string (postgresql+asyncpg://user:pass@host:port/dbname)"
            },
            "required_variables_option_2": {
                "DB_USERNAME": "Database username",
                "DB_PASSWORD": "Database password",
                "DB_HOSTNAME": "Database hostname",
                "DB_PORT": "Database port (default: 6543)",
                "DB_NAME": "Database name (default: postgres)"
            },
            "setup_steps": [
                "1. Login to Railway dashboard",
                "2. Go to your hospup-backend project",
                "3. Click on 'Variables' tab",
                "4. Add EITHER DATABASE_URL OR individual DB credentials",
                "5. Redeploy the service"
            ]
        }

    return config_status

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
        s3_client.head_bucket(Bucket=settings.bucket_name)
        
        # Test basic operations
        test_key = "test/connection-test.txt"
        test_content = "S3 connection test successful"
        
        # Upload test object
        s3_client.put_object(
            Bucket=settings.bucket_name,
            Key=test_key,
            Body=test_content,
            ContentType="text/plain"
        )
        
        # Delete test object
        s3_client.delete_object(
            Bucket=settings.bucket_name,
            Key=test_key
        )
        
        return {
            "status": "success",
            "message": "S3 connection and bucket access verified",
            "bucket": settings.bucket_name,
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

@router.get("/aws-lambda-config")
async def check_aws_lambda_configuration():
    """Check if AWS Lambda configuration is properly set up"""
    import os

    config_status = {
        "lambda_configuration": {
            "status": "healthy",
            "issues": []
        }
    }

    # Check required AWS Lambda environment variables
    required_vars = {
        "S3_ACCESS_KEY_ID": os.getenv('S3_ACCESS_KEY_ID'),
        "S3_SECRET_ACCESS_KEY": os.getenv('S3_SECRET_ACCESS_KEY'),
        "S3_REGION": os.getenv('S3_REGION', 'eu-west-1'),
        "AWS_LAMBDA_FUNCTION_NAME": os.getenv('AWS_LAMBDA_FUNCTION_NAME', 'hospup-video-generator')
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
        config_status["lambda_configuration"]["status"] = "missing_variables"
        config_status["lambda_configuration"]["issues"] = missing_vars
        config_status["lambda_configuration"]["missing_count"] = len(missing_vars)

    config_status["lambda_configuration"]["configured_variables"] = configured_vars
    config_status["lambda_configuration"]["total_required"] = len(required_vars)
    config_status["lambda_configuration"]["configured_count"] = len(configured_vars)

    return config_status

@router.post("/test-lambda-function")
async def test_lambda_function():
    """Test AWS Lambda function invocation"""
    import os
    import boto3
    import json
    from botocore.exceptions import ClientError

    # Check if variables are available
    aws_access_key_id = os.getenv('S3_ACCESS_KEY_ID')
    aws_secret_access_key = os.getenv('S3_SECRET_ACCESS_KEY')
    aws_region = os.getenv('S3_REGION', 'eu-west-1')
    lambda_function_name = os.getenv('AWS_LAMBDA_FUNCTION_NAME', 'hospup-video-generator')

    if not aws_access_key_id or not aws_secret_access_key:
        raise HTTPException(
            status_code=503,
            detail="AWS Lambda credentials not configured. Check S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY."
        )

    try:
        # Create Lambda client
        lambda_client = boto3.client(
            'lambda',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region
        )

        # Test payload
        test_payload = {
            "body": json.dumps({
                "property_id": "test",
                "video_id": "test-video-123",
                "job_id": "test-job-456",
                "template_id": "test-template",
                "segments": [
                    {
                        "id": "segment_1",
                        "video_url": "https://test.com/video.mp4",
                        "start_time": 0,
                        "end_time": 3,
                        "duration": 3,
                        "order": 1
                    }
                ],
                "text_overlays": [],
                "total_duration": 3,
                "webhook_url": "https://web-production-b52f.up.railway.app/api/v1/videos/ffmpeg-callback"
            }),
            "headers": {
                "Content-Type": "application/json"
            }
        }

        # Check if function exists first
        try:
            lambda_client.get_function(FunctionName=lambda_function_name)
            function_exists = True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                function_exists = False
            else:
                raise e

        if not function_exists:
            return {
                "status": "error",
                "error_type": "function_not_found",
                "message": f"Lambda function '{lambda_function_name}' not found",
                "function_name": lambda_function_name,
                "region": aws_region,
                "suggestion": "Check AWS_LAMBDA_FUNCTION_NAME environment variable and ensure function is deployed"
            }

        # Try to invoke function (dry run)
        response = lambda_client.invoke(
            FunctionName=lambda_function_name,
            InvocationType='RequestResponse',  # Sync for testing
            Payload=json.dumps(test_payload)
        )

        # Parse response
        response_payload = json.loads(response['Payload'].read())

        return {
            "status": "success",
            "message": "AWS Lambda function accessible and invoked successfully",
            "function_name": lambda_function_name,
            "region": aws_region,
            "status_code": response['StatusCode'],
            "response_payload": response_payload
        }

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']

        return {
            "status": "error",
            "error_type": "aws_client_error",
            "error_code": error_code,
            "message": f"Lambda Error: {error_message}",
            "function_name": lambda_function_name,
            "region": aws_region
        }

    except Exception as e:
        return {
            "status": "error",
            "error_type": "unexpected_error",
            "message": str(e)[:200],
            "function_name": lambda_function_name
        }

@router.post("/simulate-video-callback")
async def simulate_video_callback():
    """Simulate a successful video generation callback"""
    import uuid
    import httpx

    # Create test callback data
    test_video_id = "test-video-" + str(uuid.uuid4())[:8]
    test_job_id = "test-job-" + str(uuid.uuid4())[:8]

    callback_data = {
        "video_id": test_video_id,
        "job_id": test_job_id,
        "status": "COMPLETE",
        "file_url": "https://s3.eu-west-1.amazonaws.com/hospup-files/test-video.mp4",
        "thumbnail_url": "https://s3.eu-west-1.amazonaws.com/hospup-files/test-thumbnail.jpg",
        "duration": 30,
        "processing_time": "45s",
        "segments_processed": 3
    }

    webhook_url = "https://web-production-b52f.up.railway.app/api/v1/videos/ffmpeg-callback"

    try:
        # First create a test video entry in database to callback to
        from app.core.database import get_db
        from app.models.video import Video
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        # Get database session
        async for db in get_db():
            # Create test video
            test_video = Video(
                id=test_video_id,
                title="Test Video Generation",
                description=f"Test video for callback verification [JOB:{test_job_id}]",
                property_id=1,  # Assuming property 1 exists
                user_id="test-user",
                status='processing',
                duration=None,
                file_url=None,
                thumbnail_url=None
            )

            db.add(test_video)
            await db.commit()

            # Now send callback
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook_url,
                    json=callback_data,
                    headers={"Content-Type": "application/json"}
                )

                return {
                    "status": "success",
                    "message": "Test callback sent successfully",
                    "test_video_id": test_video_id,
                    "test_job_id": test_job_id,
                    "callback_data": callback_data,
                    "webhook_response": {
                        "status_code": response.status_code,
                        "response": response.json() if response.status_code == 200 else response.text[:200]
                    }
                }

    except Exception as e:
        return {
            "status": "error",
            "error_type": "callback_simulation_failed",
            "message": str(e)[:300]
        }

@router.post("/test-complete-lambda-payload")
async def test_complete_lambda_payload():
    """Test AWS Lambda with a complete realistic payload"""
    import os
    import boto3
    import json
    from botocore.exceptions import ClientError

    # Check if variables are available
    aws_access_key_id = os.getenv('S3_ACCESS_KEY_ID')
    aws_secret_access_key = os.getenv('S3_SECRET_ACCESS_KEY')
    aws_region = os.getenv('S3_REGION', 'eu-west-1')
    lambda_function_name = os.getenv('AWS_LAMBDA_FUNCTION_NAME', 'hospup-video-generator')

    if not aws_access_key_id or not aws_secret_access_key:
        raise HTTPException(
            status_code=503,
            detail="AWS Lambda credentials not configured."
        )

    try:
        # Create Lambda client
        lambda_client = boto3.client(
            'lambda',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region
        )

        # Real custom script from production compose interface
        custom_script = {
            "clips": [
                {
                    "order": 1,
                    "duration": 2.67,
                    "video_url": "https://s3.eu-west-1.amazonaws.com/hospup-files/videos/3/2/03c08f37-48ca-435d-8386-b4387c1e5ce6.MOV",
                    "video_id": "03c08f37-48ca-435d-8386-b4387c1e5ce6",
                    "start_time": 0,
                    "end_time": 2.67
                },
                {
                    "order": 2,
                    "duration": 1.2,
                    "video_url": "https://s3.eu-west-1.amazonaws.com/hospup-files/videos/3/2/632bd401-f3ad-47c1-a989-2072dcf9b63f.MOV",
                    "video_id": "632bd401-f3ad-47c1-a989-2072dcf9b63f",
                    "start_time": 2.67,
                    "end_time": 3.87
                },
                {
                    "order": 3,
                    "duration": 1.3,
                    "video_url": "https://s3.eu-west-1.amazonaws.com/hospup-files/videos/3/2/ea129303-0e67-46a2-9b09-e73ea5e8064c.mp4",
                    "video_id": "ea129303-0e67-46a2-9b09-e73ea5e8064c",
                    "start_time": 3.87,
                    "end_time": 5.17
                },
                {
                    "order": 4,
                    "duration": 1.3,
                    "video_url": "https://s3.eu-west-1.amazonaws.com/hospup-files/videos/3/2/9564f7d3-31cd-4891-9f5e-beb91ba52656.MOV",
                    "video_id": "9564f7d3-31cd-4891-9f5e-beb91ba52656",
                    "start_time": 5.17,
                    "end_time": 6.47
                },
                {
                    "order": 5,
                    "duration": 1.37,
                    "video_url": "https://s3.eu-west-1.amazonaws.com/hospup-files/videos/3/2/466d0778-861f-435f-b1ed-e3314de50680.MP4",
                    "video_id": "466d0778-861f-435f-b1ed-e3314de50680",
                    "start_time": 6.47,
                    "end_time": 7.84
                },
                {
                    "order": 6,
                    "duration": 1.13,
                    "video_url": "https://s3.eu-west-1.amazonaws.com/hospup-files/videos/3/2/5ff8bb09-2ff5-4cc4-83e7-c3fd93f9f6e4.MOV",
                    "video_id": "5ff8bb09-2ff5-4cc4-83e7-c3fd93f9f6e4",
                    "start_time": 7.84,
                    "end_time": 8.97
                },
                {
                    "order": 7,
                    "duration": 0.93,
                    "video_url": "https://s3.eu-west-1.amazonaws.com/hospup-files/videos/3/2/8f080426-8662-4558-93eb-d6b37b921b86.mov",
                    "video_id": "8f080426-8662-4558-93eb-d6b37b921b86",
                    "start_time": 8.97,
                    "end_time": 9.9
                }
            ],
            "texts": [
                {
                    "content": "Nouveau texte",
                    "start_time": 0,
                    "end_time": 5.18,
                    "position": {
                        "x": 540,
                        "y": 960
                    },
                    "style": {
                        "color": "#ffffff",
                        "font_size": 24
                    }
                }
            ],
            "total_duration": 9.9
        }

        # Complete payload exactly like in the backend
        complete_payload = {
            "property_id": "1",
            "video_id": "test-video-complete-123",
            "job_id": "test-job-complete-456",
            "template_id": "test-template",
            "segments": custom_script["clips"],  # Use clips from custom_script
            "text_overlays": custom_script["texts"],
            "custom_script": custom_script,
            "total_duration": custom_script["total_duration"],
            "webhook_url": "https://web-production-b52f.up.railway.app/api/v1/videos/ffmpeg-callback"
        }

        # Test payload wrapped in API Gateway format
        test_payload = {
            "body": json.dumps(complete_payload),
            "headers": {
                "Content-Type": "application/json"
            }
        }

        # Try to invoke function
        response = lambda_client.invoke(
            FunctionName=lambda_function_name,
            InvocationType='RequestResponse',  # Sync for testing
            Payload=json.dumps(test_payload)
        )

        # Parse response
        response_payload = json.loads(response['Payload'].read())

        return {
            "status": "success",
            "message": "AWS Lambda test with complete payload successful",
            "function_name": lambda_function_name,
            "region": aws_region,
            "status_code": response['StatusCode'],
            "payload_sent": complete_payload,
            "custom_script_included": "custom_script" in complete_payload,
            "clips_count": len(custom_script.get("clips", [])),
            "texts_count": len(custom_script.get("texts", [])),
            "response_payload": response_payload
        }

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']

        return {
            "status": "error",
            "error_type": "aws_client_error",
            "error_code": error_code,
            "message": f"Lambda Error: {error_message}",
            "function_name": lambda_function_name,
            "region": aws_region
        }

    except Exception as e:
        return {
            "status": "error",
            "error_type": "unexpected_error",
            "message": str(e)[:200],
            "function_name": lambda_function_name
        }