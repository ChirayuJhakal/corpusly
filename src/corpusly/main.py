from fastapi import FastAPI
from corpusly.routes import workspace, documents

app = FastAPI()

app.include_router(workspace.router)
app.include_router(documents.router)
