"""seed_data

Revision ID: 002
Revises: 001
Create Date: 2026-05-15

"""
from alembic import op

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        INSERT INTO users (username, email, password_hash)
        VALUES
            ('alice', 'alice@example.com', 'hashed_pw_1'),
            ('bob',   'bob@example.com',   'hashed_pw_2')
        ON CONFLICT DO NOTHING
    """)

    op.execute("""
        INSERT INTO workspace (workspace_name, owner_id)
        VALUES ('Team Alpha', 1)
        ON CONFLICT DO NOTHING
    """)

    op.execute("""
        INSERT INTO workspace_member (user_id, workspace_id, role)
        VALUES
            (1, 1, 'owner'),
            (2, 1, 'editor')
        ON CONFLICT DO NOTHING
    """)

    op.execute("""
        INSERT INTO folder (user_id, folder_name, workspace_id)
        VALUES
            (1, 'Documents', 1),
            (1, 'Media', 1)
        ON CONFLICT DO NOTHING
    """)


def downgrade():
    op.execute("DELETE FROM folder WHERE user_id = 1")
    op.execute(
        "DELETE FROM workspace_member WHERE workspace_id = 1"
    )
    op.execute("DELETE FROM workspace WHERE workspace_id = 1")
    op.execute(
        "DELETE FROM users WHERE username IN ('alice', 'bob')"
    )
