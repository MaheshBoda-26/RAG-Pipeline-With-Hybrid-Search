"""Minimal API surface over the pipeline.

    uvicorn api:app --reload

POST /v1/ask              {"question": "..."}
POST /v1/ingest           {"path": "./sample_docs"}
POST /v1/upload           multipart/form-data file upload
GET  /v1/documents        list user's documents
DELETE /v1/documents/{source}  delete a document
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
import magic

from fastapi import (
    FastAPI, HTTPException, Security, Depends, UploadFile, File, Form,
    Response, Request, Cookie
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

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


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Limit request body size globally."""

    def __init__(self, app, max_size: int = 10 * 1024 * 1024):
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_size:
            return StarletteResponse("Request body too large", status_code=413)
        return await call_next(request)


app.add_middleware(RequestSizeLimitMiddleware, max_size=10 * 1024 * 1024)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response: StarletteResponse = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        # Remove server header to avoid leaking version info
        if "server" in response.headers:
            del response.headers["server"]

        # Content-Security-Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "font-src 'self' data: https://cdn.jsdelivr.net; "
            "connect-src 'self' http://localhost:8000 ws://localhost:8000;"
        )
        response.headers["Content-Security-Policy"] = csp

        # Strict-Transport-Security (only on HTTPS)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


# Security headers middleware (added after CORS so it wraps all responses)
app.add_middleware(SecurityHeadersMiddleware)


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


async def verify_auth(
    request: Request,
    access_token: str | None = Cookie(default=None, alias="access_token")
) -> str:
    """
    Verify authentication via JWT token OR API key.
    Checks JWT first (cookie or Authorization header), then falls back to API key.
    """
    # Try JWT token first (from cookie)
    token = access_token
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

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
            detail="Invalid or expired token/API key."
        )

    raise HTTPException(
        status_code=401,
        detail="Not authenticated. Please login or provide API key."
    )


async def verify_admin(user_id: str = Depends(verify_auth)) -> str:
    """Verify the authenticated user has admin role."""
    registry = load_user_registry()
    user = registry.get(user_id)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
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


async def verify_demo_upload(
    request: Request,
    access_token: str | None = Cookie(default=None, alias="access_token")
) -> str:
    """
    Verify token for demo upload endpoint.
    Returns user_id if authenticated, otherwise returns "anonymous" for rate limiting.
    """
    token = access_token

    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if token:
        user_id = get_user_id_from_token(token)
        if user_id:
            return user_id

    return "anonymous"


class AskRequest(BaseModel):
    question: str


class IngestRequest(BaseModel):
    path: str


class CreateUserRequest(BaseModel):
    name: str
    role: str = "user"


@limiter.limit("30/minute")
@app.post("/v1/ask")
async def ask(request: Request, req: AskRequest, user_id: str = Depends(verify_auth)):
    pipeline = get_pipeline(user_id)
    response = pipeline.ask(req.question)
    return response.__dict__


@limiter.limit("10/minute")
@app.post("/v1/ingest")
async def ingest(request: Request, req: IngestRequest, user_id: str = Depends(verify_auth)):
    pipeline = get_pipeline(user_id)
    try:
        return pipeline.ingest_directory(req.path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@limiter.limit("10/minute")
@app.post("/v1/upload")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    user_id: str = Depends(verify_auth)
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

    # Validate MIME type from content
    mime = magic.from_buffer(content, mime=True)
    allowed_mimes = {
        "application/pdf",
        "text/plain",
        "text/markdown",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    }
    if mime not in allowed_mimes:
        raise HTTPException(400, f"Invalid file type: {mime}. Allowed: PDF, TXT, MD, DOCX, DOC")

    # Check extension matches MIME
    ext_mime_map = {
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
    }
    ext = Path(safe_filename).suffix.lower()
    if ext in ext_mime_map and mime != ext_mime_map[ext]:
        raise HTTPException(400, "File extension does not match content type")

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
        raise HTTPException(status_code=400, detail=f"Invalid file: {error_msg}")
    except Exception as e:
        # Unknown errors - keep file for debugging
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")


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

    # Also try to delete the physical file
    upload_dir = settings.get_user_upload_dir(user_id)
    file_path = upload_dir / source
    if file_path.exists():
        file_path.unlink()

    return {"message": f"Document deleted", "chunks_removed": deleted, "source": source}


# Admin endpoint to create users (requires authenticated admin user)
@app.post("/v1/admin/users")
async def admin_create_user(
    req: CreateUserRequest,
    user_id: str = Depends(verify_admin)
):
    """Create a new user. Requires authenticated admin user."""
    user_id, api_key = create_user(req.name, role=req.role)
    return {"user_id": user_id, "api_key": api_key, "name": req.name, "role": req.role}


@app.get("/v1/admin/users")
async def admin_list_users(user_id: str = Depends(verify_admin)):
    """List all users. Requires authenticated admin user."""
    registry = load_user_registry()
    return {
        "users": [
            {"user_id": uid, "name": info["name"], "created": info["created"], "role": info.get("role", "user")}
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
    """Clear auth cookies."""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")


@limiter.limit("3/minute")
@app.post("/v1/auth/register", response_model=TokenResponse)
async def register(request: Request, req: RegisterRequest, response: Response):
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


@limiter.limit("5/minute")
@app.post("/v1/auth/login", response_model=TokenResponse)
async def login(request: Request, req: LoginRequest, response: Response):
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
async def get_current_user(user_id: str = Depends(verify_auth)):
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
@limiter.limit("10/minute")
@app.post("/v1/demo/ask")
async def demo_ask(request: Request, req: AskRequest):
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


@limiter.limit("5/minute")
@app.post("/v1/demo/upload")
async def demo_upload(
    request: Request,
    file: UploadFile = File(...),
):
    """Upload a document file and ingest it using demo/global collection (no auth required)."""
    user_id = settings.default_user_id
    import logging
    logging.getLogger(__name__).info("Demo upload by anonymous user")
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

    # Validate MIME type from content
    mime = magic.from_buffer(content, mime=True)
    allowed_mimes = {
        "application/pdf",
        "text/plain",
        "text/markdown",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    }
    if mime not in allowed_mimes:
        raise HTTPException(400, f"Invalid file type: {mime}. Allowed: PDF, TXT, MD, DOCX, DOC")

    # Check extension matches MIME
    ext_mime_map = {
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
    }
    ext = Path(safe_filename).suffix.lower()
    if ext in ext_mime_map and mime != ext_mime_map[ext]:
        raise HTTPException(400, "File extension does not match content type")

    # Save to demo upload directory
    upload_dir = settings.get_user_upload_dir(settings.default_user_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Add UUID prefix to avoid filename collisions
    import uuid
    unique_filename = f"{uuid.uuid4().hex[:8]}_{safe_filename}"
    file_path = upload_dir / unique_filename

    try:
        with open(file_path, "wb") as f:
            f.write(content)

        # Ingest the file - pass original filename for better source tracking
        pipeline = get_pipeline(settings.default_user_id)
        result = pipeline.ingest_file(str(file_path), original_filename=safe_filename, user_id=settings.default_user_id)
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
        raise HTTPException(status_code=400, detail=f"Invalid file: {error_msg}")
    except Exception as e:
        # Unknown errors - keep file for debugging
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")


# Import decode_token for refresh endpoint
from config import decode_token