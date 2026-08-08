from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine

import app.database.models  # noqa: F401 - popula o metadata antes do create_all


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
