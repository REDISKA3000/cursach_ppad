from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
    _ensure_mvp_columns()


def _ensure_mvp_columns():
    """Small SQLite-safe compatibility migration for the local MVP."""
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "users" not in table_names:
        return

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    statements = []
    if "email" not in user_columns:
        statements.append("ALTER TABLE users ADD COLUMN email VARCHAR(255)")
    if "password_hash" not in user_columns:
        statements.append("ALTER TABLE users ADD COLUMN password_hash VARCHAR(500)")
    if "updated_at" not in user_columns:
        statements.append("ALTER TABLE users ADD COLUMN updated_at DATETIME")

    if "resume_adaptations" in table_names:
        adaptation_columns = {column["name"] for column in inspector.get_columns("resume_adaptations")}
        if "vacancy_source_type" not in adaptation_columns:
            statements.append("ALTER TABLE resume_adaptations ADD COLUMN vacancy_source_type VARCHAR(50) DEFAULT 'text'")
        if "vacancy_source_url" not in adaptation_columns:
            statements.append("ALTER TABLE resume_adaptations ADD COLUMN vacancy_source_url VARCHAR(1000)")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
