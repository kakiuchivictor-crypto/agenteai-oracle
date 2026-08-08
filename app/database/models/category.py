"""Categorias de negocio (secao 7 do prompt mestre)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlmodel import Field, SQLModel


class Category(SQLModel, table=True):
    __tablename__ = "categories"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    name: str = Field(index=True)
    slug: str = Field(index=True, unique=True)
    description: str | None = None
    parent_id: str | None = Field(default=None, foreign_key="categories.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Responsible(SQLModel, table=True):
    """Responsavel por documentos/categorias (secao 9). Nao precisa ser um
    usuario com login no sistema, apenas um contato corporativo rastreavel."""

    __tablename__ = "responsibles"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    name: str
    department: str | None = None
    email: str | None = None
    corporate_identifier: str | None = None
    last_reviewed_at: datetime | None = None
    next_review_due_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
