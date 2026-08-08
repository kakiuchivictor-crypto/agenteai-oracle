from __future__ import annotations

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.agents.nodes.generation import format_citations, make_generate_answer, verify_grounding
from app.core.config import Settings


def _settings(**overrides) -> Settings:
    # Desligado (0) por padrao para nao interferir com o limitador global de
    # chamadas ao LLM (ver `tests/conftest.py::test_settings`) — testes que
    # querem exercitar o limite passam um valor explicito via overrides.
    fields = {"llm_rate_limit_per_minute": 0, **overrides}
    return Settings(_env_file=None, **fields)


def test_generate_answer_returns_text_and_metadata(db_session) -> None:
    fake_model = FakeListChatModel(
        responses=["De acordo com a Politica de Reembolso, o prazo e de 7 dias."]
    )
    generate = make_generate_answer(fake_model, _settings(), db_session)

    result = generate(
        {
            "normalized_question": "Qual o prazo?",
            "context_text": "Documento: Politica de Reembolso\nO prazo e de 7 dias.",
            "chat_history": [],
        }
    )

    assert "7 dias" in result["answer"]
    assert result["route"] == "continue"
    assert result["latency_ms"] >= 0


def test_generate_answer_detects_conflict_marker(db_session) -> None:
    fake_model = FakeListChatModel(responses=["Encontrei informacoes divergentes entre as fontes."])
    generate = make_generate_answer(fake_model, _settings(), db_session)
    result = generate({"normalized_question": "q", "context_text": "ctx", "chat_history": []})
    assert result["route"] == "conflict"


def test_generate_answer_translates_provider_errors(db_session) -> None:
    class BrokenModel:
        def invoke(self, messages):
            raise ConnectionError("connection refused")

    generate = make_generate_answer(BrokenModel(), _settings(), db_session)
    result = generate({"normalized_question": "q", "context_text": "ctx", "chat_history": []})
    assert result["route"] == "provider_error"
    assert result["error"]


def test_generate_answer_returns_provider_busy_without_calling_model_when_rate_limited(
    db_session,
) -> None:
    """Regressao: sem essa checagem proativa, cada chamada (incluindo
    retries automaticos do cliente HTTP) batia direto no provedor mesmo com
    a cota por minuto ja esgotada."""

    class CountingModel:
        def __init__(self) -> None:
            self.calls = 0

        def invoke(self, messages):
            self.calls += 1
            if self.calls > 1:
                raise AssertionError("nao deveria ser chamado de novo com a cota ja esgotada")
            return FakeListChatModel(responses=["primeira resposta"]).invoke(messages)

    model = CountingModel()
    # Cache desligado de proposito: o objetivo aqui e testar o LIMITADOR por
    # minuto especificamente. Com o cache ligado, a 2a chamada (mesma
    # pergunta + mesmo contexto da 1a) seria resolvida pelo cache antes de
    # sequer chegar no limitador — o que e o comportamento certo em
    # producao, mas mascararia o que este teste quer verificar.
    generate = make_generate_answer(
        model, _settings(llm_rate_limit_per_minute=1, llm_answer_cache_enabled=False), db_session
    )
    state = {"normalized_question": "q", "context_text": "ctx", "chat_history": []}

    first = generate(state)
    assert first["route"] != "provider_busy"  # a 1a chamada consome a unica vaga
    assert model.calls == 1

    second = generate(state)
    assert second["route"] == "provider_busy"
    assert second["error"]
    assert model.calls == 1  # o modelo nao chegou a ser chamado de novo


