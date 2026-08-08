"""Interface comum de provedores de embedding (secao 15 do prompt mestre).

O mesmo modelo deve ser usado para indexar documentos e transformar
perguntas — por isso a interface separa `embed_documents` (indexacao, em
lote) de `embed_query` (consulta, um texto por vez), permitindo que
implementacoes apliquem prefixos diferentes quando o modelo exigir
(ex: modelos da familia E5 usam "query: "/"passage: ").
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseEmbeddingProvider(ABC):
    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def embed_query(self, text: str) -> list[float]: ...

    @property
    @abstractmethod
    def dimension(self) -> int: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...
