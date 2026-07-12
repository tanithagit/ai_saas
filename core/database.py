from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,   # checks connection liveness before using it
    pool_recycle=3600,    # recycle connections every hour (avoids MySQL timeout drops)
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()