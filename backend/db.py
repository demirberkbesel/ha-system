from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

WRITE_DSN = os.getenv("WRITE_DSN", "postgresql://postgres:postgres@haproxy-db:5000/postgres")
READ_DSN = os.getenv("READ_DSN", "postgresql://postgres:postgres@haproxy-db:5001/postgres")

write_engine = create_engine(WRITE_DSN, pool_size=3, max_overflow=5, pool_pre_ping=True, connect_args={"connect_timeout": 1})
read_engine = create_engine(READ_DSN, pool_size=5, max_overflow=5, pool_pre_ping=True, connect_args={"connect_timeout": 1})

WriteSession = sessionmaker(bind=write_engine)
ReadSession = sessionmaker(bind=read_engine)

Base = declarative_base()


def init_db():
    Base.metadata.create_all(bind=write_engine)
