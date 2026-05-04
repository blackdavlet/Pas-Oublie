FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/
WORKDIR /app
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt
COPY storage.proto storage_pb2.py storage_pb2_grpc.py server.py ./
EXPOSE 50051
CMD ["python", "server.py"]