"""Minimal API surface over the pipeline.

    uvicorn api:app --reload

POST /v1/ask              {"question": "..."}
POST /v1/ask/stream       {"question": "..."} - SSE stream
POST /v1/ingest           {"path": "./sample_docs"}
POST /v1/upload           multipart/form-data file upload
GET  /v1/documents        list user's documents
DELETE /v1/documents/{source}  delete a document
POST /v1/auth/register    register new user
POST /v1/auth/login       login user (returns JWT cookies)
"""
import asyncio
import os
from pathlib import Path
from typing import Optional, AsyncGenerator
from datetime import timedelta
import json

from fastapi import (
    FastAPI, HTTPException, Security, Depends, UploadFile, File, Form,
    Response, Request, Cookie, Body
)
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from openai import AsyncOpenAI

from config import (
    settings, get_user_by_api_key, create_user, load_user_registry, save_user_registry,
    verify_user_password, get_user_by_email, create_access_token, create_refresh_token,
    get_user_id_from_token
)
from pipeline import RAGPipeline

app = FastAPI(title="RAG Pipeline API")

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add hardening headers and stop leaking the server banner."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # Minimal CSP: API returns JSON only; docs UI needs inline scripts.
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'",
        )
        response.headers["server"] = "rag-api"
        return response


app.add_middleware(SecurityHeadersMiddleware)

# CORS middleware for frontend
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in cors_origins],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Cookie"],
    expose_headers=["Retry-After"],
    max_age=86400,
)


@app.get("/")
def root():
    return {
        "status": "online",
        "service": "RAG Pipeline API",
        "documentation": "/docs",
        "endpoints": {
            "ask": "POST /v1/ask",
            "ask_stream": "POST /v1/ask/stream",
            "ingest": "POST /v1/ingest",
            "upload": "POST /v1/upload",
            "documents": "GET /v1/documents",
            "delete_document": "DELETE /v1/documents/{source}",
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


def _get_token_from_request(request: Request, access_token: str | None = None) -> str | None:
    token = access_token
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
    return token


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
    token = _get_token_from_request(request, access_token)

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


async def verify_auth(
    request: Request,
    access_token: str | None = Cookie(default=None, alias="access_token")
) -> str:
    """
    Verify authentication via JWT token OR API key.
    Checks JWT first (cookie or Authorization header), then falls back to API key.
    """
    token = _get_token_from_request(request, access_token)

    if token:
        # Try JWT
        user_id = get_user_id_from_token(token)
        if user_id:
            return user_id

        # Try API key
        user_id = get_user_by_api_key(token)
        if user_id:
            return user_id

    raise HTTPException(
        status_code=401,
        detail="Invalid or missing authentication. Please provide a valid Bearer token or login cookie."
    )


async def verify_admin(
    request: Request,
    access_token: str | None = Cookie(default=None, alias="access_token")
) -> str:
    """Verify that the caller is authenticated and has the 'admin' role."""
    user_id = await verify_auth(request, access_token)
    registry = load_user_registry()
    user = registry.get(user_id, {})
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required."
        )
    return user_id


class AskRequest(BaseModel):
    question: str
    source: str | None = None


class IngestRequest(BaseModel):
    path: str


class CreateUserRequest(BaseModel):
    name: str
    role: str = "user"


@app.post("/v1/ask")
@limiter.limit("30/minute")
async def ask(request: Request, req: AskRequest = Body(...), user_id: str = Depends(verify_auth)):
    pipeline = get_pipeline(user_id)
    response = pipeline.ask(req.question, source=req.source)
    return response.__dict__


@app.post("/v1/ask/stream")
@limiter.limit("30/minute")
async def ask_stream(request: Request, req: AskRequest = Body(...), user_id: str = Depends(verify_auth)):
    """SSE streaming endpoint for token-by-token generation."""
    pipeline = get_pipeline(user_id)

    async def event_generator():
        try:
            async for chunk in pipeline.ask_stream(req.question, source=req.source):
                # Yield each token as it comes
                data = json.dumps({"token": chunk["delta"]})
                yield f"event: token\ndata: {data}\n\n"
        except Exception as e:
            data = json.dumps({"error": str(e)})
            yield f"event: error\ndata: {data}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/v1/ingest")
