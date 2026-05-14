FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/
WORKDIR /app
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt
COPY search.proto search_pb2.py search_pb2_grpc.py search_service.py ./
EXPOSE 50052
CMD ["python", "search_service.py"]
