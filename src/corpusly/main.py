from fastapi import FastAPI, Request
from corpusly.routes import workspace, documents
import uuid

app = FastAPI()

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
