import os
import asyncio
import grpc
import asyncpg
from concurrent import futures
from openai import OpenAI

import search_pb2
import search_pb2_grpc

DATABASE_URL = os.environ["DATABASE_URL"]
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

_openai = OpenAI(api_key=OPENAI_API_KEY)


def generate_query_embedding(query: str) -> list[float]:
    response = _openai.embeddings.create(
        model="text-embedding-3-small",
        input=query[:8000]
    )
    return response.data[0].embedding

async def _query_pgvector(embedding, workspace_id, limit):
    con = await asyncpg.connect(DATABASE_URL)
    try:
        if workspace_id:
            return await con.fetch(
                """
                SELECT f.file_id, f.filename, f.storage_path,
                       (2 - (fe.embedding <-> $1::vector)) / 2 as similarity
                FROM file_embeddings fe
                JOIN file f ON fe.file_id = f.file_id
                WHERE f.workspace_id = $2
                ORDER BY fe.embedding <-> $1::vector
                LIMIT $3
                """,
                str(embedding), workspace_id, limit
            )
        else:
            return await con.fetch(
                """
                SELECT f.file_id, f.filename, f.storage_path,
                       (2 - (fe.embedding <-> $1::vector)) / 2 as similarity
                FROM file_embeddings fe
                JOIN file f ON fe.file_id = f.file_id
                ORDER BY fe.embedding <-> $1::vector
                LIMIT $2
                """,
                str(embedding), limit
            )
    finally:
        await con.close()

class SearchServicer(search_pb2_grpc.SearchServiceServicer):

    def Search(self, request, context):
        try:
            query_embedding = generate_query_embedding(request.query)
            limit = request.limit if request.limit > 0 else 10
            workspace_id = request.workspace_id if request.workspace_id else None

            rows = asyncio.run(
                _query_pgvector(query_embedding, workspace_id, limit)
            )

            results = []
            for row in rows:
                results.append(search_pb2.SearchResult(
                    file_id=row["file_id"],
                    filename=row["filename"],
                    storage_path=row["storage_path"],
                    similarity=float(row["similarity"])
                ))

            return search_pb2.SearchResponse(results=results)

        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, str(e))

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    search_pb2_grpc.add_SearchServiceServicer_to_server(SearchServicer(), server)
    server.add_insecure_port("[::]:50052")
    server.start()
    print("search_service listening on :50052", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()


