import os
import grpc
from app import storage_pb2, storage_pb2_grpc

_storage_channel = None
_storage_stub = None

def _get_storage_stub():
    global _storage_channel, _storage_stub
    if _storage_stub is None:
        _storage_channel = grpc.insecure_channel(
            os.environ["STORAGE_SERVICE_URL"]
        )
        _storage_stub = storage_pb2_grpc.StorageServiceStub(_storage_channel)
    return _storage_stub


def download_file(storage_path: str):
    req = storage_pb2.DownloadRequest(storage_path=storage_path)
    return _get_storage_stub().DownloadFile(req, timeout=30)


def delete_file(storage_path: str):
    req = storage_pb2.DeleteRequest(storage_path=storage_path)
    return _get_storage_stub().DeleteFile(req, timeout=10)