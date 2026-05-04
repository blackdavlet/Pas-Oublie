import os
from concurrent import futures
import grpc
from minio import Minio
from io import BytesIO

import storage_pb2
import storage_pb2_grpc

MINIO_ENDPOINT = os.environ["MINIO_ENDPOINT"]
MINIO_ACCESS_KEY = os.environ["MINIO_ACCESS_KEY"]
MINIO_SECRET_KEY = os.environ["MINIO_SECRET_KEY"]
BUCKET = "pasoublie-files"

_minio = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)


class StorageServicer(storage_pb2_grpc.StorageServiceServicer):

    def DownloadFile(self, request, context):
        try:
            object_name = request.storage_path.split("/", 1)[1]

            response = _minio.get_object(BUCKET, object_name)
            file_data = response.read()
            stat = _minio.stat_object(BUCKET, object_name)

            return storage_pb2.DownloadResponse(
                file_data=file_data,
                filename=object_name.split("/")[-1],
                mime_type=stat.content_type or "application/octet-stream",
                size_bytes=stat.size
            )
        except Exception as e:
            context.abort(grpc.StatusCode.NOT_FOUND, str(e))

    def DeleteFile(self, request, context):
        try:
            object_name = request.storage_path.split("/", 1)[1]
            _minio.remove_object(BUCKET, object_name)
            return storage_pb2.DeleteResponse(success=True)
        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, str(e))


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    storage_pb2_grpc.add_StorageServiceServicer_to_server(StorageServicer(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    print("storage_service listening on :50051", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()