"""Schemas da API de categorias (secao 7 do prompt mestre)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CategoryCreateRequest(BaseModel):
    name: str
    slug: str
    description: str | None = None
    parent_id: str | None = None


class CategoryResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None
    parent_id: str | None
    created_at: datetime
