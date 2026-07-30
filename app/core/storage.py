from dataclasses import dataclass
from functools import lru_cache

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from app.core.config import get_settings

settings = get_settings()


@lru_cache
def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=BotoConfig(signature_version="s3v4"),
        region_name="auto",
    )


@dataclass
class ObjectMetadata:
    content_length: int
    content_type: str | None


def generate_presigned_upload_url(
    object_key: str, *, content_type: str, expires_in: int = 300
) -> str:
    return get_r2_client().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.r2_bucket_name,
            "Key": object_key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
    )


def head_object(object_key: str) -> ObjectMetadata | None:
    try:
        response = get_r2_client().head_object(Bucket=settings.r2_bucket_name, Key=object_key)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
            return None
        raise
    return ObjectMetadata(
        content_length=response["ContentLength"],
        content_type=response.get("ContentType"),
    )


def delete_object(object_key: str) -> None:
    get_r2_client().delete_object(Bucket=settings.r2_bucket_name, Key=object_key)


def build_public_url(object_key: str) -> str:
    return f"{settings.r2_public_base_url.rstrip('/')}/{object_key}"