@limiter.limit("10/minute")
async def ingest(request: Request, req: IngestRequest = Body(...), user_id: str = Depends(verify_auth)):
    pipeline = get_pipeline(user_id)
    try:
        return pipeline.ingest_directory(req.path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


async def _process_file_upload(file: UploadFile, user_id: str) -> dict:
    """Process file upload: validation, saving, and ingestion."""
    # Check if API key is configured before accepting uploads
    if not settings.nvidia_api_key or settings.nvidia_api_key in ("", "your-nvidia-key", "test-key"):
        raise HTTPException(
            status_code=503,
            detail="Embedding service not configured. Set NVIDIA_API_KEY in .env file."
        )

    # Validate file size BEFORE reading the whole body into memory twice
    content = await file.read()
    max_size = settings.max_file_size_mb * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {settings.max_file_size_mb}MB"
        )

    # Validate filename (no path traversal) BEFORE any processing
    safe_filename = Path(file.filename or "").name
    if not safe_filename or safe_filename.startswith("."):
        raise HTTPException(
            status_code=400,
            detail="Invalid filename"
        )

    # Validate file extension
    allowed_exts = {".pdf", ".txt", ".md", ".docx", ".doc"}
    ext = Path(safe_filename).suffix.lower()
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(allowed_exts))}"
        )

    # Validate MIME type from content
    import magic
    mime = magic.from_buffer(content, mime=True)
    allowed_mimes = {
        "application/pdf",
        "text/plain",
        "text/markdown",
        "text/x-markdown",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "application/zip",  # older libmagic reports legacy .doc as zip
    }
    if mime not in allowed_mimes:
        raise HTTPException(400, f"Invalid file type: {mime}. Allowed: PDF, TXT, MD, DOCX, DOC")

    # Check extension matches MIME.
    # .docx MUST be the OOXML MIME (python-docx also rejects non-zip anyway).
    # .doc: libmagic historically reports older .doc files as application/zip,
    # so both are accepted — but anything else (e.g. octet-stream from a
    # spoofed 4-byte header) is rejected.
    ext_mime_map = {
        ".pdf": {"application/pdf"},
        ".txt": {"text/plain"},
        ".md": {"text/plain", "text/markdown"},
        ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        ".doc": {"application/msword", "application/zip", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    }
    if mime not in ext_mime_map.get(ext, set()):
        raise HTTPException(400, f"File extension does not match content type")

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

        # Ingest the file - pass original filename for better source tracking
        pipeline = get_pipeline(user_id)
        result = pipeline.ingest_file(str(file_path), original_filename=safe_filename, user_id=user_id)
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
    except RuntimeError as e:
        # Embedding/indexing service errors - keep file for retry
        error_msg = str(e)
        if "AuthenticationError" in error_msg or "401" in error_msg:
            raise HTTPException(
                status_code=503,
                detail=f"Embedding API authentication failed. Check NVIDIA_API_KEY in .env"
            )
        if "404" in error_msg and "model" in error_msg.lower():
            raise HTTPException(
                status_code=503,
                detail=f"Embedding model not found. Check EMBEDDING_MODEL in .env"
            )
        raise HTTPException(status_code=502, detail=f"Indexing service unavailable: {error_msg}")
    except ValueError as e:
        # Path validation / file format errors - clean up file
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=400, detail=f"Invalid file: {str(e)}")
    except Exception as e:
        # Unknown errors - keep file for debugging
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")


@limiter.limit("10/minute")
@app.post("/v1/upload")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    user_id: str = Depends(verify_auth)
):
    """Upload a document file and ingest it."""
    return await _process_file_upload(file, user_id)


@app.get("/v1/documents")
async def documents(user_id: str = Depends(verify_auth)):
    pipeline = get_pipeline(user_id)
    docs = pipeline.list_documents()
    total_chunks = sum(d.get("chunk_count", 0) for d in docs)
    return {"documents": docs, "total_documents": len(docs), "total_chunks": total_chunks}


@app.delete("/v1/documents/{source:path}")
async def delete_document(source: str, user_id: str = Depends(verify_auth)):
    pipeline = get_pipeline(user_id)
    deleted = pipeline.delete_document(source)
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"Document not found: {source}")

    # Also try to delete the physical file - with path traversal protection
    upload_dir = settings.get_user_upload_dir(user_id)
    allowed_root = Path(upload_dir).resolve()
    file_path = (allowed_root / source).resolve()

    # Validate that the resolved path is within the upload directory
    if not file_path.is_relative_to(allowed_root):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid document path: {source} is outside the allowed upload directory"
        )

    if file_path.exists():
        file_path.unlink()

    return {"message": f"Document deleted", "chunks_removed": deleted, "source": source}


