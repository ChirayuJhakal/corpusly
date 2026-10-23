import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from corpusly.config import settings
from corpusly.routes import documents, workspace


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: runs once, before the first request
    # row_factory=dict_row: every pooled connection returns rows as dicts keyed by column name.
    pool = ConnectionPool(conninfo = settings.database_url, min_size = 4, max_size = 10, open=False, kwargs={"row_factory": dict_row})
    pool.open(wait=True) # open the pool and wait for it to be ready
    app.state.db_pool = pool
    yield                       # the app serves requests while paused here
    pool.close()                # shutdown: runs once, after the last request

app = FastAPI(lifespan=lifespan)

app.include_router(workspace.router)
app.include_router(documents.router)

@app.middleware("http")
async def add_request_id_header(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID")
    if request_id is None:
        request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

@app.get("/health")
def health():
    return {"message": "server running fine"}

@app.get("/")
def root():
    return {"message": "server running"}
