"""Interface comum para carregadores de documento (secao 4 do prompt mestre)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.schemas.document import ExtractedDocument


class DocumentLoader(ABC):
    """Cada formato suportado implementa esta interface.

    `supports` deve ser barato (checar extensao/assinatura), enquanto
    `load` realiza a extracao completa e retorna um `ExtractedDocument`
    padronizado, nunca lancando excecoes genericas — erros de dominio
    devem ser instancias de `app.core.exceptions.AppError`.
    """

    @abstractmethod
    def supports(self, file_path: Path) -> bool: ...

    @abstractmethod
    def load(self, file_path: Path) -> ExtractedDocument: ...
