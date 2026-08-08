"""Hashes para deduplicacao (secao 8 do prompt mestre).

`compute_file_hash` detecta duplicatas exatas do arquivo bruto (mesmo
conteudo binario, independente do nome). `compute_content_hash` detecta
duplicatas de conteudo apos normalizacao — util quando o mesmo documento e
reenviado com metadados de arquivo diferentes (ex: recompactado, exportado
novamente) mas o texto extraido e identico.
"""

from __future__ import annotations

import hashlib


def compute_file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def compute_content_hash(normalized_text: str) -> str:
    canonical = "\n".join(line.strip() for line in normalized_text.strip().splitlines())
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
