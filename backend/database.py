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
    _migrate()
    _seed(SessionLocal())


def _migrate():
    """Add columns introduced after the initial schema to an existing SQLite DB.
    create_all() never alters existing tables, so we add them by hand."""
    from sqlalchemy import text

    new_columns = {
        "adventures": [("pending_roll", "JSON")],
        "prompt_config": [
            ("roll_enforcement", "BOOLEAN DEFAULT 1"),
            ("roll_rules_json", "JSON"),
        ],
    }
    with engine.begin() as conn:
        for table, cols in new_columns.items():
            existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            for name, decl in cols:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {decl}"))


def _seed(db):
    from models import AdventureTemplate, PromptConfig
    from templates_data import BUILTIN_TEMPLATES
    from roll_directive import DEFAULT_ROLL_RULES
    from llm import DEFAULT_SYSTEM_ADDENDUM, DEFAULT_TURN_REMINDER

    # Ensure prompt config row exists (seed sensible prompt defaults for new installs)
    cfg = db.get(PromptConfig, 1)
    if not cfg:
        db.add(PromptConfig(
            id=1,
            system_addendum=DEFAULT_SYSTEM_ADDENDUM,
            turn_reminder=DEFAULT_TURN_REMINDER,
            roll_enforcement=True, roll_rules_json=DEFAULT_ROLL_RULES,
        ))
        db.commit()
    elif not cfg.roll_rules_json:
        # Existing install upgrading in place — seed default rules once.
        cfg.roll_rules_json = DEFAULT_ROLL_RULES
        if cfg.roll_enforcement is None:
            cfg.roll_enforcement = True
        db.commit()

    # Seed built-in templates only if none exist yet
    if db.query(AdventureTemplate).filter_by(is_builtin=True).count() == 0:
        for t in BUILTIN_TEMPLATES:
            db.add(AdventureTemplate(is_builtin=True, **t))
        db.commit()

    db.close()
