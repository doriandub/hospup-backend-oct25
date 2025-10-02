"""
S3 Storage Service - UNIQUE centralized implementation

Single point of truth for all S3 operations.
Replaces all duplicate S3 client code across the codebase.
"""

import boto3
import structlog
from typing import Optional, Dict, Any, BinaryIO, Union
from io import BytesIO
from datetime import datetime, timedelta
from botocore.exceptions import ClientError, NoCredentialsError

from ...core.config import settings
from ...shared.exceptions import StorageError, ConfigurationError

logger = structlog.get_logger(__name__)


class S3StorageService:
    """
    Centralized S3 service with all storage operations

    Features:
    - Connection pooling and reuse
    - Automatic retry with exponential backoff
    - Presigned URL generation
    - File metadata extraction
    - Error handling and logging
    """

    def __init__(self):
        self._client = None
        self._bucket_name = settings.S3_BUCKET
        self._region = settings.S3_REGION

        # Validate configuration
        if not all([settings.S3_ACCESS_KEY_ID, settings.S3_SECRET_ACCESS_KEY,
                   self._bucket_name, settings.S3_REGION]):
            raise ConfigurationError("S3 configuration is incomplete")

    @property
    def client(self):
        """Get S3 client with connection reuse"""
        if self._client is None:
            try:
                self._client = boto3.client(
                    's3',
                    aws_access_key_id=settings.S3_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
                    region_name=self._region,
                    endpoint_url=f"https://s3.{self._region}.amazonaws.com",
                    config=boto3.session.Config(
                        retries={'max_attempts': 3},
                        max_pool_connections=50
                    )
                )
                logger.info("S3 client initialized", region=self._region, bucket=self._bucket_name)
            except NoCredentialsError as e:
                logger.error("S3 credentials not found", error=str(e))
                raise ConfigurationError("S3 credentials not configured")
            except Exception as e:
                logger.error("Failed to initialize S3 client", error=str(e))
                raise StorageError(f"S3 initialization failed: {e}")

        return self._client

    def upload_file_sync(
        self,
        key: str,
        content: Union[bytes, BinaryIO],
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """Synchronous version for Celery tasks"""
        try:
            extra_args = {}

            if content_type:
                extra_args['ContentType'] = content_type

            if metadata:
                extra_args['Metadata'] = metadata

            # Convert bytes to BytesIO if needed
            if isinstance(content, bytes):
                content = BytesIO(content)

            # Upload file
            self.client.upload_fileobj(
                content,
                self._bucket_name,
                key,
                ExtraArgs=extra_args
            )

            # Generate public URL - same format as assets library
            public_url = f"https://s3.{self._region}.amazonaws.com/{self._bucket_name}/{key}"

            logger.info(
                "File uploaded to S3",
                file_key=key,
                content_type=content_type,
                url=public_url
            )

            return public_url
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(
                "S3 upload failed",
                file_key=key,
                error_code=error_code,
                error=str(e)
            )
            raise StorageError(f"Upload failed: {error_code}")
        except Exception as e:
            logger.error("Unexpected S3 upload error", file_key=key, error=str(e))
            raise StorageError(f"Upload failed: {e}")

    async def upload_file(
        self,
        key: str,
        content: Union[bytes, BinaryIO],
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        public: bool = True
    ) -> str:
        """Async wrapper for upload_file_sync"""
        return self.upload_file_sync(key, content, content_type, metadata)
        """
        Upload file to S3

        Args:
            file_content: File content as binary stream
            file_key: S3 object key (path)
            content_type: MIME type of file
            metadata: Custom metadata dict
            public: Make file publicly accessible

        Returns:
            Public URL of uploaded file

        Raises:
            StorageError: If upload fails
        """

    def download_file_sync(self, key: str) -> bytes:
        """Synchronous version for Celery tasks"""
        try:
            response = self.client.get_object(Bucket=self._bucket_name, Key=key)
            content = response['Body'].read()
            logger.info("File downloaded from S3", file_key=key, size=len(content))
            return content
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error("S3 download failed", file_key=key, error_code=error_code)
            raise StorageError(f"Download failed: {error_code}")
        except Exception as e:
            logger.error("Unexpected S3 download error", file_key=key, error=str(e))
            raise StorageError(f"Download failed: {e}")

    async def download_file(self, key: str) -> bytes:
        """Async wrapper for download_file_sync"""
        return self.download_file_sync(key)

    def delete_file_sync(self, key: str) -> bool:
        """Synchronous version for Celery tasks"""
        try:
            self.client.delete_object(Bucket=self._bucket_name, Key=key)
            logger.info("File deleted from S3", file_key=key)
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.warning("File not found for deletion", file_key=key)
                return True  # Consider missing file as successful deletion
            logger.error("S3 deletion failed", file_key=key, error_code=error_code)
            return False
        except Exception as e:
            logger.error("Unexpected S3 deletion error", file_key=key, error=str(e))
            return False

    async def delete_file(self, key: str) -> bool:
        """Async wrapper for delete_file_sync"""
        return self.delete_file_sync(key)
        """
        Delete file from S3

        Args:
            file_key: S3 object key to delete

        Returns:
            True if deleted successfully
        """
        try:
            self.client.delete_object(Bucket=self._bucket_name, Key=key)
            logger.info("File deleted from S3", file_key=key)
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.warning("File not found for deletion", file_key=key)
                return True  # Consider missing file as successful deletion
            logger.error("S3 deletion failed", file_key=key, error_code=error_code)
            return False
        except Exception as e:
            logger.error("Unexpected S3 deletion error", file_key=key, error=str(e))
            return False

    async def file_exists(self, file_key: str) -> bool:
        """Check if file exists in S3"""
        try:
            self.client.head_object(Bucket=self._bucket_name, Key=file_key)
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                return False
            logger.error("S3 file existence check failed", file_key=file_key, error_code=error_code)
            raise StorageError(f"File existence check failed: {error_code}")

    async def get_file_metadata(self, file_key: str) -> Dict[str, Any]:
        """Get file metadata from S3"""
        try:
            response = self.client.head_object(Bucket=self._bucket_name, Key=file_key)
            return {
                'size': response.get('ContentLength', 0),
                'content_type': response.get('ContentType', ''),
                'last_modified': response.get('LastModified'),
                'etag': response.get('ETag', '').strip('"'),
                'metadata': response.get('Metadata', {})
            }
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                raise StorageError(f"File not found: {file_key}")
            raise StorageError(f"Metadata retrieval failed: {error_code}")

    async def generate_presigned_url(
        self,
        file_key: str,
        expires_in: int = 3600,
        method: str = 'get_object'
    ) -> str:
        """
        Generate presigned URL for secure file access

        Args:
            file_key: S3 object key
            expires_in: URL expiration time in seconds (default 1 hour)
            method: S3 method ('get_object' for download, 'put_object' for upload)

        Returns:
            Presigned URL
        """
        try:
            url = self.client.generate_presigned_url(
                method,
                Params={'Bucket': self._bucket_name, 'Key': file_key},
                ExpiresIn=expires_in
            )

            logger.info(
                "Presigned URL generated",
                file_key=file_key,
                method=method,
                expires_in=expires_in
            )

            return url
        except ClientError as e:
            logger.error("Presigned URL generation failed", file_key=file_key, error=str(e))
            raise StorageError(f"Presigned URL generation failed: {e}")

    async def generate_presigned_post(
        self,
        file_key: str,
        expires_in: int = 3600,
        fields: Optional[Dict[str, str]] = None,
        conditions: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Generate presigned POST for direct browser uploads

        Args:
            file_key: S3 object key
            expires_in: URL expiration time in seconds
            fields: Additional fields for the POST
            conditions: Upload conditions/restrictions

        Returns:
            Dict with 'url' and 'fields' for POST form
        """
        try:
            presigned_post = self.client.generate_presigned_post(
                Bucket=self._bucket_name,
                Key=file_key,
                Fields=fields or {},
                Conditions=conditions or [],
                ExpiresIn=expires_in
            )

            logger.info(
                "Presigned POST generated",
                file_key=file_key,
                expires_in=expires_in
            )

            return presigned_post
        except ClientError as e:
            logger.error("Presigned POST generation failed", file_key=file_key, error=str(e))
            raise StorageError(f"Presigned POST generation failed: {e}")

    async def copy_file(self, source_key: str, dest_key: str) -> bool:
        """Copy file within S3 bucket"""
        try:
            copy_source = {'Bucket': self._bucket_name, 'Key': source_key}
            self.client.copy_object(
                CopySource=copy_source,
                Bucket=self._bucket_name,
                Key=dest_key
            )
            logger.info("File copied in S3", source=source_key, dest=dest_key)
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error("S3 copy failed", source=source_key, dest=dest_key, error_code=error_code)
            return False

    async def list_files(self, prefix: str = "", max_keys: int = 1000) -> list:
        """List files in bucket with optional prefix filter"""
        try:
            response = self.client.list_objects_v2(
                Bucket=self._bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )

            files = []
            for obj in response.get('Contents', []):
                files.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'],
                    'etag': obj['ETag'].strip('"')
                })

            logger.info("S3 files listed", prefix=prefix, count=len(files))
            return files
        except ClientError as e:
            logger.error("S3 list files failed", prefix=prefix, error=str(e))
            raise StorageError(f"List files failed: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """Health check for S3 service"""
        try:
            # Test basic connectivity
            self.client.head_bucket(Bucket=self._bucket_name)

            # Test write/read/delete
            test_key = f"health-check/{datetime.utcnow().isoformat()}"
            test_content = b"health check"

            self.client.upload_fileobj(
                BytesIO(test_content),
                self._bucket_name,
                test_key
            )

            # Cleanup test file
            self.client.delete_object(Bucket=self._bucket_name, Key=test_key)

            return {
                "healthy": True,
                "bucket": self._bucket_name,
                "region": self._region
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "bucket": self._bucket_name,
                "region": self._region
            }


# Global singleton instance
_s3_service = None

def get_s3_service() -> S3StorageService:
    """Get singleton S3 service instance"""
    global _s3_service
    if _s3_service is None:
        _s3_service = S3StorageService()
    return _s3_service