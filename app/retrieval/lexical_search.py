"""Busca lexical (palavras-chave) via BM25 — segunda etapa da recuperacao
hibrida (secao 18 do prompt mestre).

Importante para numeros, codigos, nomes, identificadores, clausulas,
valores, datas e termos exatos que a busca puramente semantica pode nao
priorizar corretamente.

O indice BM25 e construido sob demanda a partir dos chunks armazenados no
SQLite. Para o volume de documentos previsto na primeira versao do projeto
isso e suficiente; um indice persistente (reconstruido apenas quando novos
chunks sao inseridos) e uma otimizacao natural caso o corpus cresca muito.
"""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi
from sqlmodel import Session, select

from app.database.models import DocumentChunk
from app.schemas.vector import SearchResult

_TOKEN_PATTERN = re.compile(r"[\wÀ-ÿ]+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.lower())


def lexical_search(query: str, *, session: Session, limit: int) -> list[SearchResult]:
    chunks = session.exec(select(DocumentChunk)).all()
    if not chunks:
        return []

    tokenized_corpus = [_tokenize(c.text) for c in chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(_tokenize(query))

    ranked = sorted(zip(chunks, scores, strict=True), key=lambda item: item[1], reverse=True)
    max_score = max((score for _, score in ranked), default=0.0) or 1.0

    results: list[SearchResult] = []
    for chunk_row, score in ranked[:limit]:
        if score <= 0:
            continue
        raw_metadata = {
            "document_id": chunk_row.document_id,
            "version_id": chunk_row.version_id,
            "page": chunk_row.page,
            "section": chunk_row.section,
            "slide": chunk_row.slide,
            "sheet_name": chunk_row.sheet_name,
            "row_number": chunk_row.row_number,
            "table_name": chunk_row.table_name,
        }
        results.append(
            SearchResult(
                id=chunk_row.vector_id,
                text=chunk_row.text,
                metadata={k: v for k, v in raw_metadata.items() if v is not None},
                score=score / max_score,
            )
        )
    return results
