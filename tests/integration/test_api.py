from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_check_responds_ok(api_client: TestClient) -> None:
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_endpoints_do_not_require_authentication(api_client: TestClient) -> None:
    """O sistema e de uso livre (sem login) — endpoints que antes exigiam
    token agora respondem diretamente, sem 401/403."""
    response = api_client.get("/categories")
    assert response.status_code == 200


def test_anyone_can_create_category(api_client: TestClient) -> None:
    response = api_client.post("/categories", json={"name": "Financeiro", "slug": "financeiro"})
    assert response.status_code == 201
    assert response.json()["slug"] == "financeiro"

    listed = api_client.get("/categories")
    assert listed.status_code == 200
    assert any(c["slug"] == "financeiro" for c in listed.json())


def test_document_upload_process_and_approve_flow(api_client: TestClient, fixtures_dir) -> None:
    content = (fixtures_dir / "sample_policy.pdf").read_bytes()

    upload_response = api_client.post(
        "/documents/upload", files={"file": ("sample_policy.pdf", content, "application/pdf")}
    )
    assert upload_response.status_code == 201, upload_response.text
    upload_data = upload_response.json()
    assert upload_data["status"] == "registered"
    document_id = upload_data["document_id"]

    get_response = api_client.get(f"/documents/{document_id}")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "pending_review"

    process_response = api_client.post(f"/documents/{document_id}/process")
    assert process_response.status_code == 200, process_response.text
    process_data = process_response.json()
    assert process_data["status"] == "success"
    assert process_data["chunks_indexed"] > 0

    approve_response = api_client.post(f"/documents/{document_id}/approve")
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"

    listed = api_client.get("/documents")
    assert any(d["id"] == document_id for d in listed.json())


def test_get_unknown_document_returns_404(api_client: TestClient) -> None:
    response = api_client.get("/documents/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error_code"] == "document_not_found"


def test_delete_document_archives_it(api_client: TestClient, fixtures_dir) -> None:
    content = (fixtures_dir / "sample_readme.md").read_bytes()
    upload = api_client.post(
        "/documents/upload", files={"file": ("sample_readme.md", content, "text/markdown")}
    )
    document_id = upload.json()["document_id"]

    delete_response = api_client.delete(f"/documents/{document_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "archived"


def test_chat_end_to_end_with_feedback(api_client: TestClient, fixtures_dir) -> None:
    content = (fixtures_dir / "sample_policy.pdf").read_bytes()
    upload = api_client.post(
        "/documents/upload", files={"file": ("sample_policy.pdf", content, "application/pdf")}
    )
    document_id = upload.json()["document_id"]
    api_client.post(f"/documents/{document_id}/process")
    api_client.post(f"/documents/{document_id}/approve")

    chat_response = api_client.post("/chat", json={"question": "Qual o prazo de reembolso?"})
    assert chat_response.status_code == 200, chat_response.text
    chat_data = chat_response.json()
    assert chat_data["session_id"]
    assert chat_data["answer"]

    sessions = api_client.get("/chat/sessions")
    assert sessions.status_code == 200
    assert len(sessions.json()) >= 1

    messages = api_client.get(f"/chat/sessions/{chat_data['session_id']}/messages")
    assert messages.status_code == 200
    assistant_messages = [m for m in messages.json() if m["role"] == "assistant"]
    assert len(assistant_messages) == 1

    feedback_response = api_client.post(
        "/feedback", json={"message_id": assistant_messages[0]["id"], "rating": "positive"}
    )
    assert feedback_response.status_code == 201

    feedback_list = api_client.get("/feedback")
    assert feedback_list.status_code == 200
    assert len(feedback_list.json()) == 1


def test_metrics_summary(api_client: TestClient) -> None:
    response = api_client.get("/metrics/summary")
    assert response.status_code == 200
    assert "total_documents" in response.json()
