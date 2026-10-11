import pytest
from fastapi.testclient import TestClient
from corpusly.main import app
from corpusly.repositories.documents import DocumentRepository
from corpusly.repositories.workspaces import WorkspaceRepository
import corpusly.dependencies as dependencies


@pytest.fixture
def client():
    _workspace_store_test = {}
    _document_store_test = {}
    app.dependency_overrides = {
        dependencies.get_workspace_repository: lambda: WorkspaceRepository(
            _workspace_store_test
        ),
        dependencies.get_document_repository: lambda: DocumentRepository(
            _document_store_test
        ),
    }
    yield TestClient(app)
    app.dependency_overrides.clear()
