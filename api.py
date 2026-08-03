"""Minimal API surface over the pipeline.

    uvicorn api:app --reload

POST /v1/ask      {"question": "..."}
POST /v1/ingest   {"path": "./sample_docs"}
GET  /v1/documents
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from config import settings
from pipeline import RAGPipeline


app = FastAPI(title="RAG Pipeline API")

# Lazy pipeline initialization
_pipeline = None


def get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline(settings)
    return _pipeline


# --- Auth Middleware ---
security = HTTPBearer()


async def verify_api_key(auth: HTTPAuthorizationCredentials = Security(security)):
    """
    Simple Bearer token authentication.
    Expected header: Authorization: Bearer <api_key>
    """
    if auth.credentials != settings.api_key:
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing API Key. Please provide a valid Bearer token."
        )
    return auth.credentials


class AskRequest(BaseModel):
    question: str


class IngestRequest(BaseModel):
    path: str


@app.post("/v1/ask", dependencies=[Depends(verify_api_key)])
def ask(req: AskRequest):
    pipeline = get_pipeline()
    response = pipeline.ask(req.question)
    return response.__dict__


@app.post("/v1/ingest", dependencies=[Depends(verify_api_key)])
def ingest(req: IngestRequest):
    pipeline = get_pipeline()
    try:
        return pipeline.ingest_directory(req.path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/v1/documents", dependencies=[Depends(verify_api_key)])
def documents():
    pipeline = get_pipeline()
    records = pipeline.vector_store.all_chunks()
    sources = sorted({r["payload"]["source"] for r in records})
    return {"documents": sources, "total_chunks": len(records)}
