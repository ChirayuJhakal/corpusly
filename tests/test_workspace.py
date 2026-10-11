from fastapi.testclient import TestClient
import uuid


def test_fetch_documents_from_workspace(client: TestClient):
    response = client.post("/workspaces", json={"workspace_name": "test_workspace"})
    assert response.status_code == 200
    workspace_id = response.json()["workspace"]["workspace_id"]

    response = client.post(
        f"/workspaces/{workspace_id}/documents", json={"document_name": "test_document"}
    )
    assert response.status_code == 200
    document_id = response.json()["document"]["document_id"]

    wrong_worspace_id = str(uuid.uuid4())

    response = client.get(f"/workspaces/{workspace_id}/documents/{document_id}")
    assert response.status_code == 200

    response = client.get(f"/workspaces/{wrong_worspace_id}/documents/{document_id}")
    assert response.status_code == 404

    response = client.patch(
        f"/workspaces/{workspace_id}/documents/{document_id}",
        json={"document_name": "updated_document"},
    )
    assert response.status_code == 200

    response = client.patch(
        f"/workspaces/{wrong_worspace_id}/documents/{document_id}",
        json={"document_name": "updated_document"},
    )
    assert response.status_code == 404


def test_cross_tenant_workspace_patch(client: TestClient):
    workspace_a_name = "WorkspaceA"
    workspace_b_name = "WorkspaceB"
    response = client.post("/workspaces", json={"workspace_name": workspace_a_name})
    assert response.status_code == 200
    workspace_a_id = response.json()["workspace"]["workspace_id"]

    response = client.post("/workspaces", json={"workspace_name": workspace_b_name})
    assert response.status_code == 200
    workspace_b_id = response.json()["workspace"]["workspace_id"]

    document_a_name = "DocumentA"
    document_b_name = "DocumentB"
    response = client.post(f"/workspaces/{workspace_a_id}/documents", json={"document_name": document_a_name})
    assert response.status_code == 200
    document_a_id = response.json()["document"]["document_id"]

    response = client.post(f"/workspaces/{workspace_b_id}/documents", json={"document_name": document_b_name})
    assert response.status_code == 200
    document_b_id = response.json()["document"]["document_id"]

    response = client.get(f"/workspaces/{workspace_b_id}/documents/{document_a_id}")
    assert response.status_code == 404

    response = client.get(f"/workspaces/{workspace_a_id}/documents/{document_b_id}")
    assert response.status_code == 404

    response = client.patch(f"/workspaces/{workspace_a_id}/documents/{document_b_id}", json={"document_name": "UpdatedDocumentB"})
    assert response.status_code == 404
    response = client.get(f"/workspaces/{workspace_b_id}/documents/{document_b_id}")
    assert response.status_code == 200
    assert response.json()["document"]["document_name"] == document_b_name
