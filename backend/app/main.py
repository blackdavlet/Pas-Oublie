import os
import uuid
import json
import requests as req_lib
from pathlib import Path
from prometheus_fastapi_instrumentator import Instrumentator

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Request
from fastapi.responses import JSONResponse, Response, RedirectResponse, StreamingResponse
from pydantic import BaseModel


from app import db
from app import ws
from app import seaweedfs_client
from app import grpc_client
from app import auth                    
from app.snowflake import generate_id
from app.auth import create_token, get_current_user

import redis.asyncio as aioredis

app = FastAPI(
    title="Pas Oublie API",
    version="1.0.0"
)

Instrumentator().instrument(app).expose(app)
app.include_router(ws.router)

_r = aioredis.from_url(os.environ["REDIS_URL"], decode_responses=True)


class RegisterSchema(BaseModel):
    username: str
    email: str
    password: str

class LoginSchema(BaseModel):
    email: str
    password: str

class WorkspaceSchema(BaseModel):
    workspace_name: str

class MemberSchema(BaseModel):
    user_id: int
    role: str

class FolderSchema(BaseModel):
    folder_name: str
    workspace_id: int


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
    if user is None or not db.verify_password(data.password, user["password_hash"]):
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

    upload_id = seaweedfs_client.init_multipart(object_name)

    await _r.hset(f"upload:{upload_id}", mapping={
        "filename": filename,
        "object_name": object_name,
        "workspace_id": workspace_id,
        "folder_id": folder_id,
        "user_id": current_user["user_id"],
        "parts": "[]"
    })

    await _r.expire(f"upload:{upload_id}", 3600)

    return {"upload_id": upload_id, "object_name": object_name}

@app.put("/files/upload/{upload_id}/chunk/{part_number}")
async def upload_chunk(
    upload_id: str,
    part_number: int,
    chunk: UploadFile
):

    meta = await _r.hgetall(f"upload:{upload_id}")
    if not meta:
        raise HTTPException(404, "Upload session not found or expired")

    data = await chunk.read()

    etag = seaweedfs_client.upload_part(
        meta["object_name"], upload_id, part_number, data
    )

    parts = json.loads(meta["parts"])
    parts.append({"part": part_number, "etag": etag})
    await _r.hset(f"upload:{upload_id}", "parts", json.dumps(parts))

    return {"part": part_number, "etag": etag}

@app.post("/files/upload/{upload_id}/complete")
async def upload_complete(upload_id: str):
    meta = await _r.hgetall(f"upload:{upload_id}")
    total_size = 0
    if not meta:
        raise HTTPException(404, "session not found or expired")

    parts = json.loads(meta["parts"])

    storage_path = seaweedfs_client.complete_multipart(
        meta["object_name"], upload_id, parts
    )

    file_row = await db.create_file(
        user_id=int(meta["user_id"]),
        filename=meta["filename"],
        folder_id=int(meta["folder_id"]),
        workspace_id=int(meta["workspace_id"]),
        mime_type="application/octet-stream",
        storage_path=storage_path,
        size_bytes=total_size
    )

    await _r.publish("index:queue", json.dumps({
        "file_id": str(file_row["file_id"]),
        "storage_path": storage_path,
        "filename": meta["filename"]
    }))
    
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
async def get_file(
    file_id: str,
    current_user=Depends(get_current_user)
):
    file = await db.get_file_by_id(file_id)
    if file is None:
        raise HTTPException(404, "File not found")
    return {
        "file_id": str(file["file_id"]),
        "filename": file["filename"],
        "uploaded_at": file["uploaded_at"].isoformat(),
        "mime_type": file["mime_type"],
        "size_bytes": file["size_bytes"]
    }

