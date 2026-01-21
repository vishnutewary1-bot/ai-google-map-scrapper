"""API middleware configuration."""

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from loguru import logger
import time

# Import settings
from config.settings import settings

# Rate limiting (optional)
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    HAS_SLOWAPI = True
except ImportError:
    HAS_SLOWAPI = False

# JWT verification (optional)
try:
    from jose import JWTError, jwt
    HAS_JWT = True
except ImportError:
    HAS_JWT = False

# Security bearer for JWT
security = HTTPBearer(auto_error=False)


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token if authentication is enabled."""
    if not settings.auth_enabled:
        return None

    if not HAS_JWT:
        logger.warning("JWT library not installed. Install python-jose[cryptography] for auth support.")
        return None

    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def setup_middleware(app: FastAPI):
    """Configure all middleware for the FastAPI app."""

    # CORS middleware - use settings for origins
    allowed_origins = settings.cors_origins if settings.cors_origins else ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Rate limiting
    if HAS_SLOWAPI:
        limiter = Limiter(key_func=get_remote_address)
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Log all incoming requests."""
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time

        # Log request
        logger.info(
            f"{request.method} {request.url.path} "
            f"- {response.status_code} "
            f"- {duration:.3f}s"
        )

        return response

    # Error handling middleware
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle uncaught exceptions."""
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(exc) if app.debug else "An error occurred",
            },
        )

    return app


def get_rate_limiter():
    """Get the rate limiter instance for use in routes."""
    if HAS_SLOWAPI:
        return Limiter(key_func=get_remote_address)
    return None
