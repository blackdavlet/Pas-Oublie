import os
import uuid
import json
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


from app import db
from app import ws
from app import minio_client
from app import grpc_client
from app import auth                    
from app.snowflake import generate_id
from app.auth import create_token, get_current_user

import redis.asyncio as aioredis

app = FastAPI(
    title="Pas Oublie API",
    version="1.0.0"
)

app.include_router(ws.router)

_r = aioredis.from_url(os.environ["REDIS_URL"], decode_responses=True)


class RegisterSchema(BaseModel):
    username: str
    email: str
    password: str

class LoginSchema(BaseModel):
    email: str
    password: str

@app.post("/auth/register")
async def register(data: RegisterSchema):
    user = await db.create_user(data.username, data.email, data.password)
    if user is None:
        raise HTTPException(400, "User with similar username already exists")
    token = create_token(user["user_id"], user["username"])
    return {"token": token, "user_id": user["user_id"]}

@app.post("/auth/login")
async def login(data: LoginSchema):
    user = await db.get_user_by_email(data.email)
    if user is None or not db.verifypassword(data.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    token = create_token(user["user_id"], user["username"])
    return {"token": token, "user_id": user["user_id"]}

@app.get("/auth/me")
async def me(current_user=Depends(get_current_user)):
    return {
        "user_id": current_user["user_id"],
        "username": current_user["username"],
        "email": current_user["email"]
    }

@app.post("/files/upload/init")
async def upload(
    filename: str,
    workspace_id: int,
    folder_id: int,
    current_user = Depends(get_current_user)
):

    object_name = f"{workspace_id}/{uuid.uuid4().hex}/{filename}"

    upload_id = minio_client.init_multipart(object_name)

    await _r.hset(f"upload:{upload_id}", mapping={
        "filename": filename,
        "object_name": object_name,
        "workspace_id": workspace_id,
        "folder_id": folder_id,
        "user_id": current_user["user_id"],
        "parts": "[]"
    })

    await _r.expire(f"upload: {upload_id}", 3600)

    return {"upload_id": upload_id, "object_name": object_name}

@app.put("files/upload/{upload_id}/chunk/{part_number}")
async def upload_chunk(
    upload_id: str,
    part_number: int,
    chunk: UploadFile
):

    meta = await _r.hgetall(f"upload:{upload_id}")
    if not meta:
        raise HTTPException(404, "Upload session not found or expired")

    data = await chunk.read()

    etag = minio_client.upload_part(
        meta["object_name"], upload_id, part_number, data
    )

    parts = json.loads(meta["parts"])
    parts.append({"part": part_number, "etag": etag})
    await _r.hset(f"{upload_id}", "parts", json.dumps(parts))

    return {"part": part_number, "etag": etag}

app.post("/files/upload/{upload_id}/complete")
async def upload_complete(upload_id: str):
    meta = await _r.hgetall(f"upload:{upload_id}")
    if not meta:
        raise HTTPException(404, "session not found or expired")

    parts = json.loads(meta["parts"])

    storage_path = minio_client.complete_multipart(
        meta["object_name"], upload_id, parts
    )

    file_row = await db.create_file(
        user_id=int(meta["user_id"]),
        filename=meta["filename"],
        folder_id=int(meta["folder_id"]),
        workspace_id=int(meta["workspace_id"]),
        mime_type="application/octet-stream"
    )

    await _r.delete(f"upload:{upload_id}")

    await ws.broadcast_event(int(meta["workspace_id"]), {
        "event": "file_uploaded",
        "filename": meta["filename"],
        "uploaded_by": meta["user_id"]
    })

    return {
        "file_id": str(file_row["file_id"]),
        "filename": meta["filename"],
        "storage_path": storage_path
    }











@app.get("/files/{file_id}")
async def get_file():

@app.get("/search")
async def search():




