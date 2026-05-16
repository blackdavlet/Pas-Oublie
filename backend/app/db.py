# backend/app/db.py
import os
import asyncpg
from passlib.hash import bcrypt
from app.snowflake import generate_id


_pool = None

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            os.environ["DATABASE_URL"],
            min_size=1, max_size=10
        )
    return _pool #queue function -- pool

async def create_user(username: str, email: str, password: str):                 #------------NEW-USER
    pool = await get_pool()
    password_hash = bcrypt.hash(password)
    async with pool.acquire() as con:
        try: 
            row = await con.fetchrow(
                """INSERT INTO users (username, email, password_hash)
                   VALUES ($1, $2, $3)
                   RETURNING user_id, username, email                      
                   """,
                   username, email, password_hash
            )
            return row
        except asyncpg.UniqueViolationError:
            return None


async def create_workspace(workspace_name: str, owner_id: int):
    pool = await get_pool()
    async with pool.acquire() as con:                                          #------------NEW-WORKSPACE
        async with con.transaction():
            workspace = await con.fetchrow(
                """INSERT INTO workspace (workspace_name, owner_id)                  
                   VALUES ($1, $2)
                   RETURNING workspace_id, workspace_name, created_at
                   """,
                   workspace_name, owner_id
            )

            await con.execute(
                """INSERT INTO workspace_member (user_id, workspace_id, role)
                    VALUES ($1, $2, 'owner')
                    """,
                    owner_id, workspace["workspace_id"]
                    
            )
            return workspace
        

async def create_file(user_id: int, filename: str, folder_id: int, workspace_id: int, mime_type: str, storage_path: str, size_bytes: int):
    pool = await get_pool()
    file_id = generate_id()
    async with pool.acquire() as con:
        return await con.fetchrow(
            """
            INSERT INTO file (file_id, user_id, filename, folder_id, workspace_id, mime_type, size_bytes, storage_path)      
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING file_id, filename, uploaded_at
            """,
                file_id, user_id, filename, folder_id, workspace_id, mime_type, size_bytes, storage_path                  #------------NEW-FILE
        )
    

async def add_workspace_member(user_id: int, workspace_id: int, role: str):
    pool = await get_pool()
    async with pool.acquire() as con:                                                           #------------NEW-WORKSPACE-MEMBER
        try:                
            await con.execute(
                """INSERT INTO workspace_member (user_id, workspace_id, role)           
                    VALUES ($1, $2, $3)                                     
                    """,
                    user_id, workspace_id, role
            )
            return True
        except asyncpg.UniqueViolationError:
            return False
        

async def create_folder(user_id: int, folder_name: str, workspace_id: int):                  #------------NEW-FOLDER
    pool = await get_pool()
    async with pool.acquire() as con:
        return await con.fetchrow(
            """
            INSERT INTO folder (user_id, folder_name, workspace_id)                     
            VALUES ($1, $2, $3)
            RETURNING folder_id, folder_name, created_at
            """,
            user_id, folder_name, workspace_id
        )

#--------GET-FUMCTIONS
async def get_user_by_id(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as con:
        return await con.fetchrow(
            "SELECT user_id, username, email FROM users WHERE user_id = $1",
            user_id
        )
    
async def get_user_workspaces(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as con:
        return await con.fetch(
            """
            SELECT w.workspace_id, w.workspace_name, w.created_at, wm.role
            FROM workspace w
            JOIN workspace_member wm ON w.workspace_id = wm.workspace_id
            WHERE wm.user_id = $1
            """,
            user_id
        )


async def get_workspace_by_id(workspace_id: int):
    pool = await get_pool()
    async with pool.acquire() as con:
        return await con.fetchrow(
            "SELECT * FROM workspace WHERE workspace_id = $1",
            workspace_id
        )


async def get_user_by_email(email: str):
    pool = await get_pool()
    async with pool.acquire() as con:
        return await con.fetchrow(
            "SELECT * FROM users WHERE email = $1",
            email
        )
    
    
async def get_file_by_id(file_id: str):
    pool = await get_pool()
    async with pool.acquire() as con:
        return await con.fetchrow(
            "SELECT * FROM file WHERE file_id = $1",
            file_id
        )


async def get_files_by_folder(folder_id: int):
    pool = await get_pool()
    async with pool.acquire() as con:
        return await con.fetch(
            """
            SELECT f.file_id, f.filename, f.uploaded_at,
                   f.mime_type, u.username as uploaded_by
            FROM file f
            JOIN users u ON f.user_id = u.user_id
            WHERE f.folder_id = $1
            ORDER BY f.uploaded_at DESC
            """,
            folder_id
        )
    
async def get_folders_by_workspace(workspace_id: int):
    pool = await get_pool()
    async with pool.acquire() as con:
        return await con.fetch(
            "SELECT folder_id, folder_name, created_at FROM folder WHERE workspace_id = $1 ORDER BY created_at",
            workspace_id
        )
        
async def delete_file(file_id: str):
    pool = await get_pool()
    async with pool.acquire() as con:
        return await con.fetchrow(
            "DELETE FROM file WHERE file_id = $1",
            file_id
        )
    

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.verify(plain, hashed)


