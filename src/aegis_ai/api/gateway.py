"""API Gateway - FastAPI application with single /evaluate-login endpoint."""

import logging, os, threading
from contextlib import asynccontextmanager
from typing import AsyncGenerator, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from aegis_ai.api.schemas import (EvaluateLoginRequest, EvaluateLoginResponse, ErrorResponse)
from aegis_ai.api.service import LoginEvaluationService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("aegis_api")


class ServiceManager:
    """Thread-safe service singleton manager."""
    
    _instance: Optional[LoginEvaluationService] = None
    _lock = threading.Lock()
    _initialized = False
    
    @classmethod
    def get_service(cls) -> LoginEvaluationService:
        """Get or create the evaluation service instance (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = LoginEvaluationService()
                    cls._initialized = True
                    logger.info("LoginEvaluationService initialized")
        return cls._instance
    
    @classmethod
    def shutdown(cls) -> None:
        """Shutdown the service and release resources."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.shutdown()
                cls._instance = None
                cls._initialized = False

                logger.info("LoginEvaluationService shutdown complete")


def get_service() -> LoginEvaluationService:
    """Get the evaluation service instance."""
    return ServiceManager.get_service()


# =============================================================================
# CORS CONFIGURATION
# =============================================================================

def get_cors_origins() -> List[str]:
    """Get allowed CORS origins from environment.
    
    In production, set AEGIS_CORS_ORIGINS environment variable
    to a comma-separated list of allowed origins.
    
    Example: AEGIS_CORS_ORIGINS="https://app.example.com,https://admin.example.com"
    """
    origins_env = os.environ.get("AEGIS_CORS_ORIGINS", "")
    
    if origins_env:
        return [origin.strip() for origin in origins_env.split(",") if origin.strip()]
    
    # Default: restrictive in production, permissive in development
    if os.environ.get("AEGIS_ENVIRONMENT", "development") == "production":
        logger.warning(
            "AEGIS_CORS_ORIGINS not set in production. "
            "CORS will be disabled. Set AEGIS_CORS_ORIGINS for cross-origin access."
        )
        return []
    
    # Development mode: allow all origins (with warning)
    logger.warning("Running in development mode with permissive CORS (allow_origins=['*'])")
    return ["*"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    logger.info("AegisAI API Gateway starting up...")
    get_service()  # Pre-initialize service
    logger.info("AegisAI API Gateway ready")
    
    yield
    
    # Shutdown
    logger.info("AegisAI API Gateway shutting down...")
    ServiceManager.shutdown()
    
    # Shutdown agent executor
    from aegis_ai.orchestration.agent_router import shutdown_executor
    shutdown_executor()
    
    logger.info("AegisAI API Gateway shutdown complete")


# Create FastAPI application
environment = os.environ.get("AEGIS_ENVIRONMENT", "development")
enable_docs_default = "false" if environment == "production" else "true"
enable_docs = os.environ.get("AEGIS_ENABLE_DOCS", enable_docs_default).lower() == "true"

app = FastAPI(
    title="AegisAI API Gateway",
    description=(
        "Fraud detection and trust intelligence API. "),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if enable_docs else None,
    redoc_url="/redoc" if enable_docs else None,
)


# CORS middleware (configured from environment)
cors_origins = get_cors_origins()
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["POST", "GET"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    )


# =============================================================================
# EXCEPTION HANDLERS
# =============================================================================

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Handle validation errors."""
    request_id = getattr(request.state, "request_id", None)
    logger.warning(
        "Validation error",
        extra={"request_id": request_id, "error": str(exc)}
    )
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            error="validation_error",
            message=str(exc),
            request_id=request_id,
        ).model_dump(),
    )


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError) -> JSONResponse:
    """Handle runtime errors from decision flow.
    
    Note: Agent failures should be handled gracefully in the service layer
    and result in an escalation response, not a 500 error.
    """
    request_id = getattr(request.state, "request_id", None)
    logger.error(
        "Runtime error in request processing",
        extra={"request_id": request_id, "error_type": type(exc).__name__},
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="processing_error",
            message="An error occurred while processing the request",
            request_id=request_id,
        ).model_dump(),
    )


@app.exception_handler(AttributeError)
async def attribute_error_handler(request: Request, exc: AttributeError) -> JSONResponse:
    """Handle attribute errors (often from malformed data)."""
    request_id = getattr(request.state, "request_id", None)
    logger.error(
        "Attribute error - possible malformed request",
        extra={"request_id": request_id, "error_type": type(exc).__name__},
        exc_info=True
    )
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            error="invalid_request",
            message="Request contains invalid or missing fields",
            request_id=request_id,
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected errors.
    
    Logs full exception for debugging but returns sanitized message to client.
    """
    request_id = getattr(request.state, "request_id", None)
    logger.exception(
        "Unexpected error",
        extra={"request_id": request_id, "error_type": type(exc).__name__}
    )
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="internal_error",
            message="An unexpected error occurred",
            request_id=request_id,
        ).model_dump(),
    )


# =============================================================================
# MIDDLEWARE
# =============================================================================

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID to each request for tracing."""
    request_id = f"req_{uuid4().hex[:12]}"
    request.state.request_id = request_id
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.post(
    "/evaluate-login",
    response_model=EvaluateLoginResponse,
    responses={
        200: {
            "description": "Successful evaluation",
            "model": EvaluateLoginResponse,
        },
        400: {
            "description": "Invalid request",
            "model": ErrorResponse,
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse,
        },
    },
    summary="Evaluate a login attempt",
    description=(
        "Evaluates a login attempt and returns a decision with explanation. "
        "The response includes the decision (ALLOW/BLOCK/CHALLENGE/ESCALATE), "
        "confidence score, human-readable explanation, escalation flag, and "
        "an audit ID for traceability. "
        "\n\n"
    ),
)
async def evaluate_login(request: EvaluateLoginRequest) -> EvaluateLoginResponse:
    """Evaluate a login attempt.
    
    Args:
        request: Login evaluation request containing event, session,
                 device, and user information.
    
    Returns:
        EvaluateLoginResponse with:
        - decision: The action to take (ALLOW/BLOCK/CHALLENGE/ESCALATE)
        - confidence: Confidence score (0.0 to 1.0)
        - explanation: Human-readable explanation
        - escalation_flag: True if human review required
        - audit_id: Audit trail identifier
    """
    service = get_service()
    
    # Use safe attribute access for logging
    user_id = getattr(request.user, "user_id", "unknown") if request.user else "unknown"
    session_id = getattr(request.session, "session_id", "unknown") if request.session else "unknown"
    event_id = getattr(request.login_event, "event_id", "unknown") if request.login_event else "unknown"
    
    logger.info(
        "Evaluating login request",
        extra={
            "user_id": user_id,
            "session_id": session_id,
            "event_id": event_id,
        }
    )
    
    response = service.evaluate(request)
    
    logger.info(
        "Login evaluation complete",
        extra={
            "decision": response.decision,
            "confidence": f"{response.confidence:.2f}",
            "escalation": response.escalation_flag,
            "audit_id": response.audit_id,
        }
    )
    
    return response


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "service": "aegis-ai-gateway"}


@app.get("/ready")
async def readiness_check() -> dict:
    """Readiness check endpoint.

    Returns 503 until the service singleton is initialized.
    """
    if not ServiceManager._initialized:
        raise HTTPException(status_code=503, detail="not_ready")
    return {"status": "ready", "service": "aegis-ai-gateway"}


# =============================================================================
# DEVELOPMENT SERVER
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "aegis_ai.api.gateway:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
