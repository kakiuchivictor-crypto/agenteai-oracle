"""Deteccao de quase-duplicatas por similaridade textual (secao 8 do prompt
mestre): fallback quando o hash exato nao bate, mas o conteudo e muito
semelhante (ex: mesma politica com uma frase alterada).

Usa `difflib` (biblioteca padrao) para evitar dependencia adicional apenas
para esta verificacao auxiliar.
"""

from __future__ import annotations

from difflib import SequenceMatcher

DEFAULT_SIMILARITY_THRESHOLD = 0.9


def text_similarity_ratio(text_a: str, text_b: str) -> float:
    if not text_a and not text_b:
        return 1.0
    return SequenceMatcher(None, text_a, text_b, autojunk=True).ratio()


def is_near_duplicate(
    text_a: str, text_b: str, threshold: float = DEFAULT_SIMILARITY_THRESHOLD
) -> bool:
    return text_similarity_ratio(text_a, text_b) >= threshold
