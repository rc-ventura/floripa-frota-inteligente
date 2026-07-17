import os
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

DEFAULT_URL = 'sqlite:///db/frota.db'


def get_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_URL)


_engine = None

# singleton
def get_engine():
    global _engine
    if _engine is None:
        url = get_url()
        if url.startswith("sqlite:///"):
            p = Path(url.removeprefix("sqlite:///"))
            if str(p) != ":memory:":
                p.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(url, future=True)
        if _engine.dialect.name == "sqlite":
            # SQLite não aplica FKs por padrão 
            @event.listens_for(_engine, "connect")
            def _liga_fk(conexao, _registro):
                conexao.execute("PRAGMA foreign_keys=ON")
    return _engine


def reset_engine() -> None: # fixtures de testes
    global _engine
    _engine = None


def get_session(engine=None) -> Session:
    return Session(engine or get_engine())
