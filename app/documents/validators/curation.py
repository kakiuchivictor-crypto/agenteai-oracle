"""Maquina de estados da curadoria de documentos (secao 8 do prompt mestre).

Somente documentos `APPROVED` sao usados nas respostas por padrao (aplicado
na camada de recuperacao, Fase 4). Este modulo apenas garante que as
transicoes de status feitas pelo curador/administrador sejam coerentes.
"""

from __future__ import annotations

from app.core.exceptions import InvalidCurationTransitionError
from app.database.models.enums import CurationStatus

ALLOWED_TRANSITIONS: dict[CurationStatus, set[CurationStatus]] = {
    CurationStatus.PENDING_REVIEW: {
        CurationStatus.APPROVED,
        CurationStatus.REJECTED,
        CurationStatus.DUPLICATE,
        CurationStatus.ARCHIVED,
    },
    CurationStatus.APPROVED: {
        CurationStatus.OUTDATED,
        CurationStatus.REPLACED,
        CurationStatus.ARCHIVED,
        CurationStatus.REJECTED,
        CurationStatus.DUPLICATE,
    },
    CurationStatus.REJECTED: {CurationStatus.PENDING_REVIEW, CurationStatus.ARCHIVED},
    CurationStatus.OUTDATED: {
        CurationStatus.REPLACED,
        CurationStatus.ARCHIVED,
        CurationStatus.APPROVED,
    },
    CurationStatus.REPLACED: {CurationStatus.ARCHIVED},
    CurationStatus.ARCHIVED: {CurationStatus.PENDING_REVIEW},
    CurationStatus.DUPLICATE: {CurationStatus.ARCHIVED, CurationStatus.PENDING_REVIEW},
}


def validate_transition(current: CurationStatus, new: CurationStatus) -> None:
    if current == new:
        return
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if new not in allowed:
        raise InvalidCurationTransitionError(
            f"Transicao de status invalida: '{current.value}' -> '{new.value}'."
        )
