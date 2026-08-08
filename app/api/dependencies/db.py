"""Dependencia FastAPI de sessao de banco de dados."""

from __future__ import annotations

from collections.abc import Generator

from sqlmodel import Session

from app.database.session import engine


def get_db_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
