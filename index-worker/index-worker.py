import os
import json
import asyncio
import asyncpg
import requests
import redis.asyncio as redis
from openai import OpenAI

REDIS_URL = os.environ["REDIS_URL"]
DATABASE_URL = os.environ["DATABASE_URL"]
SEAWEED_MASTER = os.environ.get("SEAWEED_MASTER", "seaweedfs:9333")
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

_r = redis.from_url(REDIS_URL, decode_responses=True)
_openai = OpenAI(api_key=OPENAI_API_KEY)
_pool = None


async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return _pool


def fetch_file_from_seaweed(storage_path: str) -> bytes:
    meta = json.loads(storage_path)
    assembled = b""
    for fid in meta["fids"]:
        vol_id = fid.split(",")[0]
        res = requests.get(f"http://{SEAWEED_MASTER}/dir/lookup?volumeId={vol_id}")
        location = res.json()["locations"][0]["publicUrl"]
        chunk = requests.get(f"http://{location}/{fid}")
        assembled += chunk.content
    return assembled


def extract_text(file_bytes: bytes, filename: str) -> str:
    if filename.endswith(".txt"):
        return file_bytes.decode("utf-8", errors="ignore")
    elif filename.endswith(".pdf"):
        import pdfplumber
        from io import BytesIO
        text = ""
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
        return text
    elif filename.endswith(".docx"):
        import docx
        from io import BytesIO
        doc = docx.Document(BytesIO(file_bytes))
        return "\n".join([p.text for p in doc.paragraphs])
    return None


def generate_embedding(text: str) -> list[float]:
    if not text.strip():
        return [0.0] * 1536
    response = _openai.embeddings.create(
        model="text-embedding-3-small",
        input=text[:8000]
    )
    return response.data[0].embedding


async def process_file(pool, file_id: str, storage_path: str, filename: str):
    try:
        file_bytes = fetch_file_from_seaweed(storage_path)
        text = extract_text(file_bytes, filename)
        embedding = generate_embedding(text)
        async with pool.acquire() as con:
            await con.execute(
                """
                INSERT INTO file_embeddings (file_id, embedding)
                VALUES ($1, $2::vector)
                ON CONFLICT DO NOTHING
                """,
                int(file_id), str(embedding)
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


