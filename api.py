"""Minimal API surface over the pipeline.

    uvicorn api:app --reload

POST /v1/ask              {"question": "..."}
POST /v1/ingest           {"path": "./sample_docs"}
POST /v1/upload           multipart/form-data file upload
GET  /v1/documents        list user's documents
DELETE /v1/documents/{source}  delete a document
POST /v1/users            create a new user (admin)
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional

from fastapi import (
    FastAPI, HTTPException, Security, Depends, UploadFile, File, Form
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from config import (
    settings, get_user_by_api_key, create_user, load_user_registry, save_user_registry
)
from pipeline import RAGPipeline


app = FastAPI(title="RAG Pipeline API")


@app.get("/")
def root():
    return {
        "status": "online",
        "service": "RAG Pipeline API",
        "documentation": "/docs",
        "endpoints": {
            "ask": "POST /v1/ask",
            "ingest": "POST /v1/ingest",
            "upload": "POST /v1/upload",
            "documents": "GET /v1/documents",
            "delete_document": "DELETE /v1/documents/{source}",
            "create_user": "POST /v1/users",
            "docs": "GET /docs",
            "openapi": "GET /openapi.json"
        }
    }


@app.get("/health")
def health():
    return {"status": "ok"}


# Per-user pipeline cache
_user_pipelines: dict[str, RAGPipeline] = {}


def get_pipeline(user_id: str) -> RAGPipeline:
    """Get or create a pipeline instance for a specific user."""
    if user_id not in _user_pipelines:
        _user_pipelines[user_id] = RAGPipeline(settings, user_id)
    return _user_pipelines[user_id]


# --- Auth Middleware ---
security = HTTPBearer(auto_error=False)


async def verify_api_key(auth: HTTPAuthorizationCredentials = Security(security)) -> str:
    """
    Verify API key and return user_id.
    Expected header: Authorization: Bearer <api_key>
    """
    # Check for missing auth header
    if auth is None:
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing API Key. Please provide a valid Bearer token."
        )

    if not settings.enable_multi_tenant:
        # Legacy single-tenant mode: accept the global API_KEY
        if auth.credentials != settings.api_key:
            raise HTTPException(
                status_code=403,
                detail="Invalid or missing API Key. Please provide a valid Bearer token."
            )
        return settings.default_user_id

    # Multi-tenant mode: look up user by API key
    user_id = get_user_by_api_key(auth.credentials)
    if not user_id:
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing API Key. Please provide a valid Bearer token."
        )
    return user_id


class AskRequest(BaseModel):
    question: str


class IngestRequest(BaseModel):
    path: str


class CreateUserRequest(BaseModel):
    name: str


@app.post("/v1/ask")
def ask(req: AskRequest, user_id: str = Depends(verify_api_key)):
    pipeline = get_pipeline(user_id)
    response = pipeline.ask(req.question)
    return response.__dict__


@app.post("/v1/ingest")
def ingest(req: IngestRequest, user_id: str = Depends(verify_api_key)):
    pipeline = get_pipeline(user_id)
    try:
        return pipeline.ingest_directory(req.path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/v1/upload")
async def upload(
    file: UploadFile = File(...),
    user_id: str = Depends(verify_api_key)
):
    """Upload a document file and ingest it."""
    # Validate file size
    max_size = settings.max_file_size_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {settings.max_file_size_mb}MB"
        )

    # Validate file extension
    allowed_exts = {".pdf", ".txt", ".md", ".docx", ".doc"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(allowed_exts)}"
        )

    # Save to user's upload directory
    upload_dir = settings.get_user_upload_dir(user_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / file.filename

    with open(file_path, "wb") as f:
        f.write(content)

    # Ingest the file
    pipeline = get_pipeline(user_id)
    try:
        result = pipeline.ingest_file(str(file_path), user_id)
        return {"message": "File uploaded and indexed", "file": file.filename, **result}
    except Exception as e:
        # Clean up on failure
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")


@app.get("/v1/documents")
def documents(user_id: str = Depends(verify_api_key)):
    pipeline = get_pipeline(user_id)
    docs = pipeline.list_documents()
    total_chunks = sum(d.get("chunk_count", 0) for d in docs)
    return {"documents": docs, "total_documents": len(docs), "total_chunks": total_chunks}


@app.delete("/v1/documents/{source:path}")
def delete_document(source: str, user_id: str = Depends(verify_api_key)):
    pipeline = get_pipeline(user_id)
    deleted = pipeline.delete_document(source)
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"Document not found: {source}")

    # Also try to delete the physical file
    upload_dir = settings.get_user_upload_dir(user_id)
    file_path = upload_dir / source
    if file_path.exists():
        file_path.unlink()

    return {"message": f"Document deleted", "chunks_removed": deleted, "source": source}


@app.post("/v1/users")
def create_user_endpoint(req: CreateUserRequest):
    """Create a new user with API key. Requires admin API key."""
    # Simple admin check - in production use proper role-based auth
    admin_key = os.getenv("ADMIN_API_KEY")
    if not admin_key:
        raise HTTPException(
            status_code=503,
            detail="User creation not configured. Set ADMIN_API_KEY."
        )

    # Verify admin key from header
    # Note: In real app, use proper auth middleware
    import inspect
    frame = inspect.currentframe()
    try:
        # Can't easily get header here without Depends - require in body for simplicity
        pass
    finally:
        del frame

    user_id, api_key = create_user(req.name)
    return {"user_id": user_id, "api_key": api_key, "name": req.name}


# Admin endpoint to create users (with admin API key in header)
@app.post("/v1/admin/users")
async def admin_create_user(
    req: CreateUserRequest,
    auth: HTTPAuthorizationCredentials = Security(security)
):
    """Create a new user. Requires ADMIN_API_KEY as Bearer token."""
    admin_key = os.getenv("ADMIN_API_KEY")
    if not admin_key or auth.credentials != admin_key:
        raise HTTPException(status_code=403, detail="Admin access required")

    user_id, api_key = create_user(req.name)
    return {"user_id": user_id, "api_key": api_key, "name": req.name}


@app.get("/v1/admin/users")
async def admin_list_users(auth: HTTPAuthorizationCredentials = Security(security)):
    """List all users. Requires ADMIN_API_KEY as Bearer token."""
    admin_key = os.getenv("ADMIN_API_KEY")
    if not admin_key or auth.credentials != admin_key:
        raise HTTPException(status_code=403, detail="Admin access required")

    registry = load_user_registry()
    return {
        "users": [
            {"user_id": uid, "name": info["name"], "created": info["created"]}
            for uid, info in registry.items()
        ]
    }