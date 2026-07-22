import os
import io
import socket
import logging
from minio import Minio

logger = logging.getLogger("storage")

MINIO_URL = os.getenv("MINIO_URL", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "files")

_minio_client = None
_bucket_ready = False


def _minio_alive():
    host = MINIO_URL.split(":")[0]
    port = int(MINIO_URL.split(":")[1])
    try:
        s = socket.create_connection((host, port), timeout=0.2)
        s.close()
        return True
    except Exception:
        return False


def _get_client():
    global _minio_client, _bucket_ready
    if _minio_client is not None and _bucket_ready:
        return _minio_client
    if not _minio_alive():
        return None
    try:
        _minio_client = Minio(MINIO_URL, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=False)
        if not _minio_client.bucket_exists(MINIO_BUCKET):
            _minio_client.make_bucket(MINIO_BUCKET)
        _bucket_ready = True
    except Exception:
        _minio_client = None
        _bucket_ready = False
        return None
    return _minio_client


def upload_file(key: str, data: bytes, content_type: str) -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        client.put_object(MINIO_BUCKET, key, io.BytesIO(data), len(data), content_type=content_type)
        return True
    except Exception:
        global _minio_client, _bucket_ready
        _minio_client = None
        _bucket_ready = False
        return False


def download_file(key: str) -> bytes | None:
    client = _get_client()
    if client is None:
        return None
    try:
        response = client.get_object(MINIO_BUCKET, key)
        data = response.read()
        response.close()
        response.release_conn()
        return data
    except Exception:
        global _minio_client, _bucket_ready
        _minio_client = None
        _bucket_ready = False
        return None


def delete_file(key: str) -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        client.remove_object(MINIO_BUCKET, key)
        return True
    except Exception:
        return False
