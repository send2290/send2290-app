"""S3 service for file operations"""
import boto3
from botocore.exceptions import ClientError
from config import Config

def get_s3_client():
    """Get configured S3 client"""
    return boto3.client(
        's3',
        aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
        region_name=Config.AWS_DEFAULT_REGION
    )

def upload_to_s3(file_content, key, content_type=None, bucket=None):
    """Upload file content to S3"""
    try:
        s3 = get_s3_client()
        bucket_name = bucket or Config.get_bucket_name()
        
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type
        
        if isinstance(file_content, str):
            file_content = file_content.encode('utf-8')
        
        s3.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=file_content,
            **extra_args
        )
        return True, key
    except Exception as e:
        return False, str(e)

def download_from_s3(key, bucket=None):
    """Download file from S3"""
    try:
        s3 = get_s3_client()
        bucket_name = bucket or Config.get_bucket_name()
        
        response = s3.get_object(Bucket=bucket_name, Key=key)
        return True, response['Body'].read()
    except Exception as e:
        return False, str(e)

def delete_from_s3(key, bucket=None):
    """Delete file from S3"""
    try:
        s3 = get_s3_client()
        bucket_name = bucket or Config.get_bucket_name()
        
        s3.delete_object(Bucket=bucket_name, Key=key)
        return True, "File deleted successfully"
    except Exception as e:
        return False, str(e)

def generate_presigned_url(key, expiration=3600, bucket=None):
    """Generate presigned URL for S3 object"""
    try:
        s3 = get_s3_client()
        bucket_name = bucket or Config.get_bucket_name()
        
        url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': key},
            ExpiresIn=expiration
        )
        return True, url
    except Exception as e:
        return False, str(e)

def test_s3_connection(bucket=None):
    """Test S3 connectivity"""
    try:
        s3 = get_s3_client()
        bucket_name = bucket or Config.get_bucket_name()
        
        response = s3.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
        return True, "S3 connection successful"
    except Exception as e:
        return False, str(e)
