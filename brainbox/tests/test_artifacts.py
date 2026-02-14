"""Tests for artifact store (MinIO/S3) integration."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from brainbox.artifacts import (
    ArtifactError,
    ArtifactResult,
    delete_artifact,
    download_artifact,
    ensure_bucket,
    health_check,
    list_artifacts,
    upload_artifact,
)
from brainbox.config import ArtifactSettings, settings


# ---------------------------------------------------------------------------
# ArtifactResult
# ---------------------------------------------------------------------------


class TestArtifactResult:
    def test_fields(self):
        r = ArtifactResult(key="test/file.txt", size=42, etag="abc123", timestamp=1700000000000)
        assert r.key == "test/file.txt"
        assert r.size == 42
        assert r.etag == "abc123"
        assert r.timestamp == 1700000000000

    def test_frozen(self):
        r = ArtifactResult(key="k", size=0, etag="", timestamp=0)
        with pytest.raises(AttributeError):
            r.key = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ArtifactError
# ---------------------------------------------------------------------------


class TestArtifactError:
    def test_message_format(self):
        err = ArtifactError("upload", "test/file.txt", "connection refused")
        assert "upload" in str(err)
        assert "test/file.txt" in str(err)
        assert "connection refused" in str(err)

    def test_fields(self):
        err = ArtifactError("download", "key", "reason")
        assert err.operation == "download"
        assert err.key == "key"
        assert err.reason == "reason"

    def test_is_runtime_error(self):
        assert isinstance(ArtifactError("op", "k", "r"), RuntimeError)


# ---------------------------------------------------------------------------
# ArtifactSettings
# ---------------------------------------------------------------------------


class TestArtifactSettings:
    def test_defaults(self):
        s = ArtifactSettings()
        assert s.mode == "warn"
        assert s.endpoint == "http://localhost:9000"
        assert s.access_key == ""
        assert s.secret_key == ""
        assert s.bucket == "artifacts"
        assert s.region == "us-east-1"

    def test_explicit_values(self):
        s = ArtifactSettings(
            mode="enforce",
            endpoint="http://minio.example.com:9000",
            access_key="mykey",
            secret_key="mysecret",
            bucket="custom-bucket",
            region="eu-west-1",
        )
        assert s.mode == "enforce"
        assert s.endpoint == "http://minio.example.com:9000"
        assert s.access_key == "mykey"
        assert s.secret_key == "mysecret"
        assert s.bucket == "custom-bucket"
        assert s.region == "eu-west-1"

    def test_invalid_mode_rejected(self):
        with pytest.raises(Exception):
            ArtifactSettings(mode="invalid")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ensure_bucket
# ---------------------------------------------------------------------------


def _client_error(code: str, message: str = "error") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": message}}, "op")


class TestEnsureBucket:
    @patch("brainbox.artifacts._s3_client")
    def test_bucket_exists(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        # head_bucket succeeds → no create call
        ensure_bucket()
        mock_client.head_bucket.assert_called_once()
        mock_client.create_bucket.assert_not_called()

    @patch("brainbox.artifacts._s3_client")
    def test_bucket_missing_creates(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.head_bucket.side_effect = _client_error("404")
        ensure_bucket()
        mock_client.create_bucket.assert_called_once()

    @patch("brainbox.artifacts._s3_client")
    def test_bucket_missing_nosuchbucket_creates(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.head_bucket.side_effect = _client_error("NoSuchBucket")
        ensure_bucket()
        mock_client.create_bucket.assert_called_once()

    @patch("brainbox.artifacts._s3_client")
    def test_head_bucket_other_error_raises(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.head_bucket.side_effect = _client_error("403", "Forbidden")
        with pytest.raises(ArtifactError, match="ensure_bucket"):
            ensure_bucket()

    @patch("brainbox.artifacts._s3_client")
    def test_create_bucket_failure_raises(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.head_bucket.side_effect = _client_error("404")
        mock_client.create_bucket.side_effect = _client_error("500", "Internal")
        with pytest.raises(ArtifactError, match="ensure_bucket"):
            ensure_bucket()


# ---------------------------------------------------------------------------
# upload_artifact
# ---------------------------------------------------------------------------


class TestUploadArtifact:
    @patch("brainbox.artifacts.ensure_bucket")
    @patch("brainbox.artifacts._s3_client")
    def test_success(self, mock_client_fn, mock_ensure):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.put_object.return_value = {"ETag": '"abc123"'}

        result = upload_artifact("test/file.txt", b"hello", {"task_id": "t1"})

        assert result.key == "test/file.txt"
        assert result.size == 5
        assert result.etag == "abc123"
        assert result.timestamp > 0
        mock_ensure.assert_called_once()

    @patch("brainbox.artifacts.ensure_bucket")
    @patch("brainbox.artifacts._s3_client")
    def test_s3_error_raises(self, mock_client_fn, mock_ensure):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.put_object.side_effect = _client_error("500", "Internal")

        with pytest.raises(ArtifactError, match="upload"):
            upload_artifact("test/file.txt", b"hello")

    @patch("brainbox.artifacts.ensure_bucket")
    @patch("brainbox.artifacts._s3_client")
    def test_metadata_tags(self, mock_client_fn, mock_ensure):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.put_object.return_value = {"ETag": '"x"'}

        upload_artifact("k", b"data", {"task_id": "t1"})

        call_kwargs = mock_client.put_object.call_args[1]
        assert "task_id" in call_kwargs["Metadata"]
        assert "timestamp" in call_kwargs["Metadata"]

    @patch("brainbox.artifacts.ensure_bucket")
    @patch("brainbox.artifacts._s3_client")
    def test_default_metadata(self, mock_client_fn, mock_ensure):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.put_object.return_value = {"ETag": '"x"'}

        upload_artifact("k", b"data")

        call_kwargs = mock_client.put_object.call_args[1]
        assert "timestamp" in call_kwargs["Metadata"]


# ---------------------------------------------------------------------------
# download_artifact
# ---------------------------------------------------------------------------


class TestDownloadArtifact:
    @patch("brainbox.artifacts._s3_client")
    def test_success(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_body = MagicMock()
        mock_body.read.return_value = b"file content"
        mock_client.get_object.return_value = {
            "Body": mock_body,
            "Metadata": {"task_id": "t1"},
        }

        body, metadata = download_artifact("test/file.txt")

        assert body == b"file content"
        assert metadata == {"task_id": "t1"}

    @patch("brainbox.artifacts._s3_client")
    def test_not_found(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.get_object.side_effect = _client_error("NoSuchKey")

        with pytest.raises(ArtifactError, match="not found"):
            download_artifact("missing/key")

    @patch("brainbox.artifacts._s3_client")
    def test_other_error(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.get_object.side_effect = _client_error("500", "Internal")

        with pytest.raises(ArtifactError, match="download"):
            download_artifact("some/key")


# ---------------------------------------------------------------------------
# list_artifacts
# ---------------------------------------------------------------------------


class TestListArtifacts:
    @patch("brainbox.artifacts._s3_client")
    def test_returns_list(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_dt = MagicMock()
        mock_dt.timestamp.return_value = 1700000.0
        mock_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "a.txt", "Size": 10, "ETag": '"e1"', "LastModified": mock_dt},
                {"Key": "b.txt", "Size": 20, "ETag": '"e2"', "LastModified": mock_dt},
            ]
        }

        results = list_artifacts()

        assert len(results) == 2
        assert results[0].key == "a.txt"
        assert results[1].key == "b.txt"

    @patch("brainbox.artifacts._s3_client")
    def test_empty_bucket(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.list_objects_v2.return_value = {}

        results = list_artifacts()
        assert results == []

    @patch("brainbox.artifacts._s3_client")
    def test_with_prefix(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.list_objects_v2.return_value = {"Contents": []}

        list_artifacts(prefix="test/")

        call_kwargs = mock_client.list_objects_v2.call_args[1]
        assert call_kwargs["Prefix"] == "test/"

    @patch("brainbox.artifacts._s3_client")
    def test_empty_prefix_omitted(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.list_objects_v2.return_value = {}

        list_artifacts(prefix="")

        call_kwargs = mock_client.list_objects_v2.call_args[1]
        assert "Prefix" not in call_kwargs


# ---------------------------------------------------------------------------
# delete_artifact
# ---------------------------------------------------------------------------


class TestDeleteArtifact:
    @patch("brainbox.artifacts._s3_client")
    def test_success(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        delete_artifact("test/file.txt")

        mock_client.delete_object.assert_called_once()

    @patch("brainbox.artifacts._s3_client")
    def test_s3_error_raises(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.delete_object.side_effect = _client_error("500", "Internal")

        with pytest.raises(ArtifactError, match="delete"):
            delete_artifact("test/file.txt")


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    @patch("brainbox.artifacts._s3_client")
    def test_healthy(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        assert health_check() is True

    @patch("brainbox.artifacts._s3_client")
    def test_unhealthy(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.head_bucket.side_effect = Exception("unreachable")

        assert health_check() is False


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------


class TestArtifactAPI:
    @pytest.fixture()
    def client(self):
        from httpx import ASGITransport, AsyncClient

        from brainbox.api import app

        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.mark.asyncio
    async def test_upload(self, client, monkeypatch):
        monkeypatch.setattr(settings.artifact, "mode", "warn")
        result = ArtifactResult(key="test/f.txt", size=5, etag="abc", timestamp=100)
        with patch("brainbox.api.upload_artifact", return_value=result):
            resp = await client.post(
                "/api/artifacts/test/f.txt",
                content=b"hello",
                headers={"content-type": "text/plain"},
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["stored"] is True
        assert body["key"] == "test/f.txt"

    @pytest.mark.asyncio
    async def test_download(self, client, monkeypatch):
        monkeypatch.setattr(settings.artifact, "mode", "warn")
        with patch(
            "brainbox.api.download_artifact",
            return_value=(b"content", {"content_type": "text/plain"}),
        ):
            resp = await client.get("/api/artifacts/test/f.txt")
        assert resp.status_code == 200
        assert resp.content == b"content"

    @pytest.mark.asyncio
    async def test_list(self, client, monkeypatch):
        monkeypatch.setattr(settings.artifact, "mode", "warn")
        items = [
            ArtifactResult(key="a.txt", size=10, etag="e1", timestamp=100),
            ArtifactResult(key="b.txt", size=20, etag="e2", timestamp=200),
        ]
        with patch("brainbox.api.list_artifacts", return_value=items):
            resp = await client.get("/api/artifacts?prefix=")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["key"] == "a.txt"

    @pytest.mark.asyncio
    async def test_delete(self, client, monkeypatch):
        monkeypatch.setattr(settings.artifact, "mode", "warn")
        with patch("brainbox.api.delete_artifact"):
            resp = await client.request("DELETE", "/api/artifacts/test/f.txt")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    @pytest.mark.asyncio
    async def test_health(self, client, monkeypatch):
        monkeypatch.setattr(settings.artifact, "mode", "warn")
        with patch("brainbox.api.artifact_health_check", return_value=True):
            resp = await client.get("/api/artifacts/health")
        assert resp.status_code == 200
        assert resp.json()["healthy"] is True


class TestArtifactModes:
    @pytest.fixture()
    def client(self):
        from httpx import ASGITransport, AsyncClient

        from brainbox.api import app

        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.mark.asyncio
    async def test_off_returns_503(self, client, monkeypatch):
        monkeypatch.setattr(settings.artifact, "mode", "off")
        resp = await client.post(
            "/api/artifacts/test/f.txt",
            content=b"hello",
        )
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_warn_swallows_errors(self, client, monkeypatch):
        monkeypatch.setattr(settings.artifact, "mode", "warn")
        with patch(
            "brainbox.api.upload_artifact",
            side_effect=ArtifactError("upload", "k", "connection refused"),
        ):
            resp = await client.post("/api/artifacts/test/f.txt", content=b"hello")
        assert resp.status_code == 201
        assert resp.json()["stored"] is False

    @pytest.mark.asyncio
    async def test_enforce_returns_502(self, client, monkeypatch):
        monkeypatch.setattr(settings.artifact, "mode", "enforce")
        with patch(
            "brainbox.api.upload_artifact",
            side_effect=ArtifactError("upload", "k", "connection refused"),
        ):
            resp = await client.post("/api/artifacts/test/f.txt", content=b"hello")
        assert resp.status_code == 502

    @pytest.mark.asyncio
    async def test_health_off(self, client, monkeypatch):
        monkeypatch.setattr(settings.artifact, "mode", "off")
        resp = await client.get("/api/artifacts/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["healthy"] is False
        assert data["mode"] == "off"

    @pytest.mark.asyncio
    async def test_download_warn_not_found_returns_404(self, client, monkeypatch):
        monkeypatch.setattr(settings.artifact, "mode", "warn")
        with patch(
            "brainbox.api.download_artifact",
            side_effect=ArtifactError("download", "k", "not found"),
        ):
            resp = await client.get("/api/artifacts/test/f.txt")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_download_enforce_not_found_returns_404(self, client, monkeypatch):
        monkeypatch.setattr(settings.artifact, "mode", "enforce")
        with patch(
            "brainbox.api.download_artifact",
            side_effect=ArtifactError("download", "k", "not found"),
        ):
            resp = await client.get("/api/artifacts/test/f.txt")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_warn_swallows_connection_errors(self, client, monkeypatch):
        monkeypatch.setattr(settings.artifact, "mode", "warn")
        with patch(
            "brainbox.api.upload_artifact",
            side_effect=ConnectionError("Connection refused"),
        ):
            resp = await client.post("/api/artifacts/test/f.txt", content=b"hello")
        assert resp.status_code == 201
        assert resp.json()["stored"] is False

    @pytest.mark.asyncio
    async def test_enforce_connection_error_returns_502(self, client, monkeypatch):
        monkeypatch.setattr(settings.artifact, "mode", "enforce")
        with patch(
            "brainbox.api.upload_artifact",
            side_effect=ConnectionError("Connection refused"),
        ):
            resp = await client.post("/api/artifacts/test/f.txt", content=b"hello")
        assert resp.status_code == 502