# Admin endpoint to create users (requires authenticated admin user)
@app.post("/v1/admin/users")
async def admin_create_user(
    req: CreateUserRequest = Body(...),
    user_id: str = Depends(verify_admin)
):
    """Create a new user. Requires authenticated admin user."""
    # Role whitelist: an unchecked role field would let an admin account be
    # created with arbitrary role strings (or an operator typo silently grant
    # privileges). Only these two roles exist in the authorization model.
    if req.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Role must be 'user' or 'admin'")
    import logging
    logging.getLogger(__name__).info("Admin %s creating user with role=%s", user_id, req.role)
    new_user_id, api_key = create_user(req.name, role=req.role)
    return {"user_id": new_user_id, "api_key": api_key, "name": req.name, "role": req.role}


@app.get("/v1/admin/users")
async def admin_list_users(user_id: str = Depends(verify_admin)):
    """List all users. Requires authenticated admin user."""
    registry = load_user_registry()
    return {"users": registry}


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
    secure = settings.cookie_secure
    domain = settings.cookie_domain or None
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
        domain=domain,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/",
        domain=domain,
    )


def clear_auth_cookies(response: Response):
    """Clear HttpOnly auth cookies."""
    domain = settings.cookie_domain or None
    response.delete_cookie(key="access_token", path="/", domain=domain)
    response.delete_cookie(key="refresh_token", path="/", domain=domain)


@limiter.limit("5/minute")
@app.post("/v1/auth/register", response_model=TokenResponse)
async def register(request: Request, req: RegisterRequest = Body(...), response: Response = None):
    """Register a new user and return JWT tokens in HttpOnly cookies."""
    # FastAPI injects the real Response when the default is None; a manually
    # constructed Response() here would be discarded and its cookies lost.
    existing_user_id = get_user_by_email(req.email)
    if existing_user_id:
        raise HTTPException(status_code=400, detail="User already exists")

    user_id, api_key = create_user(req.name or req.email, req.email, req.password)

    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    set_auth_cookies(response, access_token, refresh_token)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@limiter.limit("5/minute")
@app.post("/v1/auth/login", response_model=TokenResponse)
async def login(request: Request, req: LoginRequest = Body(...), response: Response = None):
    """Login user and return JWT tokens in HttpOnly cookies."""
    user_id = get_user_by_email(req.email)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_user_password(user_id, req.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    set_auth_cookies(response, access_token, refresh_token)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@app.post("/v1/auth/refresh", response_model=TokenResponse)
async def refresh_token(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias="refresh_token")
):
    """Refresh access token using refresh token."""
    from config import decode_token
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token not found")

    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    new_access_token = create_access_token(user_id)
    new_refresh_token = create_refresh_token(user_id)

    set_auth_cookies(response, new_access_token, new_refresh_token)

    return TokenResponse(access_token=new_access_token, refresh_token=new_refresh_token)


@app.post("/v1/auth/logout")
async def logout(response: Response):
    """Logout user by clearing cookies."""
    clear_auth_cookies(response)
    return {"message": "Logged out successfully"}


@app.get("/v1/auth/me")
async def get_current_user(user_id: str = Depends(verify_auth)):
    """Get current authenticated user info."""
    registry = load_user_registry()
    user = registry.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": user_id,
        "email": user.get("email", user.get("name", "")),
        "name": user.get("name", ""),
    }


# --- Demo mode endpoint (uses global 'docs' collection) ---
@limiter.limit("10/minute")
@app.post("/v1/demo/ask")
async def demo_ask(request: Request, req: AskRequest = Body(...)):
    """Ask question using demo/global collection (no auth required)."""
    pipeline = get_pipeline(settings.default_user_id)
    response = pipeline.ask(req.question, source=req.source)
    return response.__dict__


@app.get("/v1/demo/documents")
async def demo_documents():
    """List demo documents (no auth required)."""
    pipeline = get_pipeline(settings.default_user_id)
    docs = pipeline.list_documents()
    total_chunks = sum(d.get("chunk_count", 0) for d in docs)
    return {"documents": docs, "total_documents": len(docs), "total_chunks": total_chunks}


@limiter.limit("5/minute")
@app.post("/v1/demo/upload")
async def demo_upload(
    request: Request,
    file: UploadFile = File(...),
):
    """Upload a document file and ingest it using demo/global collection (no auth required)."""
    import logging
    logging.getLogger(__name__).info("Demo upload by anonymous user")
    return await _process_file_upload(file, settings.default_user_id)