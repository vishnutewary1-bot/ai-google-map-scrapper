"""Cloud storage upload for S3 and Google Cloud Storage."""
import os
from typing import Optional
from dataclasses import dataclass
from datetime import timedelta
from loguru import logger

try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False
    boto3 = None

try:
    from google.cloud import storage as gcs
    HAS_GCS = True
except ImportError:
    HAS_GCS = False
    gcs = None


@dataclass
class UploadResult:
    """Result of cloud upload."""
    success: bool
    url: Optional[str] = None
    error: Optional[str] = None
    provider: Optional[str] = None
    file_size: Optional[int] = None


class CloudStorageManager:
    """Manage uploads to cloud storage services."""

    def __init__(self):
        self.s3_client = None
        self.gcs_client = None
        self.s3_configured = False
        self.gcs_configured = False

    def init_s3(
        self,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1"
    ) -> bool:
        """Initialize S3 client."""
        if not HAS_BOTO3:
            logger.error("boto3 is required for S3 uploads. Run: pip install boto3")
            return False

        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region
            )
            self.s3_configured = True
            logger.info(f"S3 client initialized for region {region}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize S3: {e}")
            return False

    def init_gcs(self, credentials_path: str) -> bool:
        """Initialize Google Cloud Storage client."""
        if not HAS_GCS:
            logger.error("google-cloud-storage is required. Run: pip install google-cloud-storage")
            return False

        try:
            self.gcs_client = gcs.Client.from_service_account_json(credentials_path)
            self.gcs_configured = True
            logger.info("Google Cloud Storage client initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize GCS: {e}")
            return False

    def _get_content_type(self, file_path: str) -> str:
        """Determine content type from file extension."""
        ext = os.path.splitext(file_path)[1].lower()
        content_types = {
            '.csv': 'text/csv',
            '.json': 'application/json',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel',
            '.pdf': 'application/pdf',
            '.txt': 'text/plain',
            '.zip': 'application/zip',
        }
        return content_types.get(ext, 'application/octet-stream')

    def upload_to_s3(
        self,
        file_path: str,
        bucket: str,
        key: Optional[str] = None,
        make_public: bool = False,
        expiration_hours: int = 24
    ) -> UploadResult:
        """Upload file to S3."""
        if not self.s3_client:
            return UploadResult(
                success=False,
                error="S3 client not initialized. Call init_s3() first.",
                provider="s3"
            )

        if not os.path.exists(file_path):
            return UploadResult(
                success=False,
                error=f"File not found: {file_path}",
                provider="s3"
            )

        try:
            if key is None:
                key = os.path.basename(file_path)

            file_size = os.path.getsize(file_path)
            content_type = self._get_content_type(file_path)

            extra_args = {'ContentType': content_type}
            if make_public:
                extra_args['ACL'] = 'public-read'

            self.s3_client.upload_file(
                file_path,
                bucket,
                key,
                ExtraArgs=extra_args
            )

            # Generate URL
            if make_public:
                url = f"https://{bucket}.s3.amazonaws.com/{key}"
            else:
                url = self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket, 'Key': key},
                    ExpiresIn=expiration_hours * 3600
                )

            logger.info(f"Uploaded to S3: s3://{bucket}/{key}")
            return UploadResult(
                success=True,
                url=url,
                provider="s3",
                file_size=file_size
            )

        except ClientError as e:
            error_msg = str(e)
            logger.error(f"S3 upload failed: {error_msg}")
            return UploadResult(success=False, error=error_msg, provider="s3")
        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
            return UploadResult(success=False, error=str(e), provider="s3")

    def upload_to_gcs(
        self,
        file_path: str,
        bucket: str,
        blob_name: Optional[str] = None,
        make_public: bool = False,
        expiration_hours: int = 24
    ) -> UploadResult:
        """Upload file to Google Cloud Storage."""
        if not self.gcs_client:
            return UploadResult(
                success=False,
                error="GCS client not initialized. Call init_gcs() first.",
                provider="gcs"
            )

        if not os.path.exists(file_path):
            return UploadResult(
                success=False,
                error=f"File not found: {file_path}",
                provider="gcs"
            )

        try:
            if blob_name is None:
                blob_name = os.path.basename(file_path)

            file_size = os.path.getsize(file_path)
            content_type = self._get_content_type(file_path)

            bucket_obj = self.gcs_client.bucket(bucket)
            blob = bucket_obj.blob(blob_name)
            blob.content_type = content_type

            # Upload
            blob.upload_from_filename(file_path)

            if make_public:
                blob.make_public()
                url = blob.public_url
            else:
                # Generate signed URL
                url = blob.generate_signed_url(
                    expiration=timedelta(hours=expiration_hours)
                )

            logger.info(f"Uploaded to GCS: gs://{bucket}/{blob_name}")
            return UploadResult(
                success=True,
                url=url,
                provider="gcs",
                file_size=file_size
            )

        except Exception as e:
            logger.error(f"GCS upload failed: {e}")
            return UploadResult(success=False, error=str(e), provider="gcs")

    def upload_file(
        self,
        file_path: str,
        provider: str = "s3",
        bucket: Optional[str] = None,
        key: Optional[str] = None,
        make_public: bool = False
    ) -> UploadResult:
        """Upload file to specified provider."""
        if provider.lower() == "s3":
            if not bucket:
                return UploadResult(success=False, error="S3 bucket name required")
            return self.upload_to_s3(file_path, bucket, key, make_public)
        elif provider.lower() in ("gcs", "google"):
            if not bucket:
                return UploadResult(success=False, error="GCS bucket name required")
            return self.upload_to_gcs(file_path, bucket, key, make_public)
        else:
            return UploadResult(
                success=False,
                error=f"Unknown provider: {provider}. Use 's3' or 'gcs'"
            )

    def list_s3_objects(self, bucket: str, prefix: str = "") -> list:
        """List objects in S3 bucket."""
        if not self.s3_client:
            return []

        try:
            response = self.s3_client.list_objects_v2(
                Bucket=bucket,
                Prefix=prefix,
                MaxKeys=100
            )
            return [obj['Key'] for obj in response.get('Contents', [])]
        except Exception as e:
            logger.error(f"Failed to list S3 objects: {e}")
            return []

    def list_gcs_objects(self, bucket: str, prefix: str = "") -> list:
        """List objects in GCS bucket."""
        if not self.gcs_client:
            return []

        try:
            bucket_obj = self.gcs_client.bucket(bucket)
            blobs = bucket_obj.list_blobs(prefix=prefix, max_results=100)
            return [blob.name for blob in blobs]
        except Exception as e:
            logger.error(f"Failed to list GCS objects: {e}")
            return []

    def delete_s3_object(self, bucket: str, key: str) -> bool:
        """Delete an object from S3."""
        if not self.s3_client:
            return False

        try:
            self.s3_client.delete_object(Bucket=bucket, Key=key)
            logger.info(f"Deleted from S3: s3://{bucket}/{key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete S3 object: {e}")
            return False

    def delete_gcs_object(self, bucket: str, blob_name: str) -> bool:
        """Delete an object from GCS."""
        if not self.gcs_client:
            return False

        try:
            bucket_obj = self.gcs_client.bucket(bucket)
            blob = bucket_obj.blob(blob_name)
            blob.delete()
            logger.info(f"Deleted from GCS: gs://{bucket}/{blob_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete GCS object: {e}")
            return False

    def get_status(self) -> dict:
        """Get cloud storage configuration status."""
        return {
            "s3": {
                "available": HAS_BOTO3,
                "configured": self.s3_configured
            },
            "gcs": {
                "available": HAS_GCS,
                "configured": self.gcs_configured
            }
        }


# Singleton
cloud_storage = CloudStorageManager()


def upload_to_cloud(
    file_path: str,
    provider: str,
    bucket: str,
    key: Optional[str] = None
) -> UploadResult:
    """Quick function to upload a file to cloud storage."""
    return cloud_storage.upload_file(file_path, provider, bucket, key)
