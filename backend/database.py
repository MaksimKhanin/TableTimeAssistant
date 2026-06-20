from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DB_PATH = os.environ.get("DB_PATH", "dnd_game.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _seed(SessionLocal())


def _seed(db):
    from models import AdventureTemplate, PromptConfig
    from templates_data import BUILTIN_TEMPLATES

    # Ensure prompt config row exists
    if not db.get(PromptConfig, 1):
        db.add(PromptConfig(id=1, system_addendum="", turn_reminder=""))
        db.commit()

    # Seed built-in templates only if none exist yet
    if db.query(AdventureTemplate).filter_by(is_builtin=True).count() == 0:
        for t in BUILTIN_TEMPLATES:
            db.add(AdventureTemplate(is_builtin=True, **t))
        db.commit()

    db.close()
