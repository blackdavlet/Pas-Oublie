import os
import json
import grpc
import requests
from concurrent import futures

import storage_pb2
import storage_pb2_grpc

SEAWEED_MASTER = os.environ.get("SEAWEED_MASTER", "seaweedfs:9333")


class StorageServicer(storage_pb2_grpc.StorageServiceServicer):

    def DownloadFile(self, request, context):
        try:
            meta = json.loads(request.storage_path)
            assembled = b""
            for fid in meta["fids"]:
                vol_id = fid.split(",")[0]
                res = requests.get(
                    f"http://{SEAWEED_MASTER}/dir/lookup?volumeId={vol_id}"
                )
                location = res.json()["locations"][0]["publicUrl"]
                chunk = requests.get(f"http://{location}/{fid}")
                assembled += chunk.content

            return storage_pb2.DownloadResponse(
                file_data=assembled,
                filename=meta["object_name"].split("/")[-1],
                mime_type="application/octet-stream",
                size_bytes=len(assembled)
            )
        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def DeleteFile(self, request, context):
        try:
            meta = json.loads(request.storage_path)
            for fid in meta["fids"]:
                vol_id = fid.split(",")[0]
                res = requests.get(
                    f"http://{SEAWEED_MASTER}/dir/lookup?volumeId={vol_id}"
                )
                location = res.json()["locations"][0]["publicUrl"]
                requests.delete(f"http://{location}/{fid}")
            return storage_pb2.DeleteResponse(success=True)
        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def DeleteFile(self, request, context):
        try:
            meta = json.loads(request.storage_path)
            for fid in meta["fids"]:
                vol_id = fid.split(",")[0]
                res = requests.get(
                    f"http://{SEAWEED_MASTER}/dir/lookup?volumeId={vol_id}"
                )
                location = res.json()["locations"][0]["publicUrl"]
                requests.delete(f"http://{location}/{fid}")
            return storage_pb2.DeleteResponse(success=True)
        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, str(e))


def serve():
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=4),
        options=[
            ('grpc.max_receive_message_length', 100 * 1024 * 1024),
            ('grpc.max_sent_message_length', 100 * 1024 * 1024),
        ]
    )
    storage_pb2_grpc.add_StorageServiceServicer_to_server(
        StorageServicer(), server
    )
    server.add_insecure_port("[::]:50051")
    server.start()
    print("storage_service listening on :50051", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
