import os, uuid
from pathlib import Path
from fastapi import FastAPI
from .db import get_pool

app = FastAPI(title="Pas Oublie API", version="0.0.1")
app.include_rouer(ws_router)

@app.post("/auth/register")
async def register():

@app.post("/auth/login")
async def login():

@app.post("/files/upload")
async def upload():

@app.get("/files/{file_id}")
async def get_file():

@app.get("/search")
async def search():




