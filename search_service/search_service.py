import os
from concurrent import futures
import grpc
import asyncpg
import asyncio
from openai import OpenAI

import search_pb2
import search_pb2_grpc

DATABASE_URL = os.environ["DATABASE_URL"]
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

_openai = OpenAI(api_key=OPENAI_API_KEY)
_pool = None


async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return _pool


def generate_query_embedding(query: str) -> list[float]:
    response = _openai.embeddings.create(
        model="text-embedding-3-small",
        input=query[:8000]
    )
    return response.data[0].embedding


class SearchServicer(search_pb2_grpc.SearchServiceServicer):

    def Search(self, request, context):
        try:
            query_embedding = generate_query_embedding(request.query)
            limit = request.limit if request.limit > 0 else 10

            loop = asyncio.new_event_loop()
            rows = loop.run_until_complete(
                self._query_pgvector(
                    query_embedding,
                    request.workspace_id,
                    limit
                )
            )
            loop.close()

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

    async def _query_pgvector(self, embedding: list, workspace_id: int, limit: int):
        pool = await get_pool()
        async with pool.acquire() as con:
            return await con.fetch(
                """
                SELECT f.file_id, f.filename, f.storage_path,
                       1 - (fe.embedding <-> $1::vector) as similarity
                FROM file_embeddings fe
                JOIN file f ON fe.file_id = f.file_id
                WHERE f.workspace_id = $2
                ORDER BY fe.embedding <-> $1::vector
                LIMIT $3
                """,
                str(embedding), workspace_id, limit
            )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    search_pb2_grpc.add_SearchServiceServicer_to_server(SearchServicer(), server)
    server.add_insecure_port("[::]:50052")
    server.start()
    print("search_service listening on :50052", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
    