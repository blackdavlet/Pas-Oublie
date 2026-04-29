import os
from minio import Minio

BUCKET = "pasoublie-files"

_client = None

def get_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            os.environ["MINIO_ENDPOINT"],
            access_key=os.environ["MINIO_ACCESS_KEY"],
            secret_key=os.environ["MINIO_SECRET_KEY"],
            secure=False
        )
        if not _client.bucket_exists(BUCKET):
            _client.make_bucket(BUCKET)
    return _client


def init_multipart(object_name: str) -> str:
    """Start a multipart upload, returns upload_id from MinIO."""
    client = get_client()
    upload_id = client._create_multipart_upload(BUCKET, object_name, {})
    return upload_id


def upload_part(object_name: str, upload_id: str,
                part_number: int, data: bytes) -> str:
    """Upload one chunk, returns etag."""
    client = get_client()
    from io import BytesIO
    etag = client._upload_part(
        BUCKET, object_name, upload_id,
        part_number, BytesIO(data), len(data)
    )
    return etag


def complete_multipart(object_name: str, upload_id: str, parts: list) -> str:
    """
    parts = [{"part": 1, "etag": "abc"}, {"part": 2, "etag": "def"}]
    Returns final storage path.
    """
    client = get_client()
    from minio.commonconfig import Part
    client._complete_multipart_upload(
        BUCKET, object_name, upload_id,
        [Part(p["part"], p["etag"]) for p in parts]
    )
    return f"{BUCKET}/{object_name}"