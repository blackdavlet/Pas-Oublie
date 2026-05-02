CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgvector;
CREATE TYPE user_role AS ENUM ('owner', 'editor', 'viewer');

CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS workspace (
    workspace_id SERIAL PRIMARY KEY,
    owner_id INTEGER NOT NULL,
    workspace_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workspace_member (
    user_id INTEGER NOT NULL,
    workspace_id INTEGER NOT NULL,
    role user_role NOT NULL,
    PRIMARY KEY (user_id, workspace_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id) REFERENCES workspace(workspace_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS folder (
    folder_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    folder_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    workspace_id INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id) REFERENCES workspace(workspace_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS file (
    file_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id INTEGER NOT NULL,
    filename VARCHAR(255) NOT NULL,
    folder_id INTEGER NOT NULL,
    mime_type VARCHAR(127),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    storage_path VARCHAR(512) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (folder_id) REFERENCES folder(folder_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS file_embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID NOT NULL,
    embedding vector(1536),  --vector data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES file(file_id) ON DELETE CASCADE
);


CREATE INDEX IF NOT EXISTS idx_file_workspace ON file(workspace_id);
CREATE INDEX IF NOT EXISTS idx_file_folder ON file(folder_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_file ON file_embeddings(file_id);
