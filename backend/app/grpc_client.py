import os
import grpc
from app import storage_pb2, storage_pb2_grpc
from app import search_pb2, search_pb2_grpc

# ─── STORAGE ────────────────────────────────────────────
_storage_channel = None
_storage_stub = None

def _get_storage_stub():
    global _storage_channel, _storage_stub
    if _storage_stub is None:
        _storage_channel = grpc.insecure_channel(
            os.environ["STORAGE_SERVICE_URL"],
            options=[
                ('grpc.max_receive_message_length', 100 * 1024 * 1024),
                ('grpc.max_send_message_length', 100 * 1024 * 1024),
            ]
        )
        _storage_stub = storage_pb2_grpc.StorageServiceStub(_storage_channel)
    return _storage_stub


def download_file(storage_path: str):
    req = storage_pb2.DownloadRequest(storage_path=storage_path)
    return _get_storage_stub().DownloadFile(req, timeout=30)


def delete_file(storage_path: str):
    req = storage_pb2.DeleteRequest(storage_path=storage_path)
    return _get_storage_stub().DeleteFile(req, timeout=10)

# ─── SEARCH ─────────────────────────────────────────────
_search_channel = None
_search_stub = None

def _get_search_stub():
    global _search_channel, _search_stub
    if _search_stub is None:
        _search_channel = grpc.insecure_channel(
            os.environ["SEARCH_SERVICE_URL"]
        )
        _search_stub = search_pb2_grpc.SearchServiceStub(_search_channel)
    return _search_stub


def search(query: str, workspace_id: int, limit: int = 10):
    req = search_pb2.SearchRequest(
        query=query,
        workspace_id=workspace_id,
        limit=limit
    )
    response = _get_search_stub().Search(req, timeout=15)
    return [
        {
            "file_id": str(r.file_id),
            "filename": r.filename,
            "storage_path": r.storage_path,
            "similarity": r.similarity
        }
        for r in response.results
    ]
