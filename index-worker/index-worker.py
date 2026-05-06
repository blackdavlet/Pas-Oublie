import os, json, asyncio
import asyncpg
import redis.asyncio as redis
from minio import Minio
from openai import OpenAI

REDIS_URL = os.environ["REDIS_URL"]
DATABASE_URL = os.environ["DATABASE_URL"]
MINIO_ENDPOINT = os.environ["MINIO_ENDPOINT"]
MINIO_ACCESS_KEY = os.environ["MINIO_ACCESS_KEY"]
MINIO_SECRET_KEY = os.environ["MINIO_SECRET_KEY"]

_r = redis.from_url(REDIS_URL, decode_responses=True)
_minio = Minio(MINIO_ENDPOINT,
               access_key=MINIO_ACCESS_KEY,
               secret_key=MINIO_SECRET_KEY,
               secure=False)
_openai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


async def get_pool():
    return await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract plain text from file bytes depending on type."""
    if filename.endswith(".txt"):
        return file_bytes.decode("utf-8", errors="ignore")
    
    elif filename.endswith(".pdf"):
        import pdfplumber, io
        text = ""
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
        return text

    return ""


def generate_embedding(text: str) -> list[float]:
    """returns vector of 1536"""
    if not text.strip():
        return [0.0] * 1536
    
    response = _openai.embeddings.create(
        model="text-embedding-3-small",
        input=text[:8000] 
    )
    return response.data[0].embedding


async def process_file(pool, file_id: str,
                       storage_path: str, filename: str):
    try:
        bucket, object_name = storage_path.split("/", 1)
        response = _minio.get_object(bucket, object_name)
        file_bytes = response.read()
        
        text = extract_text(file_bytes, filename)
        
        embedding = generate_embedding(text)
        
        async with pool.acquire() as con:
            await con.execute(
                """
                INSERT INTO file_embeddings (file_id, embedding)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
                """,
                file_id, embedding
            )
        
        print(f"Indexed {filename} ({file_id})", flush=True)
    
    except Exception as e:
        print(f"Failed to index {file_id}: {e}", flush=True)


async def main():
    pool = await get_pool()
    pubsub = _r.pubsub()
    await pubsub.subscribe("index:queue")
    
    print("index-worker listening on index:queue", flush=True)
    
    async for msg in pubsub.listen():
        if msg["type"] != "message":
            continue
        
        data = json.loads(msg["data"])
        await process_file(
            pool,
            file_id=data["file_id"],
            storage_path=data["storage_path"],
            filename=data["filename"]
        )

if __name__ == "__main__":
    asyncio.run(main())