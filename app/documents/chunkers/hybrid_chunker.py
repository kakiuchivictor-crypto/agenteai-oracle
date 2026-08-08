"""Chunking hibrido (secao 13 do prompt mestre).

Prioridade de agrupamento: unidades estruturais atomicas (linha de
planilha/CSV, slide, tabela, campo JSON) nunca sao mescladas com vizinhas —
cada uma vira seu proprio chunk. Unidades de prosa (paragrafos/titulos de
Word, Markdown, HTML, paginas de PDF) sao agrupadas sequencialmente
enquanto pertencerem ao mesmo contexto (mesma secao/titulo ou mesma pagina)
e couberem em `chunk_size`. Divisao por tamanho de caractere e usada apenas
como ultimo recurso, quando uma unidade (ou grupo) excede `max_chunk_size`.
"""

from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.documents.cleaners.document_cleaner import CleanedSection
from app.schemas.chunk import Chunk

_GroupKey = tuple[str, object]


def _is_atomic(section: CleanedSection) -> bool:
    return (
        section.row_number is not None
        or section.slide is not None
        or section.table_name is not None
        or section.json_path is not None
    )


def _grouping_key(section: CleanedSection) -> _GroupKey:
    if section.section:
        return ("section", section.section)
    if section.page is not None:
        return ("page", section.page)
    return ("none", None)


def _build_chunk(text: str, anchor: CleanedSection) -> Chunk:
    return Chunk(
        chunk_index=0,  # reindexado no final
        text=text,
        char_count=len(text),
        page=anchor.page,
        section=anchor.section,
        slide=anchor.slide,
        sheet_name=anchor.sheet_name,
        row_number=anchor.row_number,
        table_name=anchor.table_name,
        json_path=anchor.json_path,
        is_ocr=anchor.is_ocr,
    )


def _split_oversized(
    text: str, chunk_size: int, chunk_overlap: int, max_chunk_size: int
) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=min(chunk_overlap, chunk_size // 2 or 1),
        length_function=len,
        separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""],
    )
    pieces = [p for p in splitter.split_text(text) if p.strip()]
    # Garantia adicional do teto rigido (RecursiveCharacterTextSplitter usa
    # chunk_size como alvo, nao como limite absoluto em casos extremos).
    hard_capped: list[str] = []
    for piece in pieces:
        while len(piece) > max_chunk_size:
            hard_capped.append(piece[:max_chunk_size])
            piece = piece[max(0, max_chunk_size - chunk_overlap) :]
        hard_capped.append(piece)
    return hard_capped or [text[:max_chunk_size]]


def chunk_sections(
    sections: list[CleanedSection],
    *,
    chunk_size: int,
    chunk_overlap: int,
    max_chunk_size: int,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    buffer: list[CleanedSection] = []

    def flush() -> None:
        if not buffer:
            return
        combined_text = "\n\n".join(s.normalized_text for s in buffer).strip()
        anchor = buffer[0]
        if len(combined_text) > max_chunk_size:
            for piece in _split_oversized(combined_text, chunk_size, chunk_overlap, max_chunk_size):
                chunks.append(_build_chunk(piece, anchor))
        else:
            chunks.append(_build_chunk(combined_text, anchor))
        buffer.clear()

    for section in sections:
        if not section.normalized_text.strip():
            continue

        if _is_atomic(section):
            flush()
            text = section.normalized_text
            if len(text) > max_chunk_size:
                for piece in _split_oversized(text, chunk_size, chunk_overlap, max_chunk_size):
                    chunks.append(_build_chunk(piece, section))
            else:
                chunks.append(_build_chunk(text, section))
            continue

        if buffer and _grouping_key(buffer[0]) != _grouping_key(section):
            flush()

        prospective_length = (
            sum(len(s.normalized_text) for s in buffer)
            + len(section.normalized_text)
            + 2 * len(buffer)
        )
        if buffer and prospective_length > chunk_size:
            flush()

        buffer.append(section)

    flush()

    for index, chunk in enumerate(chunks):
        chunk.chunk_index = index

    return chunks
