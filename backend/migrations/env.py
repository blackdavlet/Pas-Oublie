import os
from sqlalchemy import create_engine

def run_migrations_online():
    connectable = create_engine(os.environ["DATABASE_URL"])
    with connectable.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()