"""S3-compatible artifact store (MinIO) for durable, addressable outputs."""

from __future__ import annotations

import time
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError

from .config import settings
from .log import get_logger

log = get_logger()

# ---------------------------------------------------------------------------
# Cached Boto3 S3 client for connection pooling
# ---------------------------------------------------------------------------

_s3_client_cached = None


@dataclass(frozen=True)
class ArtifactResult:
    key: str
    size: int
    etag: str
    timestamp: int  # epoch ms


class ArtifactError(RuntimeError):
    def __init__(self, operation: str, key: str, reason: str):
        self.operation = operation
        self.key = key
        self.reason = reason
        super().__init__(f"artifact {operation} failed for '{key}': {reason}")


def _s3_client():
    """Get cached boto3 S3 client with connection pooling."""
    global _s3_client_cached
    if _s3_client_cached is None:
        _s3_client_cached = boto3.client(
            "s3",
            endpoint_url=settings.artifact.endpoint,
            aws_access_key_id=settings.artifact.access_key,
            aws_secret_access_key=settings.artifact.secret_key,
            region_name=settings.artifact.region,
        )
    return _s3_client_cached


def ensure_bucket() -> None:
    """Create the configured bucket if it doesn't already exist."""
    client = _s3_client()
    try:
        client.head_bucket(Bucket=settings.artifact.bucket)
    except ClientError as exc:
        code = exc.response["Error"].get("Code", "")
        if code in ("404", "NoSuchBucket"):
            try:
                client.create_bucket(Bucket=settings.artifact.bucket)
            except ClientError as create_exc:
                raise ArtifactError("ensure_bucket", settings.artifact.bucket, str(create_exc))
        else:
            raise ArtifactError("ensure_bucket", settings.artifact.bucket, str(exc))


def upload_artifact(key: str, data: bytes, metadata: dict | None = None) -> ArtifactResult:
    """Upload bytes to the artifact store with optional metadata tags."""
    try:
        ensure_bucket()
        client = _s3_client()
        now_ms = int(time.time() * 1000)
        tags = metadata or {}
        tags.setdefault("timestamp", str(now_ms))

        resp = client.put_object(
            Bucket=settings.artifact.bucket,
            Key=key,
            Body=data,
            Metadata={k: str(v) for k, v in tags.items()},
        )
        return ArtifactResult(
            key=key,
            size=len(data),
            etag=resp.get("ETag", "").strip('"'),
            timestamp=now_ms,
        )
    except ArtifactError:
        raise
    except ClientError as exc:
        raise ArtifactError("upload", key, str(exc))


def download_artifact(key: str) -> tuple[bytes, dict]:
    """Download an artifact. Returns (body_bytes, metadata_dict)."""
    try:
        client = _s3_client()
        resp = client.get_object(Bucket=settings.artifact.bucket, Key=key)
        body = resp["Body"].read()
        metadata = resp.get("Metadata", {})
        return body, metadata
    except ClientError as exc:
        code = exc.response["Error"].get("Code", "")
        if code == "NoSuchKey":
            raise ArtifactError("download", key, "not found")
        raise ArtifactError("download", key, str(exc))


def list_artifacts(prefix: str = "") -> list[ArtifactResult]:
    """List artifacts, optionally filtered by key prefix."""
    try:
        client = _s3_client()
        kwargs: dict = {"Bucket": settings.artifact.bucket}
        if prefix:
            kwargs["Prefix"] = prefix

        resp = client.list_objects_v2(**kwargs)
        results = []
        for obj in resp.get("Contents", []):
            results.append(
                ArtifactResult(
                    key=obj["Key"],
                    size=obj.get("Size", 0),
                    etag=obj.get("ETag", "").strip('"'),
                    timestamp=int(obj.get("LastModified", time.time()).timestamp() * 1000)
                    if hasattr(obj.get("LastModified"), "timestamp")
                    else 0,
                )
            )
        return results
    except ClientError as exc:
        raise ArtifactError("list", prefix, str(exc))


def delete_artifact(key: str) -> None:
    """Delete an artifact by key."""
    try:
        client = _s3_client()
        client.delete_object(Bucket=settings.artifact.bucket, Key=key)
    except ClientError as exc:
        raise ArtifactError("delete", key, str(exc))


def health_check() -> bool:
    """Check if the artifact store is reachable. Returns True/False."""
    try:
        ensure_bucket()
        return True
    except Exception as exc:
        log.debug("artifacts.health_check_failed", metadata={"reason": str(exc)})
        return False
