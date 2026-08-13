"""
exception_handlers.py

Purpose (in simple language):
------------------------------
Ensures every error this API can produce - whether it's "unknown crop",
"malformed JSON", or "something crashed unexpectedly" - comes back to the
caller as the SAME structured JSON shape, with the correct HTTP status
code, instead of a raw Python traceback or an inconsistent ad-hoc message.
"""

import os, sys
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

logger = logging.getLogger("krushimitra.errors")


class AppError(Exception):
    """
    Raised anywhere in the app (validators, services, routers) for a known,
    expected error condition (unknown crop, ineligible pair, model missing,
    etc.) with an explicit HTTP status code.
    """
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


def _structured_error(status_code: int, error: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "detail": detail, "status_code": status_code},
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(f"AppError on {request.method} {request.url.path}: {exc.message}")
    return _structured_error(exc.status_code, error=exc.__class__.__name__, detail=exc.message)


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Triggered automatically by FastAPI/Pydantic for malformed JSON or
    missing/wrong-type required fields - always a 422.
    """
    logger.warning(f"Validation error on {request.method} {request.url.path}: {exc.errors()}")
    detail = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
    return _structured_error(status.HTTP_422_UNPROCESSABLE_ENTITY, error="ValidationError", detail=detail)


async def not_found_handler(request: Request, exc) -> JSONResponse:
    return _structured_error(status.HTTP_404_NOT_FOUND, error="NotFound", detail=str(exc.detail) if hasattr(exc, "detail") else "Not found")


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return _structured_error(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        error="InternalServerError",
        detail="An unexpected error occurred while processing the request.",
    )
