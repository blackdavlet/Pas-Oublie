# backend/app/db.py
import os
import asyncpg
from passlib.hash import bcrypt


_pool = None

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            os.environ["DATABASE_URL"],
            min_size=1, max_size=10
        )
    return _pool #queue function -- pool

async def create_user(username: str, email: str, password: str):
    pool = await get_pool()
    password_hash = bcrypt.hash(password)
    async with pool.acquire() as con:
        try: 
            row = await con.fetchrow(
                """INSERT INTO users (username, email, password_hash)
                   VALUES ($1, $2, $3)
                   RETURNING user_id, username, email                      #------------NEW-USER
                   """,
                   username, email, password_hash
            )
            return row
        except asyncpg.UniqueViolationError:
            return None


async def create_workspace(workspace_name: str, owner_id: int):
    pool = await get_pool()
    async with pool.acquire() as con:
        async with con.transaction():
            workspace = await con.fetchrow(
                """INSERT INTO workspace (workspace_name)                  #------------NEW-WORKSPACE
                   VALUES ($1)
                   RETURNING workspace_id, workspace_name, created_at
                   """,
                   workspace_name
            )

            await con.execute(
                """INSERT INTO workspace_member (user_id, workspace_id, role)
                    VALUESV ($1, $2, 'owner')
                    """,
                    owner_id, workspace["workspace_id"]
                    
            )
            return workspace
        

async def create_file(user_id: int, filename: str, folder_id: int, workspace_id: int, mime: str):
    pool = await get_pool()
    async with pool.acquire() as con:
        return await con.fetchrow(
            """INSERT INTO file (user_id, filename, folder_id, workspace_id, mime)      #------------NEW-FILE
                VALUES (1$, 2$, 3$, 4$, 5$)
                RETURNING file_id, filename, uploaded_at
                """,
                user_id, filename, folder_id, workspace_id, mime
        )
    

async def add_workspace_member(user_id: int, workspace_id: int, role: str):
    pool = await get_pool()
    async with pool.acquire() as con:
        try:
            await con.execute(
                """INSERT INTO workspace_member (user_id, workspace_id, role)           #------------NEW-WORKSPACE-MEMBER
                    VALUES ($1, $2, $3)                                     
                    """,
                    user_id, workspace_id, role
            )
            return True
        except asyncpg.UniqueViolationError:
            return False

#--------GET-FUMCTIONS
async def get_user_by_id(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as con:
        return await con.fetchrow(
            "SELECT user_id, username, email FROM users WHERE user_id = $1",
            user_id
        )


async def get_workspace_by_id(workspace_id: int):
    pool = await get_pool()
    async with pool.acquire() as con:
        return await con.fetchrow(
            "SELECT * FROM workspace WHERE workspace_id = $1",
            workspace_id
        )
    
    
async def get_file_by_id(file_id: str):
    pool = await get_pool()
    async with pool.acquire() as con:
        return await con.fetchrow(
            "SELECT * FROM file WHERE file_id = $1",
            file_id
        )
    




    
async def delete_file(file_id: str):
    pool = await get_pool()
    async with pool.acquire() as con:
        return await con.fetchrow(
            "DELETE FROM file WHERE file_id = $1",
            file_id
        )
    






#   NO FOLDERS YET AND SOME OF GET FUNCTIONS