"""Google Cloud Storage client wrapper with fake-gcs-server emulator support."""

import os
from pathlib import Path

from google.cloud import storage
from google.auth.credentials import AnonymousCredentials


def get_gcs_client() -> storage.Client:
    """Return a GCS client.

    When GCS_EMULATOR_HOST is set, connects to fake-gcs-server with anonymous
    credentials — no code changes needed for production.
    """
    emulator_host = os.environ.get("GCS_EMULATOR_HOST")
    if emulator_host:
        return storage.Client(
            credentials=AnonymousCredentials(),
            project="financial-dev",
            client_options={"api_endpoint": emulator_host},
        )
    return storage.Client()


def upload_bytes(
    bucket_name: str,
    blob_path: str,
    data: bytes,
    content_type: str = "application/octet-stream",
    client: storage.Client | None = None,
) -> str:
    """Upload bytes to GCS. Returns the gs:// URI."""
    gcs = client or get_gcs_client()
    bucket = gcs.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(data, content_type=content_type)
    return f"gs://{bucket_name}/{blob_path}"


def download_bytes(
    bucket_name: str,
    blob_path: str,
    client: storage.Client | None = None,
) -> bytes:
    """Download bytes from GCS."""
    gcs = client or get_gcs_client()
    bucket = gcs.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    return blob.download_as_bytes()


def ensure_bucket(bucket_name: str, location: str = "US", client: storage.Client | None = None) -> None:
    """Create bucket if it does not exist."""
    gcs = client or get_gcs_client()
    try:
        gcs.create_bucket(bucket_name, location=location)
    except Exception as exc:
        if "409" not in str(exc) and "already own" not in str(exc).lower():
            raise
