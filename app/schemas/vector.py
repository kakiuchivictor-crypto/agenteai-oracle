"""Schemas de dominio para o banco vetorial (secao 16 do prompt mestre)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class VectorDocument(BaseModel):
    id: str
    text: str
    embedding: list[float]
    metadata: dict[str, Any]


class SearchResult(BaseModel):
    id: str
    text: str
    metadata: dict[str, Any]
    score: float  # similaridade (0-1, maior = mais relevante)
