from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ssscreen_web.domain.errors import DomainError

logger = logging.getLogger(__name__)


def error_payload(code: str, message: str, trace_id: str) -> dict[str, object]:
    return {"code": code, "message": message, "field_errors": [], "trace_id": trace_id}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
        field_errors = [
            {
                "field": ".".join(str(part) for part in item["loc"] if part != "body"),
                "message": item["msg"],
                "type": item["type"],
            }
            for item in error.errors()
        ]
        payload = error_payload(
            "request.validation_failed", "The request contains invalid fields", trace_id
        )
        payload["field_errors"] = field_errors
        return JSONResponse(status_code=422, content=payload)

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, error: DomainError) -> JSONResponse:
        trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
        return JSONResponse(
            status_code=error.status_code,
            content=error_payload(error.code, error.message, trace_id),
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, error: Exception) -> JSONResponse:
        trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
        logger.exception("Unhandled API error trace_id=%s", trace_id, exc_info=error)
        return JSONResponse(
            status_code=500,
            content=error_payload("internal.error", "The request could not be completed", trace_id),
        )
