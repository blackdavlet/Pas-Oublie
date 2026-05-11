import os
import uuid
import requests
from io import BytesIO

SEAWEED_MASTER = os.environ.get("SEAWEED_MASTER", "seaweedfs:9333")
SEAWEED_FILER = os.environ.get("SEAWEED_FILER", "seaweedfs:8080")
BUCKET = "pasoublie-files"


def _assign() -> tuple[str, str]:
    """Ask SeaweedFS master for a volume to write to."""
    res = requests.get(f"http://{SEAWEED_MASTER}/dir/assign")
    data = res.json()
    return data["fid"], f"http://{data['url']}/{data['fid']}"


def init_multipart(object_name: str) -> str:
    """Return a session ID — SeaweedFS handles chunks natively."""
    return str(uuid.uuid4())


def upload_part(object_name: str, upload_id: str,
                part_number: int, data: bytes) -> str:
    """Upload chunk directly to SeaweedFS volume."""
    fid, url = _assign()
    requests.put(url, data=data)
    return fid  # fid IS the etag — it's the permanent address


def complete_multipart(object_name: str, upload_id: str, parts: list) -> str:
    """
    For SeaweedFS each part is already stored permanently.
    We store the list of fids as the storage_path.
    """
    import json
    fids = [p["etag"] for p in sorted(parts, key=lambda x: x["part"])]
    # storage_path encodes all chunk fids
    return json.dumps({"object_name": object_name, "fids": fids})

def download_file(storage_path: str) -> bytes:
    """Fetch all chunks and assemble."""
    import json
    meta = json.loads(storage_path)
    assembled = b""
    for fid in meta["fids"]:
        # ask master where this fid lives
        res = requests.get(f"http://{SEAWEED_MASTER}/dir/lookup?volumeId={fid.split(',')[0]}")
        location = res.json()["locations"][0]["publicUrl"]
        chunk = requests.get(f"http://{location}/{fid}")
        assembled += chunk.content
    return assembled


def delete_file(storage_path: str):
    """Delete all chunks."""
    import json
    meta = json.loads(storage_path)
    for fid in meta["fids"]:
        res = requests.get(f"http://{SEAWEED_MASTER}/dir/lookup?volumeId={fid.split(',')[0]}")
        location = res.json()["locations"][0]["publicUrl"]
        requests.delete(f"http://{location}/{fid}")