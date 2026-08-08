"""Hierarquia de excecoes da aplicacao.

Cada excecao carrega um `error_code` estavel (usado pela API para nao
vazar tracebacks ao usuario final, conforme secao 41 do prompt mestre) e uma
mensagem segura para exibicao direta ao usuario.
"""

from __future__ import annotations


class AppError(Exception):
    """Excecao base de todas as excecoes de dominio da aplicacao."""

    error_code: str = "internal_error"
    status_code: int = 500

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


# ==========================================================
# DOCUMENTOS E INGESTAO
# ==========================================================
class UnsupportedDocumentError(AppError):
    error_code = "unsupported_document_format"
    status_code = 415


class DocumentExtractionError(AppError):
    error_code = "document_extraction_failed"
    status_code = 422


class CorruptedFileError(AppError):
    error_code = "corrupted_file"
    status_code = 422


class EmptyDocumentError(AppError):
    error_code = "empty_document"
    status_code = 422


class PasswordProtectedDocumentError(AppError):
    error_code = "password_protected_document"
    status_code = 422


class OCRUnavailableError(AppError):
    error_code = "ocr_unavailable"
    status_code = 503


class DuplicateDocumentError(AppError):
    error_code = "duplicate_document"
    status_code = 409


class DocumentNotApprovedError(AppError):
    error_code = "document_not_approved"
    status_code = 403


class DocumentNotFoundError(AppError):
    error_code = "document_not_found"
    status_code = 404


class ResourceNotFoundError(AppError):
    error_code = "resource_not_found"
    status_code = 404


class InvalidCurationTransitionError(AppError):
    error_code = "invalid_curation_transition"
    status_code = 409


# ==========================================================
# SEGURANCA E ACESSO
# ==========================================================
class InvalidFileError(AppError):
    error_code = "invalid_file"
    status_code = 400


class FileTooLargeError(AppError):
    error_code = "file_too_large"
    status_code = 413


class UnsafeFilePathError(AppError):
    error_code = "unsafe_file_path"
    status_code = 400


class RateLimitExceededError(AppError):
    error_code = "rate_limit_exceeded"
    status_code = 429


# ==========================================================
# CONFIGURACAO E PROVEDORES
# ==========================================================
class MissingConfigurationError(AppError):
    error_code = "missing_configuration"
    status_code = 500


class ProviderUnavailableError(AppError):
    error_code = "provider_unavailable"
    status_code = 503


class EmbeddingGenerationError(AppError):
    error_code = "embedding_generation_failed"
    status_code = 502


class VectorStoreError(AppError):
    error_code = "vector_store_error"
    status_code = 502


class ReindexRequiredError(AppError):
    error_code = "reindex_required"
    status_code = 409


# ==========================================================
# CONSULTA / RAG
# ==========================================================
class InvalidQuestionError(AppError):
    error_code = "invalid_question"
    status_code = 400


class NoResultsFoundError(AppError):
    error_code = "no_results_found"
    status_code = 404


class RequestTimeoutError(AppError):
    error_code = "request_timeout"
    status_code = 504
