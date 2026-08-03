"""Minimal API surface over the pipeline.

    uvicorn api:app --reload

POST /v1/ask      {"question": "..."}
POST /v1/ingest   {"path": "./sample_docs"}
GET  /v1/documents
"""
from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from config import settings
from pipeline import RAGPipeline

app = FastAPI(title="RAG Pipeline API")
pipeline = RAGPipeline(settings)


class AskRequest(BaseModel):
    question: str


class IngestRequest(BaseModel):
    path: str


@app.post("/v1/ask")
def ask(req: AskRequest):
    response = pipeline.ask(req.question)
    return response.__dict__


@app.post("/v1/ingest")
def ingest(req: IngestRequest):
    return pipeline.ingest_directory(req.path)


@app.get("/v1/documents")
def documents():
    records = pipeline.vector_store.all_chunks()
    sources = sorted({r["payload"]["source"] for r in records})
    return {"documents": sources, "total_chunks": len(records)}
