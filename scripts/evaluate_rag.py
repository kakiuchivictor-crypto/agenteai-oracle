"""Script de avaliacao do RAG (secao 34 do prompt mestre).

Ingere o pequeno conjunto de documentos ficticios de `tests/fixtures/documents/`,
executa cada pergunta de `tests/fixtures/rag_eval_dataset.json` atraves do
agente RAG completo (grafo real, recuperacao real) e classifica cada
resposta como correta, parcialmente correta, incorreta, sem evidencia ou
com fonte inadequada.

Uso:
    python scripts/evaluate_rag.py            # usa o provedor de LLM configurado no .env
    python scripts/evaluate_rag.py --fake     # smoke-test com respostas simuladas, sem LLM real

Roda em um banco de dados e indice vetorial temporarios — nunca escreve nos
diretorios de dados reais da aplicacao.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, SQLModel, create_engine  # noqa: E402

from app.agents.graph import build_agent_graph  # noqa: E402
from app.core.config import Settings, get_settings  # noqa: E402
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.database.models import Document  # noqa: E402
from app.database.models.enums import CurationStatus  # noqa: E402
from app.embeddings.base import BaseEmbeddingProvider  # noqa: E402
from app.embeddings.factory import build_embedding_provider  # noqa: E402
from app.ingestion.service import ingest_new_document  # noqa: E402
from app.llm.factory import build_chat_model  # noqa: E402
from app.reranking.factory import build_reranker  # noqa: E402
from app.vectorstores.chroma_repository import ChromaVectorRepository  # noqa: E402

logger = get_logger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "documents"
DATASET_PATH = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "rag_eval_dataset.json"

# Classificacoes possiveis, conforme exigido pela secao 34.
_CLASSIFICATIONS = ("correct", "partially_correct", "incorrect", "no_evidence", "wrong_source")


@dataclass
class EvaluationResult:
    question: str
    classification: str
    grounded: bool | None
    has_citation: bool
    expected_document: str | None
    cited_documents: list[str]
    latency_ms: int
    answer: str


def _classify(item: dict, answer: str, grounded: bool | None, cited_documents: list[str]) -> str:
    expected_document = item.get("expected_document")

    if expected_document is None:
        # Pergunta deliberadamente fora da base: o comportamento correto e
        # nao citar nenhuma fonte.
        return "correct" if not cited_documents else "incorrect"

    if not cited_documents:
        return "no_evidence"

    if expected_document not in cited_documents:
        return "wrong_source"

    keywords = item.get("expected_keywords", [])
    answer_lower = answer.lower()
    matched = [k for k in keywords if k.lower() in answer_lower]

    if not keywords:
        return "correct" if grounded else "partially_correct"
    if len(matched) == len(keywords) and grounded:
        return "correct"
    if matched:
        return "partially_correct"
    return "incorrect"


def _build_isolated_settings(tmp_dir: Path) -> Settings:
    """Copia as configuracoes reais (provedor de LLM/embeddings/reranker),
    mas isola caminhos de arquivo em um diretorio temporario — a avaliacao
    nunca deve escrever nos dados reais da aplicacao."""
    base_settings = get_settings()
    return base_settings.model_copy(
        update={
            "upload_dir": str(tmp_dir / "uploads"),
            "processed_dir": str(tmp_dir / "processed"),
            "vector_store_path": str(tmp_dir / "vector_store"),
            "log_dir": str(tmp_dir / "logs"),
        }
    )


def _build_chat_model(settings: Settings, use_fake_llm: bool):
    if use_fake_llm:
        from langchain_core.language_models.fake_chat_models import FakeListChatModel

        return FakeListChatModel(
            responses=["Resposta simulada para fins de teste do script. [Fonte 1]"] * 100
        )
    return build_chat_model(settings)


def _ingest_fixture_documents(
    session: Session, embedding_provider: BaseEmbeddingProvider,
    vector_repository: ChromaVectorRepository, settings: Settings,
) -> None:
    for path in sorted(FIXTURES_DIR.glob("sample_*")):
        result = ingest_new_document(
            original_filename=path.name, raw_bytes=path.read_bytes(), session=session,
            embedding_provider=embedding_provider, vector_repository=vector_repository,
            settings=settings,
        )
        if result.status == "success":
            document = session.get(Document, result.document_id)
            document.status = CurationStatus.APPROVED
            session.add(document)
            session.commit()
            logger.info("eval.document_ready", file=path.name, chunks=result.chunks_indexed)
        elif result.status != "duplicate":
            logger.warning("eval.document_failed", file=path.name, error=result.error)


def run_evaluation(*, use_fake_llm: bool) -> list[EvaluationResult]:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))

    # `ignore_cleanup_errors=True`: o Chroma mantem um handle aberto sobre o
    # arquivo do indice HNSW que o Windows nao libera a tempo da limpeza do
    # diretorio temporario (SQLite/mmap + coletor de lixo do Python nao
    # sincronizados) — sem essa flag, a limpeza levantaria PermissionError
    # mesmo com a avaliacao tendo rodado com sucesso.
    with tempfile.TemporaryDirectory(prefix="rag_eval_", ignore_cleanup_errors=True) as tmp:
        tmp_dir = Path(tmp)
        settings = _build_isolated_settings(tmp_dir)
        settings.ensure_runtime_directories()

        engine = create_engine(f"sqlite:///{tmp_dir / 'eval.db'}")
        SQLModel.metadata.create_all(engine)
        session = Session(engine)

        embedding_provider = build_embedding_provider(settings)
        vector_repository = ChromaVectorRepository(
            persist_path=settings.vector_store_path, collection_name="eval"
        )
        reranker = build_reranker(settings)
        chat_model = _build_chat_model(settings, use_fake_llm)

        _ingest_fixture_documents(session, embedding_provider, vector_repository, settings)

        graph = build_agent_graph(
            session=session, chat_model=chat_model, embedding_provider=embedding_provider,
            vector_repository=vector_repository, reranker=reranker, settings=settings,
        )

        results: list[EvaluationResult] = []
        for index, item in enumerate(dataset):
            start = time.perf_counter()
            final_state = graph.invoke(
                {
                    "session_id": f"eval-session-{index}",
                    "user_id": "eval-user",
                    "question": item["question"],
                    "chat_history": [],
                }
            )
            latency_ms = int((time.perf_counter() - start) * 1000)

            citations = final_state.get("citations") or []
            cited_documents = [c["document_name"] for c in citations]
            answer = final_state.get("answer", "")
            grounded = final_state.get("grounded")

            results.append(
                EvaluationResult(
                    question=item["question"],
                    classification=_classify(item, answer, grounded, cited_documents),
                    grounded=grounded,
                    has_citation=bool(citations),
                    expected_document=item.get("expected_document"),
                    cited_documents=cited_documents,
                    latency_ms=latency_ms,
                    answer=answer,
                )
            )

        session.close()

    return results


def print_summary(results: list[EvaluationResult]) -> None:
    total = len(results)
    if total == 0:
        print("Nenhuma pergunta no dataset de avaliacao.")
        return

    counts = {classification: 0 for classification in _CLASSIFICATIONS}
    for result in results:
        counts[result.classification] = counts.get(result.classification, 0) + 1

    grounded_count = sum(1 for r in results if r.grounded)
    citation_count = sum(1 for r in results if r.has_citation)
    avg_latency = sum(r.latency_ms for r in results) / total

    print("\n=== Avaliacao do RAG ===\n")
    for result in results:
        print(f"[{result.classification.upper():17}] {result.question}")
        print(
            f"   Fontes citadas: {result.cited_documents or '(nenhuma)'} | "
            f"Fundamentado: {result.grounded} | {result.latency_ms}ms"
        )

    print("\n--- Resumo ---")
    print(f"Total de perguntas: {total}")
    for classification in _CLASSIFICATIONS:
        count = counts[classification]
        print(f"  {classification}: {count} ({count / total:.0%})")
    print(f"Taxa de fundamentacao (grounded): {grounded_count}/{total} ({grounded_count / total:.0%})")
    print(f"Taxa de citacao: {citation_count}/{total} ({citation_count / total:.0%})")
    print(f"Latencia media por pergunta: {avg_latency:.0f}ms")
    print(
        "Tokens: nao instrumentado nesta versao (depende de metricas de uso do provedor "
        "de LLM configurado).\n"
        "Satisfacao: coletada em producao via POST /feedback; nao mensuravel em avaliacao "
        "sintetica sem usuarios reais."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Avalia a qualidade das respostas do RAG.")
    parser.add_argument(
        "--fake", action="store_true",
        help=(
            "Usa um modelo de chat simulado, sem LLM real — util para validar o "
            "funcionamento do script sem depender de um provedor configurado."
        ),
    )
    args = parser.parse_args()

    configure_logging()
    results = run_evaluation(use_fake_llm=args.fake)
    print_summary(results)


if __name__ == "__main__":
    main()
