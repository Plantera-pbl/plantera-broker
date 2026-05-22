"""
SQLAlchemy database setup and session management.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import DATABASE_URL

# connect_args only needed for SQLite (allows multi-thread use)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables (called once at startup)."""
    from models import Reading, Device  # noqa: F401 — ensure models are registered
    Base.metadata.create_all(bind=engine)
    _migrate()


def _migrate():
    """Add new columns to existing tables without losing data."""
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    existing = {c["name"] for c in inspector.get_columns("devices")}
    with engine.begin() as conn:
        if "config" not in existing:
            conn.execute(text("ALTER TABLE devices ADD COLUMN config JSON"))
