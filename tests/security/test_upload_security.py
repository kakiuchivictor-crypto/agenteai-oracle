"""Testes de seguranca de upload de documentos (secao 29 do prompt mestre):
extensao/MIME, tamanho maximo e nomes de arquivo maliciosos."""

from __future__ import annotations


def test_rejects_disguised_executable_as_pdf(api_client) -> None:
    fake_pdf = b"MZ\x90\x00\x03\x00\x00\x00conteudo de executavel disfarcado"

    response = api_client.post(
        "/documents/upload", files={"file": ("relatorio.pdf", fake_pdf, "application/pdf")}
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "invalid_file"


def test_rejects_unsupported_extension(api_client) -> None:
    response = api_client.post(
        "/documents/upload",
        files={"file": ("script.exe", b"MZ\x90\x00conteudo", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "invalid_file"


def test_rejects_path_traversal_filename(api_client) -> None:
    response = api_client.post(
        "/documents/upload",
        files={"file": ("../../etc/passwd.md", b"# conteudo qualquer", "text/markdown")},
    )
    assert response.status_code == 400


def test_rejects_empty_file(api_client) -> None:
    response = api_client.post(
        "/documents/upload", files={"file": ("vazio.md", b"", "text/markdown")}
    )
    assert response.status_code == 400


def test_stored_filename_never_reuses_original_name(api_client, db_session, fixtures_dir) -> None:
    """O arquivo em disco deve usar um nome gerado (UUID), nunca o nome
    original enviado pelo usuario — evita colisoes e injecao via nome de
    arquivo (secao 29: "nome de arquivo seguro")."""
    content = (fixtures_dir / "sample_readme.md").read_bytes()

    response = api_client.post(
        "/documents/upload",
        files={"file": ("'; DROP TABLE documents; --.md", content, "text/markdown")},
    )
    assert response.status_code == 201

    from app.database.models import DocumentVersion

    version = db_session.get(DocumentVersion, response.json()["version_id"])
    assert "DROP TABLE" not in version.storage_path
    assert "'" not in version.storage_path


def test_filename_with_slash_is_rejected_as_unsafe(api_client, fixtures_dir) -> None:
    content = (fixtures_dir / "sample_readme.md").read_bytes()

    response = api_client.post(
        "/documents/upload",
        files={"file": ("<script>alert(1)</script>.md", content, "text/markdown")},
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "unsafe_file_path"