def test_generate_answer_reuses_cached_answer_without_calling_model_again(db_session) -> None:
    class CountingModel:
        def __init__(self) -> None:
            self.calls = 0

        def invoke(self, messages):
            self.calls += 1
            if self.calls > 1:
                raise AssertionError("nao deveria ser chamado de novo - deveria vir do cache")
            return FakeListChatModel(responses=["resposta original"]).invoke(messages)

    model = CountingModel()
    generate = make_generate_answer(model, _settings(), db_session)
    state = {"normalized_question": "Qual o prazo?", "context_text": "ctx", "chat_history": []}

    first = generate(state)
    db_session.commit()
    assert first["answer"] == "resposta original"
    assert model.calls == 1

    second = generate(state)
    assert second["answer"] == "resposta original"
    assert second["route"] == first["route"]
    assert model.calls == 1  # veio do cache, nao chamou o modelo de novo


def test_generate_answer_cache_ignores_different_context(db_session) -> None:
    """A chave do cache inclui o CONTEXTO: se o conteudo recuperado mudar
    (ex: documento reindexado), a pergunta identica nao deve reaproveitar a
    resposta antiga."""
    fake_model = FakeListChatModel(responses=["resposta A", "resposta B"])
    generate = make_generate_answer(fake_model, _settings(), db_session)

    first = generate({"normalized_question": "q", "context_text": "contexto 1", "chat_history": []})
    db_session.commit()
    second = generate({"normalized_question": "q", "context_text": "contexto 2", "chat_history": []})

    assert first["answer"] == "resposta A"
    assert second["answer"] == "resposta B"


def test_generate_answer_returns_provider_busy_when_daily_limit_reached(db_session) -> None:
    class CountingModel:
        def __init__(self) -> None:
            self.calls = 0

        def invoke(self, messages):
            self.calls += 1
            return FakeListChatModel(responses=["resposta"]).invoke(messages)

    model = CountingModel()
    generate = make_generate_answer(
        model, _settings(llm_answer_cache_enabled=False, llm_daily_request_limit=1), db_session
    )

    first = generate({"normalized_question": "pergunta 1", "context_text": "ctx", "chat_history": []})
    db_session.commit()
    assert first["route"] != "provider_busy"
    assert model.calls == 1

    second = generate({"normalized_question": "pergunta 2", "context_text": "ctx", "chat_history": []})
    assert second["route"] == "provider_busy"
    assert "hoje" in second["error"].lower() or "amanhã" in second["error"].lower()
    assert model.calls == 1


def test_verify_grounding_true_when_answer_overlaps_context() -> None:
    result = verify_grounding(
        {
            "answer": "O prazo de reembolso e de 7 dias corridos apos a compra.",
            "context_text": "O prazo de reembolso e de 7 dias corridos apos a compra do produto.",
        }
    )
    assert result["grounded"] is True


def test_verify_grounding_false_when_no_evidence_phrase() -> None:
    result = verify_grounding(
        {"answer": "Nao encontrei informacoes suficientes.", "context_text": "algum contexto"}
    )
    assert result["grounded"] is False


def test_verify_grounding_false_when_answer_unrelated_to_context() -> None:
    result = verify_grounding(
        {
            "answer": "A capital da França é Paris e o clima está ótimo hoje.",
            "context_text": "Política de reembolso: prazo de sete dias corridos após a compra.",
        }
    )
    assert result["grounded"] is False


def test_format_citations_keeps_only_documents_named_in_the_answer() -> None:
    citations = [
        {"label": "Fonte 1", "document_id": "d1", "document_name": "Politica de Ferias"},
        {"label": "Fonte 2", "document_id": "d2", "document_name": "Manual do Colaborador"},
    ]
    result = format_citations(
        {"answer": "Conforme o Manual do Colaborador, o prazo e de 30 dias.", "citations": citations}
    )
    assert [c["document_name"] for c in result["citations"]] == ["Manual do Colaborador"]


def test_format_citations_falls_back_to_all_when_no_document_name_matches() -> None:
    citations = [{"label": "Fonte 1", "document_id": "d1", "document_name": "Politica de Ferias"}]
    result = format_citations(
        {"answer": "Resposta parafraseada sem citar o documento pelo nome.", "citations": citations}
    )
    assert result["citations"] == citations
