from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DB_URL = "sqlite:///./school.db"

engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False},
    future=True,
)

# ВАЖНО: чтобы после commit не было DetachedInstanceError
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)

Base = declarative_base()
