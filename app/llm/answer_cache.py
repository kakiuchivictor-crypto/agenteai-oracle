"""Cache de respostas ja geradas (pergunta normalizada + contexto -> resposta).

Evita uma chamada inteira ao provedor de LLM quando a mesma pergunta e feita
de novo sobre o mesmo contexto ja recuperado. A chave inclui o texto do
CONTEXTO (nao so a pergunta): se o conteudo dos documentos mudar, a chave
muda junto e uma resposta desatualizada nunca e reaproveitada por engano.
"""

from __future__ import annotations

import hashlib

from sqlmodel import Session, select

from app.database.models import AnswerCache


def compute_cache_key(normalized_question: str, context_text: str) -> str:
    payload = f"{normalized_question.strip().lower()}\x1f{context_text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_cached_answer(session: Session, cache_key: str) -> AnswerCache | None:
    return session.exec(select(AnswerCache).where(AnswerCache.cache_key == cache_key)).first()


def store_answer(session: Session, *, cache_key: str, answer: str, route: str, model_used: str) -> None:
    session.add(AnswerCache(cache_key=cache_key, answer=answer, route=route, model_used=model_used))
