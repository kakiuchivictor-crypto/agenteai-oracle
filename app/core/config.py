"""Configuracao central da aplicacao, carregada exclusivamente do .env."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"
    GEMINI = "gemini"


class EmbeddingProvider(StrEnum):
    SENTENCE_TRANSFORMERS = "sentence_transformers"
    OPENAI = "openai"
    OLLAMA = "ollama"


class RerankerProvider(StrEnum):
    CROSS_ENCODER = "cross_encoder"
    HEURISTIC = "heuristic"


class VectorStoreProvider(StrEnum):
    CHROMA = "chroma"


class FusionStrategy(StrEnum):
    RRF = "rrf"
    WEIGHTED = "weighted"


class Settings(BaseSettings):
    """Configuracoes tipadas da aplicacao.

    Uma instrucao explicita do prompt mestre exige informar claramente quando
    uma configuracao obrigatoria estiver ausente: a validacao abaixo falha
    cedo (na inicializacao) em vez de deixar o erro estourar em tempo de uso.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Aplicacao ---
    app_name: str = "AxysAI - Respostas para suas dúvidas"
    app_env: str = "development"
    app_debug: bool = True
    app_secret_key: str = "changeme"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:8501,http://localhost:8000"

    # --- Banco de dados ---
    database_url: str = "sqlite:///./data/app.db"

    # --- LLM ---
    # Padrao de classe continua Ollama (nao exige credencial) para que
    # `Settings()` sem `.env` siga construivel em testes. O `.env` real do
    # projeto sobrescreve para `gemini` — ver LLM_PROVIDER no .env/.env.example.
    llm_provider: LLMProvider = LLMProvider.OLLAMA
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "llama3.1"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 500
    # 180s (nao 60s): em CPU, a primeira chamada apos o modelo ser
    # descarregado da memoria (~5GB, formato gguf) pode levar mais de 60s so
    # para carregar do disco, antes de gerar um token sequer. Um timeout
    # curto demais corta a conexao antes da carga terminar — e o Ollama
    # aborta o carregamento junto quando o cliente desconecta, entao o
    # modelo nunca fica "quente" e toda chamada seguinte tambem falha.
    llm_timeout_seconds: int = 180
    # Quantas vezes o cliente HTTP tenta de novo sozinho antes de desistir
    # (erros transitorios: timeout, 5xx, 429). O padrao das bibliotecas
    # cliente costuma ser generoso (a do Gemini, por exemplo, tenta 6 vezes
    # com backoff exponencial) — bom para uma falha de rede pontual, ruim
    # quando o motivo e cota por minuto esgotada: cada retry e mais uma
    # chamada contra a MESMA janela ja estourada, entao a tentativa demora
    # dezenas de segundos so para falhar de qualquer jeito. Um numero baixo
    # aqui, combinado com `llm_rate_limit_per_minute` (que evita nem tentar
    # quando ja sabemos que vamos estourar a cota), falha rapido no caso
    # comum sem perder a resiliencia a falhas de rede de fato transitorias.
    llm_max_retries: int = 2
    # Quanto tempo o Ollama mantem o modelo carregado na memoria apos o
    # ultimo uso, antes de descarrega-lo (formato aceito pelo Ollama: "5m",
    # "30m", "1h", "-1" para nunca descarregar, ou segundos). Recarregar um
    # modelo do zero em CPU pode levar mais de 1 minuto — manter aquecido
    # durante uma sessao de uso e a maior alavanca de velocidade disponivel
    # sem trocar de modelo.
    ollama_keep_alive: str = "30m"
    # Limite global (nao por usuario) de chamadas ao provedor de LLM por
    # minuto — protege a cota real do provedor (ex: Gemini free tier, ~15
    # req/min compartilhada pelo projeto inteiro), nao o servidor local.
    # Fixado um pouco abaixo da cota real de proposito: sobra margem para
    # que o modo de conhecimento geral e retries pontuais nao estourem o
    # limite do provedor mesmo com poucas pessoas testando ao mesmo tempo.
    # 0 desliga o limite (sem protecao — nao recomendado com Gemini free tier).
    llm_rate_limit_per_minute: int = 12
    # Reaproveita a resposta ja gerada quando a MESMA pergunta (normalizada)
    # e feita de novo sobre o MESMO contexto recuperado — pula a chamada ao
    # provedor por completo (nao gasta cota nenhuma). Seguro por padrao: a
    # chave do cache inclui o texto do contexto, entao uma mudanca real nos
    # documentos (nova versao, reindexacao) muda a chave e invalida o cache
    # automaticamente, sem precisar de expiracao manual.
    llm_answer_cache_enabled: bool = True
    # Teto diario (nao por minuto) de chamadas ao provedor, persistido no
    # banco para sobreviver a reinicios do processo. O plano gratuito do
    # Gemini tambem tem um limite de requisicoes POR DIA, alem do limite por
    # minuto acima — sem essa guarda, o sistema pode funcionar a manha
    # inteira e travar de vez a tarde sem aviso. Desligado (0) por padrao
    # porque o numero exato varia por modelo/conta: confira o seu em
    # https://aistudio.google.com/apikey (pagina de cota) antes de ativar.
    llm_daily_request_limit: int = 0

    # --- Embeddings ---
    embedding_provider: EmbeddingProvider = EmbeddingProvider.SENTENCE_TRANSFORMERS
    embedding_model: str = "intfloat/multilingual-e5-base"
    embedding_dimension: int = 768

    # --- Reranking ---
    reranker_provider: RerankerProvider = RerankerProvider.CROSS_ENCODER
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    retrieval_candidates: int = 20
    rerank_top_k: int = 3
    # Score minimo (0-1, apos o reranking) para um resultado ser considerado
    # evidencia de verdade. A busca vetorial sempre devolve os "vizinhos mais
    # proximos" mesmo quando nada e realmente relevante (ex: perguntar sobre
    # um assunto fora da base ainda retorna os documentos mais parecidos, so
    # que fracamente) — sem esse corte, esses vizinhos fracos virariam
    # CONTEXTO e o agente tentaria responder no modo documento (estrito) em
    # vez de cair no modo conhecimento geral do SYSTEM_PROMPT.
    rerank_min_score: float = 0.3

    # --- Banco vetorial ---
    vector_store_provider: VectorStoreProvider = VectorStoreProvider.CHROMA
    vector_store_path: str = "./data/vector_store"
    vector_store_collection: str = "documents"

    # --- Chunking ---
    chunk_size: int = 800
    chunk_overlap: int = 150
    max_chunk_size: int = 1200

    # --- Busca hibrida ---
    hybrid_search_enabled: bool = True
    hybrid_fusion_strategy: FusionStrategy = FusionStrategy.RRF
    hybrid_rrf_k: int = 60

    # --- Ingestao ---
    upload_dir: str = "./data/uploads"
    processed_dir: str = "./data/processed"
    max_upload_size_mb: int = 50
    allowed_extensions: str = ".pdf,.docx,.xlsx,.pptx,.md,.csv,.json,.html,.htm"
    watched_folder_path: str = ""
    watched_folder_enabled: bool = False

    # --- OCR ---
    ocr_enabled: bool = True
    ocr_language: str = "por+eng"
    tesseract_cmd: str = ""

    # --- Logging ---
    log_level: str = "INFO"
    log_format: str = "json"
    log_dir: str = "./data/logs"

    # --- Rate limiting ---
    rate_limit_per_minute: int = 300

    # --- Agente RAG ---
    max_context_chars: int = 3000
    max_chat_history_turns: int = 6

    # --- Curadoria ---
    # Quando ativo, um documento e aprovado automaticamente assim que o
    # processamento (extracao/chunking/indexacao) termina com sucesso —
    # continua passando pela mesma maquina de estados e trilha de auditoria
    # da aprovacao manual (secao 8 e 29), so que sem exigir o clique. Padrao
    # ligado: o sistema nao tem login/administrador dedicado para ficar
    # aprovando documentos manualmente — a pagina de Curadoria continua
    # disponivel para quem quiser revisar/rejeitar algo manualmente, mas
    # ninguem e obrigado a usa-la. Desligue explicitamente se quiser exigir
    # revisao manual antes de um documento ficar disponivel no chat.
    auto_approve_on_upload: bool = True

    @field_validator("cors_origins", "allowed_extensions")
    @classmethod
    def _strip_csv(cls, value: str) -> str:
        return value.strip()

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_extensions_list(self) -> list[str]:
        return [ext.strip().lower() for ext in self.allowed_extensions.split(",") if ext.strip()]

    @model_validator(mode="after")
    def _validate_required_credentials(self) -> "Settings":
        missing: list[str] = []

        if self.llm_provider == LLMProvider.ANTHROPIC and not self.anthropic_api_key:
            missing.append("ANTHROPIC_API_KEY (obrigatorio quando LLM_PROVIDER=anthropic)")
        if self.llm_provider == LLMProvider.OPENAI and not self.openai_api_key:
            missing.append("OPENAI_API_KEY (obrigatorio quando LLM_PROVIDER=openai)")
        if self.llm_provider == LLMProvider.GEMINI and not self.gemini_api_key:
            missing.append("GEMINI_API_KEY (obrigatorio quando LLM_PROVIDER=gemini)")
        if self.embedding_provider == EmbeddingProvider.OPENAI and not self.openai_api_key:
            missing.append("OPENAI_API_KEY (obrigatorio quando EMBEDDING_PROVIDER=openai)")

        if self.app_secret_key == "changeme" and self.app_env != "development":  # noqa: S105
            missing.append("APP_SECRET_KEY (nao pode usar o valor padrao fora de development)")

        if missing:
            raise ValueError(
                "Configuracao obrigatoria ausente ou invalida no .env:\n- "
                + "\n- ".join(missing)
            )
        return self

    def ensure_runtime_directories(self) -> None:
        """Cria os diretorios de dados necessarios caso ainda nao existam."""
        for directory in (
            self.upload_dir,
            self.processed_dir,
            self.vector_store_path,
            self.log_dir,
        ):
            Path(directory).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Retorna a instancia unica (cacheada) de configuracoes da aplicacao."""
    return Settings()
