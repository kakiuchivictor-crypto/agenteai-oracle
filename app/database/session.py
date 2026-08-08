"""Engine e sessao de banco de dados (SQLModel sobre SQLAlchemy)."""

from __future__ import annotations

from collections.abc import Generator

from sqlmodel import Session, create_engine

from app.core.config import get_settings

settings = get_settings()

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, echo=False, connect_args=_connect_args)


def get_session() -> Generator[Session, None, None]:
    """Dependencia FastAPI: fornece uma sessao de banco de dados por requisicao."""
    with Session(engine) as session:
        yield session