@app.get("/files/{file_id}/download")
async def download_file(file_id: str, current_user=Depends(get_current_user)):
    file = await db.get_file_by_id(int(file_id))
    if not file:
        raise HTTPException(404, "File not found")

    import json
    import requests as req_lib
    meta = json.loads(file["storage_path"])
    fids = meta["fids"]
    SEAWEED_MASTER = os.environ.get("SEAWEED_MASTER", "seaweedfs:9333")

    def get_chunk_url(fid):
        vol_id = fid.split(",")[0]
        lookup = req_lib.get(f"http://{SEAWEED_MASTER}/dir/lookup?volumeId={vol_id}").json()
        public_url = lookup['locations'][0]['publicUrl']
        return f"http://{public_url}/{fid}"

    def stream_chunks():
        for fid in fids:
            vol_id = fid.split(",")[0]
            res = req_lib.get(f"http://{SEAWEED_MASTER}/dir/lookup?volumeId={vol_id}")
            location = res.json()["locations"][0]["publicUrl"]
            chunk_res = req_lib.get(f"http://{location}/{fid}", stream=True)
            for data in chunk_res.iter_content(chunk_size=1024*1024):
                yield data

    # get total size for Content-Length header
    total_size = 0
    if len(fids) <= 5:
        total_size = sum(int(req_lib.head(get_chunk_url(fid)).headers.get('content-length', 0)) for fid in fids)

    headers = {"Content-Disposition": f"attachment; filename={file['filename']}"}
    if total_size:
        headers["Content-Length"] = str(total_size)

    return StreamingResponse(
        stream_chunks(),
        media_type="application/octet-stream",
        headers=headers
    )

@app.delete("/files/{file_id}/delete")
async def delete_file(
    file_id: str,
    current_user=Depends(get_current_user)
):
    file = await db.get_file_by_id(file_id)
    if file is None:
        raise HTTPException(404, "File not found")
    
    grpc_client.delete_file(file["storage_path"])
    await db.delete_file(file_id)

    await ws.broadcast_event(file["workspace_id"], {
        "event": "file_deleted",
        "file_id": file_id,
        "filename": file["filename"]
    })
    
    return {"message": "File deleted"}

@app.get("/search")
async def search(
    query: str,
    workspace_id: int = None,
    current_user=Depends(get_current_user)
):
    if not query.strip():
        raise HTTPException(400, "Query cannot be empty")
    
    # if no workspace specified, get all user's workspaces
    if not workspace_id:
        user_workspaces = await db.get_user_workspaces(current_user["user_id"])
        workspace_ids = [w["workspace_id"] for w in user_workspaces]
    else:
        workspace_ids = [workspace_id]
    
    all_results = []
    for ws_id in workspace_ids:
        results = grpc_client.search(query, ws_id)
        all_results.extend(results)
    
    # sort by similarity descending
    all_results.sort(key=lambda x: x["similarity"], reverse=True)
    return {"results": all_results[:10]}

@app.post("/workspaces")
async def create_workspace(
    data: WorkspaceSchema,
    current_user=Depends(get_current_user)
):
    workspace = await db.create_workspace(
        data.workspace_name,
        current_user["user_id"]
    )
    return{
        "workspace_id": workspace["workspace_id"],
        "workspace_name": workspace["workspace_name"]
    }

@app.get("/workspaces")
async def get_workspaces(current_user=Depends(get_current_user)):
    workspaces = await db.get_user_workspaces(current_user["user_id"])
    return{"workspaces": [dict(w) for w in workspaces]}

@app.post("/workspaces/{workspace_id}/members")
async def add_member(
    workspace_id: int,
    data: MemberSchema,
    current_user=Depends(get_current_user)
):
    success = await db.add_workspace_member(
        data.user_id, workspace_id, data.role
    )
    if not success:
        raise HTTPException(400, "User is already a member")
    return {"message": "Member added"}

@app.get("/workspaces/{workspace_id}/files")
async def get_workspace_files(
    workspace_id: int,
    folder_id: int,
    current_user=Depends(get_current_user)
):
    files = await db.get_files_by_folder(folder_id)
    return {"files": [
        {
            **dict(f),
            "file_id": str(f["file_id"]),  # ← convert to string
            "uploaded_at": f["uploaded_at"].isoformat()
        }
        for f in files
    ]}

@app.post("/folders")
async def create_folder(
    data: FolderSchema,
    current_user=Depends(get_current_user)
):
    folder = await db.create_folder(
        current_user["user_id"],
        data.folder_name,
        data.workspace_id
    )
    return{
        "folder_id": folder["folder_id"],
        "folder_name": folder["folder_name"]
    }

@app.get("/workspaces/{workspace_id}/folders")
async def get_folders(workspace_id: int, current_user=Depends(get_current_user)):
    folders = await db.get_folders_by_workspace(workspace_id)
    return {"folders": [dict(f) for f in folders]}