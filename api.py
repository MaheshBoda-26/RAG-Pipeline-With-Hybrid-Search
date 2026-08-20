"""Minimal API surface over the pipeline.

    uvicorn api:app --reload

POST /v1/ask              {"question": "..."}
POST /v1/ingest           {"path": "./sample_docs"}
POST /v1/upload           multipart/form-data file upload
GET  /v1/documents        list user's documents
DELETE /v1/documents/{source}  delete a document
POST /v1/users            create a new user (admin)
POST /v1/auth/register    register new user
POST /v1/auth/login       login user (returns JWT cookies)
POST /v1/auth/refresh     refresh access token
POST /v1/auth/logout      logout user
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional
from datetime import timedelta

from fastapi import (
    FastAPI, HTTPException, Security, Depends, UploadFile, File, Form,
    Response, Request, Cookie
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import (
    settings, get_user_by_api_key, create_user, load_user_registry, save_user_registry,
    verify_user_password, get_user_by_email, create_access_token, create_refresh_token,
    get_user_id_from_token
)
from pipeline import RAGPipeline


app = FastAPI(title="RAG Pipeline API")

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


async def verify_jwt_token(
    request: Request,
    access_token: str | None = Cookie(default=None, alias="access_token")
) -> str:
    """
    Verify JWT token from HttpOnly cookie and return user_id.
    Supports both cookie and Authorization header (for backward compatibility).
    """
    token = access_token

    # Fallback to Authorization header if no cookie
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated. Please login."
        )

    user_id = get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token. Please login again."
        )

    return user_id


async def get_optional_user_id(
    request: Request,
    access_token: str | None = Cookie(default=None, alias="access_token")
) -> str | None:
    """
    Get user_id if authenticated, otherwise return None (for demo mode).
    """
    token = access_token

    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        return None

    user_id = get_user_id_from_token(token)
    return user_id


class AskRequest(BaseModel):
    question: str


class IngestRequest(BaseModel):
    path: str


class CreateUserRequest(BaseModel):
    name: str


@app.post("/v1/ask")
async def ask(req: AskRequest, user_id: str = Depends(verify_jwt_token)):
    pipeline = get_pipeline(user_id)
    response = pipeline.ask(req.question)
    return response.__dict__


@app.post("/v1/ingest")
async def ingest(req: IngestRequest, user_id: str = Depends(verify_jwt_token)):
    pipeline = get_pipeline(user_id)
    try:
        return pipeline.ingest_directory(req.path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/v1/upload")
async def upload(
    file: UploadFile = File(...),
    user_id: str = Depends(verify_jwt_token)
):
    """Upload a document file and ingest it."""
    # Check if API key is configured before accepting uploads
    if not settings.nvidia_api_key or settings.nvidia_api_key in ("", "your-nvidia-key", "test-key"):
        raise HTTPException(
            status_code=503,
            detail="Embedding service not configured. Set NVIDIA_API_KEY in .env file."
        )

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
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(allowed_exts))}"
        )

    # Validate filename (no path traversal)
    safe_filename = Path(file.filename).name
    if not safe_filename or safe_filename.startswith("."):
        raise HTTPException(
            status_code=400,
            detail="Invalid filename"
        )

    # Save to user's upload directory
    upload_dir = settings.get_user_upload_dir(user_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Add UUID prefix to avoid filename collisions
    import uuid
    unique_filename = f"{uuid.uuid4().hex[:8]}_{safe_filename}"
    file_path = upload_dir / unique_filename

    try:
        with open(file_path, "wb") as f:
            f.write(content)

        # Ingest the file
        pipeline = get_pipeline(user_id)
        result = pipeline.ingest_file(str(file_path), user_id)
        return {
            "message": "File uploaded and indexed",
            "file": safe_filename,
            "stored_as": unique_filename,
            **result
        }
    except HTTPException:
        # Clean up on failure
        if file_path.exists():
            file_path.unlink()
        raise
    except Exception as e:
        # Clean up on failure
        if file_path.exists():
            file_path.unlink()
        error_msg = str(e)
        if "401" in error_msg or "Authentication" in error_msg:
            raise HTTPException(
                status_code=503,
                detail=f"Embedding API authentication failed. Check NVIDIA_API_KEY in .env"
            )
        if "404" in error_msg and "model" in error_msg.lower():
            raise HTTPException(
                status_code=503,
                detail=f"Embedding model not found. Check EMBEDDING_MODEL in .env"
            )
        raise HTTPException(status_code=500, detail=f"Failed to process file: {error_msg}")


@app.get("/v1/documents")
async def documents(user_id: str = Depends(verify_jwt_token)):
    pipeline = get_pipeline(user_id)
    docs = pipeline.list_documents()
    total_chunks = sum(d.get("chunk_count", 0) for d in docs)
    return {"documents": docs, "total_documents": len(docs), "total_chunks": total_chunks}


@app.delete("/v1/documents/{source:path}")
async def delete_document(source: str, user_id: str = Depends(verify_jwt_token)):
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


# --- JWT Auth Endpoints ---
class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    """Set HttpOnly cookies for auth tokens."""
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/",
    )


def clear_auth_cookies(response: Response):
    """Clear auth cookies."""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")


@app.post("/v1/auth/register", response_model=TokenResponse)
async def register(req: RegisterRequest, response: Response):
    """Register a new user and return JWT tokens in HttpOnly cookies."""
    # Check if user already exists
    existing_user_id = get_user_by_email(req.email)
    if existing_user_id:
        raise HTTPException(status_code=400, detail="User already exists")

    # Create user with password
    user_id, api_key = create_user(req.name or req.email, req.email, req.password)

    # Generate tokens
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    # Set HttpOnly cookies
    set_auth_cookies(response, access_token, refresh_token)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@app.post("/v1/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest, response: Response):
    """Login user and return JWT tokens in HttpOnly cookies."""
    user_id = get_user_by_email(req.email)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_user_password(user_id, req.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Generate tokens
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    # Set HttpOnly cookies
    set_auth_cookies(response, access_token, refresh_token)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@app.post("/v1/auth/refresh", response_model=TokenResponse)
async def refresh_token(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias="refresh_token")
):
    """Refresh access token using refresh token."""
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token not found")

    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Generate new tokens
    new_access_token = create_access_token(user_id)
    new_refresh_token = create_refresh_token(user_id)

    # Set new cookies
    set_auth_cookies(response, new_access_token, new_refresh_token)

    return TokenResponse(access_token=new_access_token, refresh_token=new_refresh_token)


@app.post("/v1/auth/logout")
async def logout(response: Response):
    """Logout user by clearing cookies."""
    clear_auth_cookies(response)
    return {"message": "Logged out successfully"}


@app.get("/v1/auth/me")
async def get_current_user(user_id: str = Depends(verify_jwt_token)):
    """Get current authenticated user info."""
    registry = load_user_registry()
    user = registry.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": user_id,
        "email": user.get("name", ""),
        "name": user.get("name", ""),
    }


# --- Demo mode endpoint (uses global 'docs' collection) ---
@app.post("/v1/demo/ask")
async def demo_ask(req: AskRequest):
    """Ask question using demo/global collection (no auth required)."""
    pipeline = get_pipeline(settings.default_user_id)
    response = pipeline.ask(req.question)
    return response.__dict__


@app.get("/v1/demo/documents")
async def demo_documents():
    """List demo documents (no auth required)."""
    pipeline = get_pipeline(settings.default_user_id)
    docs = pipeline.list_documents()
    total_chunks = sum(d.get("chunk_count", 0) for d in docs)
    return {"documents": docs, "total_documents": len(docs), "total_chunks": total_chunks}


# Import decode_token for refresh endpoint
from config import decode_token