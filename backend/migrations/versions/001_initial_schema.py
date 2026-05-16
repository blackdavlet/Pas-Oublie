"""initial_schema

Revision ID: 001
Revises: 
Create Date: 2026-05-15

"""
from alembic import op

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE user_role AS ENUM ('owner', 'editor', 'viewer');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id SERIAL PRIMARY KEY,
            username VARCHAR(255) NOT NULL UNIQUE,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS workspace (
            workspace_id SERIAL PRIMARY KEY,
            owner_id INTEGER NOT NULL,
            workspace_name VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS workspace_member (
            user_id INTEGER NOT NULL,
            workspace_id INTEGER NOT NULL,
            role user_role NOT NULL,
            PRIMARY KEY (user_id, workspace_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (workspace_id) REFERENCES workspace(workspace_id) ON DELETE CASCADE
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS folder (
            folder_id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            folder_name VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            workspace_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (workspace_id) REFERENCES workspace(workspace_id) ON DELETE CASCADE
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS file (
            file_id BIGINT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            filename VARCHAR(255) NOT NULL,
            folder_id INTEGER NOT NULL,
            workspace_id INTEGER,
            mime_type VARCHAR(127),
            storage_path VARCHAR(512) NOT NULL,
            size_bytes BIGINT DEFAULT 0,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (folder_id) REFERENCES folder(folder_id) ON DELETE CASCADE,
            FOREIGN KEY (workspace_id) REFERENCES workspace(workspace_id) ON DELETE CASCADE
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS file_embeddings (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            file_id BIGINT NOT NULL,
            embedding vector(1536),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (file_id) REFERENCES file(file_id) ON DELETE CASCADE
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_file_workspace
        ON file(workspace_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_file_folder
        ON file(folder_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_embeddings_file
        ON file_embeddings(file_id)
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_embeddings_file")
    op.execute("DROP INDEX IF EXISTS idx_file_folder")
    op.execute("DROP INDEX IF EXISTS idx_file_workspace")
    op.execute("DROP TABLE IF EXISTS file_embeddings")
    op.execute("DROP TABLE IF EXISTS file")
    op.execute("DROP TABLE IF EXISTS folder")
    op.execute("DROP TABLE IF EXISTS workspace_member")
    op.execute("DROP TABLE IF EXISTS workspace")
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TYPE IF EXISTS user_role")