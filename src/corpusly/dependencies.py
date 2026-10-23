from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from psycopg import Connection

from corpusly.repositories.documents import DocumentRepository
from corpusly.repositories.workspaces import WorkspaceRepository


# dependency with yield that borrows one connection from the pool for the lifetime of one request.
# You never write commit() or rollback() yourself. Because the with block surrounds the yield, the transaction always ends correctly, whichever way the request ends.
def get_db_connection(request: Request) -> Iterator[Connection]:
    with request.app.state.db_pool.connection() as conn:
        yield conn

# scope="function" goes here, on the dependency that commits. It makes the code after yield run before the response is sent, so a 200 means the data is saved.
ConnectionFromPool = Annotated[Connection, Depends(get_db_connection, scope='function')]

def get_workspace_repository(conn: ConnectionFromPool) -> WorkspaceRepository:
    return WorkspaceRepository(conn)

def get_document_repository(conn: ConnectionFromPool) -> DocumentRepository:
    return DocumentRepository(conn)

WorkspaceRepo = Annotated[WorkspaceRepository, Depends(get_workspace_repository)]
DocumentRepo = Annotated[DocumentRepository, Depends(get_document_repository)]
